"""Medical report endpoints.

    POST   /api/reports              upload a PDF; it is processed immediately
    GET    /api/reports              list your reports
    GET    /api/reports/{id}         one report and the values read from it
    GET    /api/reports/{id}/file    download the original
    DELETE /api/reports/{id}         remove it and its stored file

Every endpoint requires an authenticated, age-verified user, and every query is
scoped to that user's id — the identity comes from the verified token, never
from the path.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Query, Response, UploadFile, status

from app.api.deps import AppSettings, DbSession, OnboardedUser, Storage
from app.schemas.report import ReportDetail, ReportSummary
from app.services.reports.service import FileTooLargeError, ReportService

router = APIRouter(prefix="/reports", tags=["reports"])

#: Module-level singleton: FastAPI needs the marker as a default, and calling
#: `File(...)` inline in the signature is evaluated once at import anyway.
_UPLOADED_FILE = File(description="A PDF laboratory report.")


@router.post(
    "",
    response_model=ReportDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a medical report",
    responses={
        409: {"description": "You have already uploaded this file."},
        413: {"description": "The file exceeds the size limit."},
        422: {"description": "The file is not a readable PDF."},
    },
)
async def upload_report(
    current_user: OnboardedUser,
    session: DbSession,
    settings: AppSettings,
    storage: Storage,
    file: UploadFile = _UPLOADED_FILE,
) -> ReportDetail:
    """Store a PDF and read any laboratory values it contains.

    Values are **extracted from the document**, never inferred. Where the report
    prints no reference range, the value is recorded without a normal/abnormal
    judgement rather than compared against a hard-coded one.
    """
    service = ReportService(session, settings, storage)

    # Read with a cap rather than trusting the declared length: a client can
    # send more bytes than its own content-length header claims.
    limit = settings.max_upload_size_mb * 1024 * 1024
    content = await file.read(limit + 1)
    if len(content) > limit:
        raise FileTooLargeError(f"The file exceeds the {settings.max_upload_size_mb} MB limit.")

    return await service.upload(
        current_user,
        filename=file.filename or "report.pdf",
        content_type=file.content_type or "",
        content=content,
    )


@router.get("", response_model=list[ReportSummary], summary="List your reports")
async def list_reports(
    current_user: OnboardedUser,
    session: DbSession,
    settings: AppSettings,
    storage: Storage,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ReportSummary]:
    service = ReportService(session, settings, storage)
    return await service.list_reports(current_user, limit=limit, offset=offset)


@router.get(
    "/{report_id}",
    response_model=ReportDetail,
    summary="One report and its extracted values",
    responses={404: {"description": "No such report for this user."}},
)
async def get_report(
    report_id: uuid.UUID,
    current_user: OnboardedUser,
    session: DbSession,
    settings: AppSettings,
    storage: Storage,
    include_text: bool = Query(default=False, description="Include the full extracted text."),
) -> ReportDetail:
    service = ReportService(session, settings, storage)
    return await service.get(current_user, report_id, include_text=include_text)


@router.get(
    "/{report_id}/file",
    summary="Download the original file",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download_report(
    report_id: uuid.UUID,
    current_user: OnboardedUser,
    session: DbSession,
    settings: AppSettings,
    storage: Storage,
) -> Response:
    """Return the uploaded document itself.

    Served as an attachment with a fixed filename: echoing a user-supplied name
    into `Content-Disposition` is a header-injection route, and the browser
    should not be persuaded to render the file inline either.
    """
    service = ReportService(session, settings, storage)
    content, content_type, _ = await service.download(current_user, report_id)
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="report-{report_id}.pdf"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete(
    "/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a report and its stored file",
)
async def delete_report(
    report_id: uuid.UUID,
    current_user: OnboardedUser,
    session: DbSession,
    settings: AppSettings,
    storage: Storage,
) -> None:
    service = ReportService(session, settings, storage)
    await service.delete(current_user, report_id)
