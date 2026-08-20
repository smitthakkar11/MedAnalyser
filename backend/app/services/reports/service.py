"""Medical report upload and processing.

    upload → validate → store → extract text → read lab values → persist

Validation is deliberately thorough. This is the one endpoint that accepts
arbitrary bytes from the internet, so the file is checked by declared type, by
extension, by size, and by its actual magic bytes — a client-supplied
content-type is a claim, not evidence.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, ConflictError, NotFoundError, ValidationError
from app.models.report import (
    ExtractionMethod,
    MedicalReport,
    ReportStatus,
    ReportValue,
    ValueFlag,
)
from app.models.user import User
from app.repositories.report import ReportRepository
from app.schemas.report import ReportDetail, ReportSummary, ReportValueResponse
from app.services.reports.lab_extractor import LabExtractor, get_lab_extractor
from app.services.reports.pdf_extractor import PdfExtractionError, extract_document
from app.services.storage.base import StorageError, StorageService

logger = logging.getLogger(__name__)

#: Only PDFs for now. Images are a later extension of the same pipeline.
ALLOWED_CONTENT_TYPES = frozenset({"application/pdf"})
ALLOWED_EXTENSIONS = frozenset({".pdf"})

#: The first bytes of a PDF. Checked because a declared content-type is a claim.
PDF_MAGIC = b"%PDF-"

#: Dates printed on reports, e.g. "Collected on: 14/03/2026".
_DATE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"), "%Y-%m-%d"),
    (re.compile(r"\b(\d{2}/\d{2}/\d{4})\b"), "%d/%m/%Y"),
    (re.compile(r"\b(\d{2}-\d{2}-\d{4})\b"), "%d-%m-%Y"),
    (re.compile(r"\b(\d{1,2} [A-Za-z]{3,9} \d{4})\b"), "%d %B %Y"),
)


class UnsupportedFileError(ValidationError):
    """Raised when an upload is not a file this pipeline can process."""

    code = "unsupported_file"


class FileTooLargeError(AppError):
    """Raised when an upload exceeds the configured size limit."""

    status_code = 413
    code = "file_too_large"
    message = "That file is too large."


class ReportService:
    """Stores uploaded reports and reads laboratory values out of them."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        storage: StorageService,
        *,
        lab_extractor: LabExtractor | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._storage = storage
        self._repository = ReportRepository(session)
        self._labs = lab_extractor or get_lab_extractor()

    # ------------------------------------------------------------- uploading

    def validate(self, *, filename: str, content_type: str, content: bytes) -> None:
        """Reject anything this pipeline should not accept.

        Raises:
            UnsupportedFileError: wrong type, extension, or magic bytes.
            FileTooLargeError: over the configured limit.
        """
        limit = self._settings.max_upload_size_mb * 1024 * 1024
        if len(content) > limit:
            raise FileTooLargeError(
                f"That file is {len(content) / 1_048_576:.1f} MB. "
                f"The limit is {self._settings.max_upload_size_mb} MB."
            )
        if not content:
            raise UnsupportedFileError("That file is empty.")

        if content_type not in ALLOWED_CONTENT_TYPES:
            raise UnsupportedFileError("Only PDF reports can be uploaded at the moment.")

        extension = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
        if extension not in ALLOWED_EXTENSIONS:
            raise UnsupportedFileError("Only PDF reports can be uploaded at the moment.")

        # The declared content-type is whatever the client chose to send.
        if not content.startswith(PDF_MAGIC):
            raise UnsupportedFileError("That file is not a valid PDF.")

    async def upload(
        self, user: User, *, filename: str, content_type: str, content: bytes
    ) -> ReportDetail:
        """Validate, store and process an uploaded report."""
        self.validate(filename=filename, content_type=content_type, content=content)

        try:
            stored = await self._storage.save(
                owner_id=str(user.id),
                filename=filename,
                content=content,
                content_type=content_type,
            )
        except StorageError as exc:
            logger.error("Report storage failed", extra={"error": str(exc)})
            raise AppError("The report could not be stored.") from exc

        duplicate = await self._repository.find_by_checksum(user.id, stored.checksum)
        if duplicate is not None:
            # Keep the original; drop the copy we just wrote.
            await self._storage.delete(stored.key)
            raise ConflictError(
                "You have already uploaded this file.",
                details={"existing_report_id": str(duplicate.id)},
            )

        report = MedicalReport(
            user_id=user.id,
            original_filename=_display_filename(filename),
            storage_key=stored.key,
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            checksum=stored.checksum,
            status=ReportStatus.PENDING,
        )
        self._repository.add(report)
        await self._session.commit()
        await self._session.refresh(report)

        await self._process(report, content)
        return self._detail(report, include_text=False)

    async def _process(self, report: MedicalReport, content: bytes) -> None:
        """Extract text and laboratory values, then record the outcome.

        A document that yields nothing is marked `failed` with a message the
        user can act on — not left silently empty.
        """
        try:
            document = extract_document(content)
        except PdfExtractionError as exc:
            report.status = ReportStatus.FAILED
            report.error_message = str(exc)
            report.processed_at = datetime.now(UTC)
            await self._session.commit()
            await self._session.refresh(report)
            return

        report.extraction_method = ExtractionMethod(document.method.value)
        report.page_count = document.page_count
        report.extracted_text = document.text or None
        report.report_date = _read_report_date(document.text)
        report.processed_at = datetime.now(UTC)

        if document.is_empty:
            report.status = ReportStatus.FAILED
            report.error_message = (
                "No readable text was found. If this is a scan, a clearer image may help."
            )
            await self._session.commit()
            await self._session.refresh(report)
            return

        extracted = self._labs.extract(document.text)
        self._repository.add_values(
            [
                ReportValue(
                    report_id=report.id,
                    user_id=report.user_id,
                    analyte=value.analyte,
                    display_name=value.display_name,
                    value=value.value,
                    unit=value.unit,
                    reference_low=value.reference_low,
                    reference_high=value.reference_high,
                    reference_text=value.reference_text,
                    flag=ValueFlag(value.flag.value),
                    unit_unrecognised=value.unit_unrecognised,
                    source_line=value.source_line,
                )
                for value in extracted
            ]
        )
        report.status = ReportStatus.PROCESSED
        if not extracted:
            report.error_message = (
                "Text was read, but no laboratory values were recognised. "
                "MedAnalyser understands a fixed list of tests."
            )

        await self._session.commit()
        await self._session.refresh(report)

        # Counts only — never the extracted medical content itself.
        logger.info(
            "Report processed",
            extra={
                "report_id": str(report.id),
                "method": report.extraction_method.value if report.extraction_method else None,
                "pages": report.page_count,
                "n_values": len(extracted),
            },
        )

    # --------------------------------------------------------------- reading

    async def get(
        self, user: User, report_id: uuid.UUID, *, include_text: bool = False
    ) -> ReportDetail:
        return self._detail(await self._require(user, report_id), include_text=include_text)

    async def list_reports(
        self, user: User, *, limit: int = 50, offset: int = 0
    ) -> list[ReportSummary]:
        reports = await self._repository.list_for_user(user.id, limit=limit, offset=offset)
        return [
            ReportSummary(
                id=report.id,
                original_filename=report.original_filename,
                status=report.status,
                size_bytes=report.size_bytes,
                page_count=report.page_count,
                extraction_method=report.extraction_method,
                report_date=report.report_date,
                value_count=len(report.values),
                abnormal_count=report.abnormal_count,
                created_at=report.created_at,
            )
            for report in reports
        ]

    async def download(self, user: User, report_id: uuid.UUID) -> tuple[bytes, str, str]:
        """Return the original bytes, its content type and display filename."""
        report = await self._require(user, report_id)
        try:
            content = await self._storage.read(report.storage_key)
        except StorageError as exc:
            raise NotFoundError("The stored file is no longer available.") from exc
        return content, report.content_type, report.original_filename

    async def delete(self, user: User, report_id: uuid.UUID) -> None:
        """Remove a report, its values, and the stored file."""
        report = await self._require(user, report_id)
        storage_key = report.storage_key

        await self._repository.delete(report)
        await self._session.commit()

        # After the row is gone: an orphaned file is recoverable, a database row
        # pointing at a deleted file is not.
        try:
            await self._storage.delete(storage_key)
        except StorageError as exc:
            logger.warning(
                "Stored file could not be removed",
                extra={"report_id": str(report_id), "error": str(exc)},
            )

    async def _require(self, user: User, report_id: uuid.UUID) -> MedicalReport:
        report = await self._repository.get_for_user(report_id, user.id)
        if report is None:
            raise NotFoundError("Report not found.")
        return report

    def _detail(self, report: MedicalReport, *, include_text: bool) -> ReportDetail:
        return ReportDetail(
            id=report.id,
            original_filename=report.original_filename,
            status=report.status,
            content_type=report.content_type,
            size_bytes=report.size_bytes,
            page_count=report.page_count,
            extraction_method=report.extraction_method,
            report_date=report.report_date,
            error_message=report.error_message,
            values=[ReportValueResponse.model_validate(value) for value in report.values],
            extracted_text=report.extracted_text if include_text else None,
            created_at=report.created_at,
            processed_at=report.processed_at,
        )


def _display_filename(filename: str) -> str:
    """A safe label for the UI.

    Never used to build a path — the storage key is generated — but it is shown
    back to the user, so path separators and control characters are stripped.
    """
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", filename.replace("\\", "/").split("/")[-1])
    return cleaned.strip()[:255] or "report.pdf"


def _read_report_date(text: str) -> date | None:
    """The collection date printed on the report, if one can be read.

    Only the first 2000 characters are searched: the date belongs in the header,
    and scanning the whole document would pick up dates of birth and print
    timestamps. Future dates are rejected as misreads.
    """
    head = text[:2000]
    today = date.today()
    for pattern, fmt in _DATE_PATTERNS:
        for match in pattern.finditer(head):
            try:
                parsed = datetime.strptime(match.group(1), fmt).date()
            except ValueError:
                continue
            if date(1900, 1, 1) <= parsed <= today:
                return parsed
    return None
