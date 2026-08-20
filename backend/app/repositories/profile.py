"""Data access for the user medical profile and its collections.

Every method takes a ``user_id`` and filters on it. Ownership is therefore
enforced by construction: there is no query here that can return another user's
rows, so no route can leak them by forgetting a check.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Allergy, Condition, Medication, UserProfile

#: The user-owned collections managed as part of the profile document.
CollectionModel = type[Allergy] | type[Condition] | type[Medication]


class ProfileRepository:
    """Reads and writes for `user_profiles`, `allergies`, `conditions`, `medications`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_profile(self, user_id: uuid.UUID) -> UserProfile | None:
        result = await self._session.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    def add_profile(self, profile: UserProfile) -> UserProfile:
        """Stage a new profile row. The caller commits."""
        self._session.add(profile)
        return profile

    async def list_allergies(self, user_id: uuid.UUID) -> list[Allergy]:
        result = await self._session.execute(
            select(Allergy).where(Allergy.user_id == user_id).order_by(Allergy.substance)
        )
        return list(result.scalars().all())

    async def list_conditions(self, user_id: uuid.UUID) -> list[Condition]:
        result = await self._session.execute(
            select(Condition).where(Condition.user_id == user_id).order_by(Condition.name)
        )
        return list(result.scalars().all())

    async def list_medications(self, user_id: uuid.UUID) -> list[Medication]:
        result = await self._session.execute(
            select(Medication)
            .where(Medication.user_id == user_id)
            # Current medications first, then alphabetically.
            .order_by(Medication.is_current.desc(), Medication.name)
        )
        return list(result.scalars().all())

    async def replace_collection(
        self,
        model: CollectionModel,
        user_id: uuid.UUID,
        rows: list[Allergy] | list[Condition] | list[Medication],
    ) -> None:
        """Delete this user's rows in *model* and stage *rows* in their place.

        Scoped to `user_id`, so a replacement can never touch another user's
        records. Runs in the caller's transaction: the delete and the insert
        either both land or neither does.
        """
        await self._session.execute(delete(model).where(model.user_id == user_id))
        self._session.add_all(rows)
