"""Schemas for the dashboard summary."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class ProfileSummary(BaseModel):
    """Just enough profile detail for the dashboard's context card."""

    completeness: int = Field(ge=0, le=100)
    age: int | None
    date_of_birth: date | None
    allergy_count: int
    condition_count: int
    current_medication_count: int


class DashboardResponse(BaseModel):
    """Everything the dashboard renders in one round trip.

    Assessments, reports and the medical timeline arrive in Phases 4, 5 and 10.
    Their counts are present and correct — zero — rather than absent, so the
    contract does not change when those features land.
    """

    user_name: str
    profile: ProfileSummary

    assessment_count: int = Field(
        default=0, description="Saved assessments. Populated from Phase 4."
    )
    report_count: int = Field(
        default=0, description="Uploaded medical reports. Populated from Phase 5."
    )
