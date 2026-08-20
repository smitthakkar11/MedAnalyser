"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import AuthenticationError
from app.db.session import get_db_session
from app.models.user import User
from app.services.auth.google import GoogleTokenVerifier, build_google_verifier
from app.services.auth.service import AuthService, OnboardingRequiredError
from app.services.ml.condition_prediction.inference import ConditionPredictionService
from app.services.ml.condition_prediction.model_loader import ModelUnavailableError
from app.services.storage.base import StorageService
from app.services.storage.factory import build_storage_service


def get_app_settings(request: Request) -> Settings:
    """Return the settings the running app was built with.

    Reads `app.state.settings` rather than calling `get_settings()` directly, so
    that an app constructed via `create_app(custom_settings)` — as tests do —
    is actually served with those settings.
    """
    settings = getattr(request.app.state, "settings", None)
    return settings if isinstance(settings, Settings) else get_settings()


#: Request-scoped database session.
DbSession = Annotated[AsyncSession, Depends(get_db_session)]

#: Settings of the running application.
AppSettings = Annotated[Settings, Depends(get_app_settings)]


def get_google_verifier(request: Request, settings: AppSettings) -> GoogleTokenVerifier | None:
    """Return the Google verifier, or None when Google sign-in is unconfigured.

    A verifier placed on `app.state` wins, which is how tests inject a stub in
    place of a real network round-trip to Google's JWKS endpoint.
    """
    override = getattr(request.app.state, "google_verifier", None)
    if override is not None:
        return override
    return build_google_verifier(settings)


GoogleVerifier = Annotated[GoogleTokenVerifier | None, Depends(get_google_verifier)]


def get_auth_service(
    session: DbSession,
    settings: AppSettings,
    google_verifier: GoogleVerifier,
) -> AuthService:
    return AuthService(session, settings, google_verifier=google_verifier)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]

# auto_error=False so a missing header produces our own JSON error envelope
# rather than FastAPI's default shape.
_bearer_scheme = HTTPBearer(auto_error=False, description="JWT access token")
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)]


def get_condition_predictor(request: Request) -> ConditionPredictionService | None:
    """Return the condition predictor, or None when no model is available.

    A predictor placed on `app.state` wins, which is how tests inject a small
    in-fixture model instead of depending on trained artifacts being present.
    Returning None rather than raising keeps the rest of the API working on a
    checkout where training has not been run; the assessment service turns it
    into a 503 only at the point analysis is actually requested.
    """
    override = getattr(request.app.state, "condition_predictor", None)
    if override is not None:
        return override
    try:
        return ConditionPredictionService()
    except ModelUnavailableError:
        return None


ConditionPredictor = Annotated[ConditionPredictionService | None, Depends(get_condition_predictor)]


def get_storage_service(request: Request, settings: AppSettings) -> StorageService:
    """Return the configured storage provider.

    A provider placed on `app.state` wins, which is how tests point uploads at
    a temporary directory instead of the developer's storage root.
    """
    override = getattr(request.app.state, "storage_service", None)
    if override is not None:
        return override
    return build_storage_service(settings)


Storage = Annotated[StorageService, Depends(get_storage_service)]


async def get_current_user(
    credentials: BearerCredentials,
    auth_service: AuthServiceDep,
) -> User:
    """Resolve the authenticated user from the `Authorization: Bearer` header.

    Raises:
        AuthenticationError: when the header is missing, malformed, or the token
            is invalid, expired, or of the wrong type.
    """
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Sign in to access this resource.")
    return await auth_service.user_from_access_token(credentials.credentials)


#: An authenticated user. Onboarding may still be incomplete.
CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_onboarded_user(current_user: CurrentUser) -> User:
    """An authenticated user who has completed onboarding.

    Every medical feature depends on this rather than `CurrentUser`, so an
    account that has not passed the age check cannot reach them.
    """
    if not current_user.onboarding_complete:
        raise OnboardingRequiredError()
    return current_user


#: An authenticated, onboarded (and therefore age-verified) user.
OnboardedUser = Annotated[User, Depends(get_onboarded_user)]
