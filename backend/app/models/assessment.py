"""Assessment records: one symptom-analysis episode per row.

An assessment is a point-in-time episode, distinct from the standing medical
profile. It stores not just the conclusion but everything needed to explain and
reproduce it later: what the user wrote, what the extractor understood, what
they answered, which model ran, and what it returned.

Recording `model_name` and `model_version` on every row is what makes a stored
assessment interpretable after the model changes. Without it, an old prediction
is an unattributable number.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AssessmentStatus(StrEnum):
    """Where an assessment is in its lifecycle."""

    #: Created, gathering information through follow-up questions.
    IN_PROGRESS = "in_progress"
    #: Analysed; predictions are stored and the record is immutable.
    COMPLETED = "completed"


class MessageRole(StrEnum):
    ASSISTANT = "assistant"
    USER = "user"


def _enum_column(enum_type: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_type,
        name=name,
        values_callable=lambda members: [member.value for member in members],
    )


class Assessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One symptom assessment belonging to exactly one user."""

    __tablename__ = "assessments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[AssessmentStatus] = mapped_column(
        _enum_column(AssessmentStatus, "assessment_status"),
        nullable=False,
        default=AssessmentStatus.IN_PROGRESS,
        index=True,
    )

    #: Exactly what the user typed, preserved verbatim.
    input_text: Mapped[str] = mapped_column(Text, nullable=False)

    # --- what the extractor and the follow-up answers produced --------------
    #: Canonical symptoms fed to the model. JSONB because it is a variable-length
    #: list read as a whole, never queried element-wise.
    recognised_symptoms: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    #: Symptoms the user explicitly denied. Kept because "no chest pain" is
    #: clinically meaningful and must not be confused with "not mentioned".
    rejected_symptoms: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    #: Phrases the extractor could not map. Retained so the vocabulary can be
    #: improved from real usage.
    unrecognised_terms: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    duration_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # --- previous care, as reported by the user -----------------------------
    # Explicit columns rather than a blob: these are a fixed, known set that
    # later phases and the timeline will query.
    previous_consultation: Mapped[bool | None] = mapped_column(nullable=True)
    previous_diagnosis: Mapped[str | None] = mapped_column(String(300), nullable=True)
    previous_medication: Mapped[str | None] = mapped_column(String(300), nullable=True)
    treatment_response: Mapped[str | None] = mapped_column(String(40), nullable=True)
    still_taking_medication: Mapped[bool | None] = mapped_column(nullable=True)

    # --- safety ---------------------------------------------------------
    # Produced by the deterministic red-flag engine, never by the model, and
    # stored so a completed assessment records what the user was warned about.
    safety_level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="none", server_default="none"
    )
    safety_flags: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    # --- model output -------------------------------------------------------
    #: Ranked candidates as returned by the inference service. JSONB genuinely
    #: fits: the shape depends on the model version that produced it.
    predictions: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # --- specialty recommendation ----------------------------------------
    # A transparent lookup from the predicted condition, overridden when the
    # red-flag engine says this needs emergency care rather than a referral.
    recommended_specialty: Mapped[str | None] = mapped_column(String(60), nullable=True)
    specialty_display: Mapped[str | None] = mapped_column(String(80), nullable=True)
    specialty_reason: Mapped[str | None] = mapped_column(String(400), nullable=True)
    specialty_basis: Mapped[str | None] = mapped_column(String(20), nullable=True)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list[AssessmentMessage]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="AssessmentMessage.created_at",
        lazy="selectin",
    )

    @property
    def is_completed(self) -> bool:
        return self.status is AssessmentStatus.COMPLETED

    @property
    def top_condition(self) -> str | None:
        """The highest-scoring candidate, for list views."""
        if not self.predictions:
            return None
        first = self.predictions[0]
        return str(first.get("condition")) if isinstance(first, dict) else None


class AssessmentMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One turn of the intake conversation.

    Stored so an assessment can be replayed and audited: which question was
    asked, and exactly what the user replied.
    """

    __tablename__ = "assessment_messages"

    assessment_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[MessageRole] = mapped_column(
        _enum_column(MessageRole, "message_role"), nullable=False
    )
    #: The rule that produced an assistant question, or that a user reply
    #: answers. Null for the opening free-text message.
    question_key: Mapped[str | None] = mapped_column(String(60), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    assessment: Mapped[Assessment] = relationship(back_populates="messages")
