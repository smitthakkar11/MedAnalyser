"""User medical profile and dashboard endpoints.

Both depend on `OnboardedUser`, so they are reachable only by an authenticated,
age-verified account. Every query is scoped to that user's id in the repository
layer — the identity comes from the verified token, never from the request body
or a path parameter, so there is nothing for a caller to tamper with.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import DbSession, OnboardedUser
from app.schemas.dashboard import DashboardResponse
from app.schemas.profile import ProfileResponse, ProfileUpdate
from app.services.dashboard import DashboardService
from app.services.profile import ProfileService

router = APIRouter(tags=["profile"])


@router.get("/profile", response_model=ProfileResponse, summary="The signed-in user's profile")
async def get_profile(current_user: OnboardedUser, session: DbSession) -> ProfileResponse:
    """Return the profile, creating an empty one on first access."""
    return await ProfileService(session).get_profile(current_user)


@router.put("/profile", response_model=ProfileResponse, summary="Replace the profile")
async def update_profile(
    payload: ProfileUpdate,
    current_user: OnboardedUser,
    session: DbSession,
) -> ProfileResponse:
    """Replace the profile and all of its collections in a single transaction."""
    return await ProfileService(session).update_profile(current_user, payload)


@router.get("/dashboard", response_model=DashboardResponse, summary="Dashboard summary")
async def get_dashboard(current_user: OnboardedUser, session: DbSession) -> DashboardResponse:
    return await DashboardService(session).build(current_user)
