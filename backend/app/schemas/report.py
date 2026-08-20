"""Request and response schemas for medical reports."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.report import ExtractionMethod, ReportStatus, ValueFlag


class ReportValueResponse(BaseModel):
    """One laboratory result read off a report.

    Everything here was **read from the document**. Nothing is inferred by a
    model, and no reference range is supplied by MedAnalyser — `flag` is
    `unknown` unless the report printed a range of its own.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    analyte: str
    display_name: str
    value: float
    unit: str | None
    reference_low: float | None
    reference_high: float | None
    reference_text: str | None
    flag: ValueFlag
    unit_unrecognised: bool = Field(
        description=(
            "The printed unit was not recognised, so the value is stored as "
            "written and must not be compared across reports."
        )
    )
    source_line: str | None


class ReportSummary(BaseModel):
    """A report as it appears in a list."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    status: ReportStatus
    size_bytes: int
    page_count: int | None
    extraction_method: ExtractionMethod | None
    report_date: date | None
    value_count: int
    abnormal_count: int
    created_at: datetime


class ReportDetail(BaseModel):
    """A report and everything read out of it."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    status: ReportStatus
    content_type: str
    size_bytes: int
    page_count: int | None
    extraction_method: ExtractionMethod | None
    report_date: date | None
    error_message: str | None
    values: list[ReportValueResponse] = Field(default_factory=list)
    #: Text is returned only on request; it can be long and is sensitive.
    extracted_text: str | None = None
    created_at: datetime
    processed_at: datetime | None
