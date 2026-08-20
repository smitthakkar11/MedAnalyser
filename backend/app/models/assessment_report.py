"""Link between an assessment and the medical reports it considered.

A join table rather than a column, because an assessment may draw on several
reports and a report may be relevant to several assessments over time.

Attaching a report does **not** feed its values into the condition model. The
model is trained on symptoms only; lab results travel alongside a prediction as
separately-sourced evidence, and the two are never merged. See
`docs/architecture.md` for why.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AssessmentReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One report attached to one assessment."""

    __tablename__ = "assessment_reports"
    __table_args__ = (
        # Attaching the same report twice is a no-op, not two rows.
        UniqueConstraint("assessment_id", "report_id"),
    )

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("medical_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
