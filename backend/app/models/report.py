"""Uploaded medical reports and the values read out of them.

Two tables, kept apart on purpose:

* ``medical_reports`` — the upload itself: who owns it, where the bytes live,
  how the text was obtained.
* ``report_values``   — one row per laboratory result read off the page.

Every value records the line it came from and whether the report printed a
reference range. Nothing here is inferred by a model: this is what the document
said. Phase 7 will combine these with model output, and the distinction between
*extracted* and *inferred* has to survive that.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ReportStatus(StrEnum):
    """Where an upload is in processing."""

    PENDING = "pending"
    PROCESSED = "processed"
    #: Stored, but no text or no values could be read.
    FAILED = "failed"


class ExtractionMethod(StrEnum):
    """How the text was obtained from the document."""

    TEXT_LAYER = "text_layer"
    OCR = "ocr"
    MIXED = "mixed"
    NONE = "none"


class ValueFlag(StrEnum):
    """Where a value sits relative to the range printed on the report."""

    NORMAL = "normal"
    LOW = "low"
    HIGH = "high"
    #: The report printed no usable range, so no judgement was made.
    UNKNOWN = "unknown"


def _enum_column(enum_type: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_type,
        name=name,
        values_callable=lambda members: [member.value for member in members],
    )


class MedicalReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One uploaded document belonging to exactly one user."""

    __tablename__ = "medical_reports"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: The name the user's file had. A display label only — never used to build
    #: a path, because an uploaded filename is attacker-controlled.
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Provider-independent handle from StorageService.
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    #: SHA-256, so a re-upload of the same file is recognisable.
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    status: Mapped[ReportStatus] = mapped_column(
        _enum_column(ReportStatus, "report_status"),
        nullable=False,
        default=ReportStatus.PENDING,
        index=True,
    )
    extraction_method: Mapped[ExtractionMethod | None] = mapped_column(
        _enum_column(ExtractionMethod, "extraction_method"), nullable=True
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Full extracted text, kept so extraction can be re-run and improved
    #: without asking the user to upload again.
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Collection date printed on the report, when one could be read.
    report_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    #: Why processing failed, for the user. Never a raw exception.
    error_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    values: Mapped[list[ReportValue]] = relationship(
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="ReportValue.display_name",
        lazy="selectin",
    )

    @property
    def abnormal_count(self) -> int:
        """Values outside the range the report itself printed."""
        return sum(1 for value in self.values if value.flag in (ValueFlag.LOW, ValueFlag.HIGH))


class ReportValue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One laboratory result read off a report."""

    __tablename__ = "report_values"

    report_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("medical_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Denormalised so the medical timeline can query a user's values across
    #: reports without joining, and so ownership filters stay uniform.
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: Canonical analyte key, e.g. `hemoglobin`.
    analyte: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)

    #: Only ever the range printed on this report.
    reference_low: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_high: Mapped[float | None] = mapped_column(Float, nullable=True)
    reference_text: Mapped[str | None] = mapped_column(String(80), nullable=True)

    flag: Mapped[ValueFlag] = mapped_column(
        _enum_column(ValueFlag, "value_flag"), nullable=False, default=ValueFlag.UNKNOWN
    )
    #: True when the printed unit was not one we recognise. Such a value must
    #: not be compared across reports.
    unit_unrecognised: Mapped[bool] = mapped_column(nullable=False, default=False)

    #: The line this was read from, so a user can check what was understood.
    source_line: Mapped[str | None] = mapped_column(String(200), nullable=True)

    report: Mapped[MedicalReport] = relationship(back_populates="values")
