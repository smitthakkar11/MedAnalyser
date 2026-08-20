"""User medical profile: background information that informs every assessment.

The profile is the standing clinical context for a user — what they are allergic
to, what conditions they live with, what they take regularly. It is separate
from an assessment, which is a point-in-time episode.

Each collection is its own table rather than a JSONB blob: these are discrete
records that later phases filter, compare against retrieved evidence, and cite
in an assessment's reasoning. Date of birth deliberately lives on `users`, not
here, so there is exactly one source of truth for age verification.
"""

from __future__ import annotations

import uuid
from datetime import date
from enum import StrEnum

from sqlalchemy import Boolean, Date, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User


class SexAtBirth(StrEnum):
    """Sex assigned at birth.

    Recorded because laboratory reference ranges and the prevalence of many
    conditions differ by it. Kept distinct from gender identity, which is a
    separate free-text field, and always optional.
    """

    FEMALE = "female"
    MALE = "male"
    INTERSEX = "intersex"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class AllergySeverity(StrEnum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    UNKNOWN = "unknown"


class ConditionStatus(StrEnum):
    ACTIVE = "active"
    MANAGED = "managed"
    RESOLVED = "resolved"


def _enum_column(enum_type: type[StrEnum], name: str) -> Enum:
    """A native PostgreSQL enum storing the member *values*, not their names."""
    return Enum(
        enum_type,
        name=name,
        values_callable=lambda members: [member.value for member in members],
    )


class UserProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Scalar profile fields. Exactly one row per user."""

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    sex_at_birth: Mapped[SexAtBirth | None] = mapped_column(
        _enum_column(SexAtBirth, "sex_at_birth"), nullable=True
    )
    gender_identity: Mapped[str | None] = mapped_column(String(80), nullable=True)

    #: Free text the user considers relevant but that fits no other field.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    emergency_contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    emergency_contact_relationship: Mapped[str | None] = mapped_column(String(60), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)

    user: Mapped[User] = relationship()


class Allergy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Something the user reacts to, as reported by them."""

    __tablename__ = "allergies"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    substance: Mapped[str] = mapped_column(String(120), nullable=False)
    reaction: Mapped[str | None] = mapped_column(String(200), nullable=True)
    severity: Mapped[AllergySeverity] = mapped_column(
        _enum_column(AllergySeverity, "allergy_severity"),
        nullable=False,
        default=AllergySeverity.UNKNOWN,
    )


class Condition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An existing medical condition, as reported by the user.

    This is the user's own account of their history, not a clinical record and
    not an AI conclusion. Later phases must keep those three sources distinct.
    """

    __tablename__ = "conditions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[ConditionStatus] = mapped_column(
        _enum_column(ConditionStatus, "condition_status"),
        nullable=False,
        default=ConditionStatus.ACTIVE,
    )
    diagnosed_year: Mapped[int | None] = mapped_column(nullable=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Medication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A medication the user takes or has taken.

    Dosage and frequency are free text on purpose: they are recorded exactly as
    the user reports them. MedAnalyser never derives, suggests or adjusts a dose.
    """

    __tablename__ = "medications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    dosage: Mapped[str | None] = mapped_column(String(80), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(80), nullable=True)
    started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
