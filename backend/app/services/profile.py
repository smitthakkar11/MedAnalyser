"""User medical profile business logic."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import calculate_age
from app.models.profile import Allergy, Condition, Medication, UserProfile
from app.models.user import User
from app.repositories.profile import ProfileRepository
from app.schemas.profile import (
    AllergyResponse,
    ConditionResponse,
    MedicationResponse,
    ProfileResponse,
    ProfileUpdate,
)

logger = logging.getLogger(__name__)

#: Fields counted when scoring how complete a profile is. Emergency contact
#: counts once as a unit rather than three times, so filling it in is worth the
#: same as any other single answer.
_COMPLETENESS_WEIGHTS = 6


class ProfileService:
    """Reads and replaces the standing medical profile for one user."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._profiles = ProfileRepository(session)

    async def get_profile(self, user: User) -> ProfileResponse:
        """Return the user's profile, creating an empty one on first access.

        Creating on read keeps every caller from having to handle "no profile
        yet"; an empty profile is semantically identical to a missing one.
        """
        profile = await self._profiles.get_profile(user.id)
        if profile is None:
            profile = self._profiles.add_profile(UserProfile(user_id=user.id))
            await self._session.commit()
            await self._session.refresh(profile)

        return await self._build_response(user, profile)

    async def update_profile(self, user: User, payload: ProfileUpdate) -> ProfileResponse:
        """Replace the user's profile with *payload*, atomically.

        The scalar fields and all three collections are written in a single
        transaction, so a partially-saved profile is never observable.
        """
        profile = await self._profiles.get_profile(user.id)
        if profile is None:
            profile = self._profiles.add_profile(UserProfile(user_id=user.id))

        profile.sex_at_birth = payload.sex_at_birth
        profile.gender_identity = payload.gender_identity
        profile.notes = payload.notes
        profile.emergency_contact_name = payload.emergency_contact_name
        profile.emergency_contact_relationship = payload.emergency_contact_relationship
        profile.emergency_contact_phone = payload.emergency_contact_phone

        await self._profiles.replace_collection(
            Allergy,
            user.id,
            [
                Allergy(
                    user_id=user.id,
                    substance=item.substance,
                    reaction=item.reaction,
                    severity=item.severity,
                )
                for item in payload.allergies
            ],
        )
        await self._profiles.replace_collection(
            Condition,
            user.id,
            [
                Condition(
                    user_id=user.id,
                    name=item.name,
                    status=item.status,
                    diagnosed_year=item.diagnosed_year,
                    notes=item.notes,
                )
                for item in payload.conditions
            ],
        )
        await self._profiles.replace_collection(
            Medication,
            user.id,
            [
                Medication(
                    user_id=user.id,
                    name=item.name,
                    dosage=item.dosage,
                    frequency=item.frequency,
                    started_on=item.started_on,
                    is_current=item.is_current,
                    notes=item.notes,
                )
                for item in payload.medications
            ],
        )

        await self._session.commit()
        await self._session.refresh(profile)

        # Counts only — never the medical content itself.
        logger.info(
            "Profile updated",
            extra={
                "user_id": str(user.id),
                "allergies": len(payload.allergies),
                "conditions": len(payload.conditions),
                "medications": len(payload.medications),
            },
        )
        return await self._build_response(user, profile)

    async def _build_response(self, user: User, profile: UserProfile) -> ProfileResponse:
        allergies = await self._profiles.list_allergies(user.id)
        conditions = await self._profiles.list_conditions(user.id)
        medications = await self._profiles.list_medications(user.id)

        return ProfileResponse(
            sex_at_birth=profile.sex_at_birth,
            gender_identity=profile.gender_identity,
            notes=profile.notes,
            emergency_contact_name=profile.emergency_contact_name,
            emergency_contact_relationship=profile.emergency_contact_relationship,
            emergency_contact_phone=profile.emergency_contact_phone,
            allergies=[AllergyResponse.model_validate(row) for row in allergies],
            conditions=[ConditionResponse.model_validate(row) for row in conditions],
            medications=[MedicationResponse.model_validate(row) for row in medications],
            date_of_birth=user.date_of_birth,
            age=calculate_age(user.date_of_birth) if user.date_of_birth else None,
            completeness=_completeness(profile, allergies, conditions, medications),
        )


def _completeness(
    profile: UserProfile,
    allergies: list[Allergy],
    conditions: list[Condition],
    medications: list[Medication],
) -> int:
    """Rough percentage of the profile the user has filled in.

    A prompt to add useful context, not a medical score. "No known allergies" is
    a real answer, so the collections count as answered when the user has
    recorded anything at all; the dashboard offers an explicit way to say none.
    """
    answered = sum(
        [
            profile.sex_at_birth is not None,
            profile.gender_identity is not None,
            profile.emergency_contact_name is not None,
            bool(allergies),
            bool(conditions),
            bool(medications),
        ]
    )
    return round(answered / _COMPLETENESS_WEIGHTS * 100)
