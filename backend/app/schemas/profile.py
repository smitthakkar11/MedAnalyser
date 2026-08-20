"""Request and response schemas for the user medical profile."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.profile import AllergySeverity, ConditionStatus, SexAtBirth

#: Upper bound on each collection. Generous for real use, but bounded so a
#: single request cannot be used to write an unlimited number of rows.
MAX_COLLECTION_ITEMS = 100

#: Earliest plausible diagnosis year.
MIN_DIAGNOSIS_YEAR = 1900


def _blank_to_none(value: str | None) -> str | None:
    """Treat a whitespace-only field as absent, so empty inputs are not stored."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


T = TypeVar("T", bound=BaseModel)


class _Trimmed(BaseModel):
    """Base that normalises every optional string field to trimmed-or-None."""

    @field_validator("*", mode="before")
    @classmethod
    def _strip_strings(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


# --------------------------------------------------------------------- items


class AllergyInput(_Trimmed):
    """An allergy as submitted by the user."""

    substance: str = Field(min_length=1, max_length=120)
    reaction: str | None = Field(default=None, max_length=200)
    severity: AllergySeverity = AllergySeverity.UNKNOWN

    @field_validator("reaction")
    @classmethod
    def _normalise(cls, value: str | None) -> str | None:
        return _blank_to_none(value)


class AllergyResponse(AllergyInput):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class ConditionInput(_Trimmed):
    """An existing condition as reported by the user."""

    name: str = Field(min_length=1, max_length=160)
    status: ConditionStatus = ConditionStatus.ACTIVE
    diagnosed_year: int | None = Field(default=None, ge=MIN_DIAGNOSIS_YEAR)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("notes")
    @classmethod
    def _normalise(cls, value: str | None) -> str | None:
        return _blank_to_none(value)

    @field_validator("diagnosed_year")
    @classmethod
    def _not_in_the_future(cls, value: int | None) -> int | None:
        if value is not None and value > datetime.now().year:
            raise ValueError("Diagnosis year cannot be in the future.")
        return value


class ConditionResponse(ConditionInput):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class MedicationInput(_Trimmed):
    """A medication, recorded exactly as the user reports it.

    Dosage and frequency are free text: MedAnalyser records what the user says
    and never derives, validates or suggests a dose.
    """

    name: str = Field(min_length=1, max_length=160)
    dosage: str | None = Field(default=None, max_length=80)
    frequency: str | None = Field(default=None, max_length=80)
    started_on: date | None = None
    is_current: bool = True
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("dosage", "frequency", "notes")
    @classmethod
    def _normalise(cls, value: str | None) -> str | None:
        return _blank_to_none(value)

    @field_validator("started_on")
    @classmethod
    def _not_in_the_future(cls, value: date | None) -> date | None:
        if value is not None and value > datetime.now().date():
            raise ValueError("Start date cannot be in the future.")
        return value


class MedicationResponse(MedicationInput):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


# ------------------------------------------------------------------ profile

Collection = Annotated[list[T], Field(max_length=MAX_COLLECTION_ITEMS)]


class ProfileUpdate(_Trimmed):
    """A complete replacement of the user's profile.

    The collections are *replacing* sets, not deltas: whatever is submitted
    becomes the profile. That matches how the form behaves — the user edits the
    whole page and saves it — and avoids a per-item CRUD surface for data that
    is only ever edited as a single document.
    """

    sex_at_birth: SexAtBirth | None = None
    gender_identity: str | None = Field(default=None, max_length=80)
    notes: str | None = Field(default=None, max_length=2000)

    emergency_contact_name: str | None = Field(default=None, max_length=120)
    emergency_contact_relationship: str | None = Field(default=None, max_length=60)
    emergency_contact_phone: str | None = Field(default=None, max_length=40)

    allergies: Collection[AllergyInput] = Field(default_factory=list)
    conditions: Collection[ConditionInput] = Field(default_factory=list)
    medications: Collection[MedicationInput] = Field(default_factory=list)

    @field_validator(
        "gender_identity",
        "notes",
        "emergency_contact_name",
        "emergency_contact_relationship",
        "emergency_contact_phone",
    )
    @classmethod
    def _normalise(cls, value: str | None) -> str | None:
        return _blank_to_none(value)


class ProfileResponse(BaseModel):
    """The user's profile, including the fields owned by their account record."""

    sex_at_birth: SexAtBirth | None
    gender_identity: str | None
    notes: str | None

    emergency_contact_name: str | None
    emergency_contact_relationship: str | None
    emergency_contact_phone: str | None

    allergies: list[AllergyResponse]
    conditions: list[ConditionResponse]
    medications: list[MedicationResponse]

    #: Mirrored from `users` for convenience; changed through onboarding, not here.
    date_of_birth: date | None
    age: int | None = Field(description="Derived server-side from the date of birth.")

    #: Rough share of the optional profile that has been filled in, for the
    #: dashboard's prompt to complete it.
    completeness: int = Field(ge=0, le=100)
