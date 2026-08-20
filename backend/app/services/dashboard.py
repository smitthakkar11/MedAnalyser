"""Dashboard aggregation.

One service assembles the whole dashboard so the frontend needs a single
request, and so the counts stay consistent with each other.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.dashboard import DashboardResponse, ProfileSummary
from app.services.profile import ProfileService


class DashboardService:
    """Builds the signed-in user's dashboard summary."""

    def __init__(self, session: AsyncSession) -> None:
        self._profiles = ProfileService(session)

    async def build(self, user: User) -> DashboardResponse:
        profile = await self._profiles.get_profile(user)

        return DashboardResponse(
            user_name=user.name,
            profile=ProfileSummary(
                completeness=profile.completeness,
                age=profile.age,
                date_of_birth=profile.date_of_birth,
                allergy_count=len(profile.allergies),
                condition_count=len(profile.conditions),
                current_medication_count=sum(
                    1 for medication in profile.medications if medication.is_current
                ),
            ),
        )
