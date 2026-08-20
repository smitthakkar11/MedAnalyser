"""Authentication and onboarding endpoints.

Token delivery: the **access token** is returned in the response body and is
meant to live in memory on the client; the **refresh token** is set as an
httpOnly, SameSite=Lax cookie scoped to the auth path, so browser scripts
cannot read it and it is not sent with cross-site requests.
"""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Response, status

from app.api.deps import AppSettings, AuthServiceDep, CurrentUser
from app.core.config import Settings
from app.core.errors import AuthenticationError
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    GoogleAuthRequest,
    LoginRequest,
    MessageResponse,
    OnboardingRequest,
    SignupRequest,
    UserResponse,
)
from app.services.auth.service import AuthService, IssuedTokens

router = APIRouter(prefix="/auth", tags=["authentication"])

REFRESH_COOKIE_NAME = "medanalyser_refresh"


def _refresh_cookie_path(settings: Settings) -> str:
    """Scope the cookie to the auth routes so it is not sent to every endpoint."""
    return f"{settings.api_prefix}/auth"


def _set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        httponly=True,
        # Secure requires HTTPS, which is not available on plain localhost.
        secure=settings.is_production,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path=_refresh_cookie_path(settings),
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path=_refresh_cookie_path(settings),
    )


async def _auth_response(
    user: User,
    tokens: IssuedTokens,
    auth_service: AuthService,
    response: Response,
    settings: Settings,
) -> AuthResponse:
    _set_refresh_cookie(response, tokens.refresh_token, settings)
    return AuthResponse(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
        user=await _user_response(user, auth_service),
    )


async def _user_response(user: User, auth_service: AuthService) -> UserResponse:
    return UserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        date_of_birth=user.date_of_birth,
        onboarding_complete=user.onboarding_complete,
        has_password=user.has_password,
        linked_providers=await auth_service.linked_providers(user),
        created_at=user.created_at,
    )


@router.post(
    "/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account with email and password",
    responses={409: {"description": "The email address is already registered."}},
)
async def signup(
    payload: SignupRequest,
    auth_service: AuthServiceDep,
    settings: AppSettings,
    response: Response,
) -> AuthResponse:
    """Register a new account and sign the user in.

    Onboarding (date of birth and the age check) happens afterwards.
    """
    user = await auth_service.signup(
        name=payload.name, email=payload.email, password=payload.password
    )
    return await _auth_response(
        user, auth_service.issue_tokens(user), auth_service, response, settings
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Sign in with email and password",
    responses={401: {"description": "Incorrect email address or password."}},
)
async def login(
    payload: LoginRequest,
    auth_service: AuthServiceDep,
    settings: AppSettings,
    response: Response,
) -> AuthResponse:
    user = await auth_service.login(email=payload.email, password=payload.password)
    return await _auth_response(
        user, auth_service.issue_tokens(user), auth_service, response, settings
    )


@router.post(
    "/google",
    response_model=AuthResponse,
    summary="Sign in or register with Google",
    responses={
        401: {"description": "The Google ID token could not be verified."},
        409: {"description": "An account with this email exists; link Google instead."},
        503: {"description": "Google sign-in is not configured on this server."},
    },
)
async def google_auth(
    payload: GoogleAuthRequest,
    auth_service: AuthServiceDep,
    settings: AppSettings,
    response: Response,
) -> AuthResponse:
    """Verify a Google ID token server-side, then sign in or create an account."""
    user = await auth_service.google_sign_in(payload.id_token)
    return await _auth_response(
        user, auth_service.issue_tokens(user), auth_service, response, settings
    )


@router.post(
    "/link-google",
    response_model=UserResponse,
    summary="Link a Google account to the signed-in user",
    responses={409: {"description": "That Google account is linked to another user."}},
)
async def link_google(
    payload: GoogleAuthRequest,
    current_user: CurrentUser,
    auth_service: AuthServiceDep,
) -> UserResponse:
    user = await auth_service.link_google(current_user, payload.id_token)
    return await _user_response(user, auth_service)


@router.post(
    "/refresh",
    response_model=AuthResponse,
    summary="Exchange the refresh cookie for a new access token",
    responses={401: {"description": "The refresh token is missing, expired or revoked."}},
)
async def refresh(
    auth_service: AuthServiceDep,
    settings: AppSettings,
    response: Response,
    medanalyser_refresh: str | None = Cookie(default=None),
) -> AuthResponse:
    if not medanalyser_refresh:
        raise AuthenticationError("Your session has expired. Please sign in again.")
    user, tokens = await auth_service.refresh(medanalyser_refresh)
    return await _auth_response(user, tokens, auth_service, response, settings)


@router.post("/logout", response_model=MessageResponse, summary="Sign out")
async def logout(
    current_user: CurrentUser,
    auth_service: AuthServiceDep,
    settings: AppSettings,
    response: Response,
) -> MessageResponse:
    """Clear the refresh cookie and revoke every outstanding refresh token.

    The current access token stays valid until it expires — that is inherent to
    stateless JWTs, and is why access token lifetime is kept short.
    """
    await auth_service.revoke_all_sessions(current_user)
    _clear_refresh_cookie(response, settings)
    return MessageResponse(message="Signed out.")


@router.get("/me", response_model=UserResponse, summary="The signed-in user")
async def me(current_user: CurrentUser, auth_service: AuthServiceDep) -> UserResponse:
    return await _user_response(current_user, auth_service)


@router.post(
    "/onboarding",
    response_model=UserResponse,
    summary="Complete onboarding with a date of birth",
    responses={403: {"description": "The user does not meet the minimum age."}},
)
async def onboarding(
    payload: OnboardingRequest,
    current_user: CurrentUser,
    auth_service: AuthServiceDep,
) -> UserResponse:
    """Record the date of birth after verifying the age requirement server-side."""
    user = await auth_service.complete_onboarding(current_user, payload.date_of_birth)
    return await _user_response(user, auth_service)
