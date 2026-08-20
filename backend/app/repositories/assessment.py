"""Data access for assessments and their intake conversation.

Every read takes a `user_id` and filters on it, so ownership is enforced by
construction: there is no query here capable of returning another user's
assessment, and no route can leak one by forgetting a check.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment, AssessmentMessage


class AssessmentRepository:
    """Reads and writes for `assessments` and `assessment_messages`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_for_user(self, assessment_id: uuid.UUID, user_id: uuid.UUID) -> Assessment | None:
        """Fetch one assessment **owned by** *user_id*.

        The ownership filter is part of the query rather than a check after the
        fact, so a missing row and someone else's row are indistinguishable to
        the caller — which is also what stops the endpoint confirming that an
        id exists.
        """
        result = await self._session.execute(
            select(Assessment).where(Assessment.id == assessment_id, Assessment.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 50, offset: int = 0
    ) -> list[Assessment]:
        result = await self._session.execute(
            select(Assessment)
            .where(Assessment.user_id == user_id)
            .order_by(Assessment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(Assessment).where(Assessment.user_id == user_id)
        )
        return int(result.scalar_one())

    def add(self, assessment: Assessment) -> Assessment:
        """Stage a new assessment. The caller commits."""
        self._session.add(assessment)
        return assessment

    def add_message(self, message: AssessmentMessage) -> AssessmentMessage:
        self._session.add(message)
        return message

    async def delete(self, assessment: Assessment) -> None:
        """Remove an assessment; messages cascade."""
        await self._session.delete(assessment)
