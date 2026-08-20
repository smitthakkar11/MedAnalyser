"""Authentication business logic.

Route handlers stay thin: they hand a validated request to this service and
serialise what comes back. Every rule that decides *who* a caller is, and
whether an account may be created or linked, lives here.
"""

from __future__ import annotations

import logging
import uuid as uuid_module
from dataclasses import dataclass
from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import (
    AuthenticationError,
    ConflictError,
    PermissionDeniedError,
    ServiceUnavailableError,
)
from app.core.security import (
    MINIMUM_AGE_YEARS,
    TokenError,
    TokenType,
    calculate_age,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.models.user import OAuthAccount, User
from app.repositories.user import UserRepository
from app.services.auth.google import (
    GOOGLE_PROVIDER,
    GoogleIdentity,
    GoogleTokenVerifier,
    GoogleVerificationError,
)

logger = logging.getLogger(__name__)

#: Returned when an existing password account must be used to link Google.
LINK_REQUIRED_CODE = "google_link_required"


class AgeRequirementError(PermissionDeniedError):
    """Raised when a user does not meet the minimum age for the application."""

    code = "age_requirement_not_met"
    message = f"MedAnalyser is only available to adults aged {MINIMUM_AGE_YEARS} and over."


class OnboardingRequiredError(PermissionDeniedError):
    """Raised when an authenticated user has not yet completed onboarding."""

    code = "onboarding_required"
    message = "Please complete onboarding before using this feature."


@dataclass(frozen=True)
class IssuedTokens:
    """A freshly issued token pair."""

    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    """Signup, login, token issuing, Google sign-in and account linking."""

    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        *,
        google_verifier: GoogleTokenVerifier | None = None,
    ) -> None:
        self._session = session
        self._settings = settings
        self._users = UserRepository(session)
        self._google_verifier = google_verifier

    # ------------------------------------------------------------------ tokens

    def issue_tokens(self, user: User) -> IssuedTokens:
        """Mint an access/refresh pair for *user*."""
        subject = str(user.id)
        return IssuedTokens(
            access_token=create_access_token(subject, self._settings),
            refresh_token=create_refresh_token(subject, user.token_version, self._settings),
            expires_in=self._settings.access_token_expire_minutes * 60,
        )

    async def user_from_access_token(self, token: str) -> User:
        """Resolve the user an access token belongs to.

        Raises:
            AuthenticationError: if the token is invalid or the user is gone.
        """
        try:
            payload = decode_token(token, TokenType.ACCESS, self._settings)
            user_id = _parse_uuid(payload["sub"])
        except (TokenError, ValueError, KeyError) as exc:
            raise AuthenticationError("Your session is invalid. Please sign in again.") from exc

        user = await self._users.get_by_id(user_id)
        if user is None:
            raise AuthenticationError("Your session is invalid. Please sign in again.")
        return user

    async def refresh(self, refresh_token: str) -> tuple[User, IssuedTokens]:
        """Exchange a refresh token for a new pair.

        The token's ``tv`` claim must match the user's current ``token_version``,
        which is how logout-everywhere invalidates outstanding tokens.
        """
        try:
            payload = decode_token(refresh_token, TokenType.REFRESH, self._settings)
            user_id = _parse_uuid(payload["sub"])
        except (TokenError, ValueError, KeyError) as exc:
            raise AuthenticationError("Your session has expired. Please sign in again.") from exc

        user = await self._users.get_by_id(user_id)
        if user is None or payload.get("tv") != user.token_version:
            raise AuthenticationError("Your session has expired. Please sign in again.")

        return user, self.issue_tokens(user)

    async def revoke_all_sessions(self, user: User) -> None:
        """Invalidate every outstanding refresh token for *user*."""
        user.token_version += 1
        await self._session.commit()

    # ------------------------------------------------------ password accounts

    async def signup(self, *, name: str, email: str, password: str) -> User:
        """Create a password-backed account.

        Raises:
            ConflictError: if the email address is already registered.
        """
        user = User(name=name, email=email, password_hash=hash_password(password))
        self._users.add(user)
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            # Unique violation on email. The address is one the caller supplied,
            # so reporting the conflict reveals nothing they did not already know.
            raise ConflictError("An account with this email address already exists.") from exc

        await self._session.refresh(user)
        logger.info("Account created", extra={"user_id": str(user.id), "method": "password"})
        return user

    async def login(self, *, email: str, password: str) -> User:
        """Authenticate with email and password.

        The same error is returned whether the address is unknown or the password
        is wrong, and a hash is always computed, so neither the response nor the
        response time reveals whether an account exists.
        """
        user = await self._users.get_by_email(email)
        stored_hash = user.password_hash if user and user.password_hash else _DUMMY_HASH

        password_ok = verify_password(password, stored_hash)
        if user is None or user.password_hash is None or not password_ok:
            raise AuthenticationError("Incorrect email address or password.")

        # Transparently upgrade hashes whose parameters are now outdated.
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
            await self._session.commit()

        logger.info("Login succeeded", extra={"user_id": str(user.id), "method": "password"})
        return user

    # ---------------------------------------------------------- google sign-in

    async def google_sign_in(self, id_token: str) -> User:
        """Sign in or register with a verified Google ID token.

        Resolution order:

        1. The Google subject is already linked → sign that user in.
        2. No linked subject, and the email is unknown → create an account.
        3. No linked subject, but the email belongs to an existing account →
           refuse, and tell the caller to sign in and link deliberately. This is
           what prevents a duplicate account for the same person, without
           silently attaching a provider to an account whose owner never asked.
        """
        identity = await self._verify_google(id_token)

        existing = await self._users.get_by_oauth_account(GOOGLE_PROVIDER, identity.subject)
        if existing is not None:
            logger.info("Login succeeded", extra={"user_id": str(existing.id), "method": "google"})
            return existing

        collision = await self._users.get_by_email(identity.email)
        if collision is not None:
            raise ConflictError(
                "An account with this email address already exists. "
                "Sign in with your password, then link Google from your settings.",
                details={"reason": LINK_REQUIRED_CODE},
            )

        user = User(
            name=identity.name or identity.email.split("@")[0],
            email=identity.email,
            password_hash=None,
        )
        self._users.add(user)
        self._users.add_oauth_account(
            OAuthAccount(
                user=user,
                provider=GOOGLE_PROVIDER,
                provider_account_id=identity.subject,
            )
        )
        try:
            await self._session.commit()
        except IntegrityError as exc:
            # Two concurrent first-time sign-ins for the same identity.
            await self._session.rollback()
            raced = await self._users.get_by_oauth_account(GOOGLE_PROVIDER, identity.subject)
            if raced is not None:
                return raced
            raise ConflictError("This Google account could not be linked.") from exc

        await self._session.refresh(user)
        logger.info("Account created", extra={"user_id": str(user.id), "method": "google"})
        return user

    async def link_google(self, user: User, id_token: str) -> User:
        """Link a verified Google identity to an already-authenticated user."""
        identity = await self._verify_google(id_token)

        owner = await self._users.get_by_oauth_account(GOOGLE_PROVIDER, identity.subject)
        if owner is not None:
            if owner.id == user.id:
                return user  # Already linked; linking again is a no-op.
            raise ConflictError("This Google account is already linked to another user.")

        self._users.add_oauth_account(
            OAuthAccount(
                user_id=user.id,
                provider=GOOGLE_PROVIDER,
                provider_account_id=identity.subject,
            )
        )
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            raise ConflictError("This Google account could not be linked.") from exc

        await self._session.refresh(user)
        logger.info("Provider linked", extra={"user_id": str(user.id), "provider": "google"})
        return user

    async def _verify_google(self, id_token: str) -> GoogleIdentity:
        if self._google_verifier is None:
            raise ServiceUnavailableError("Google sign-in is not configured on this server.")
        try:
            identity = await self._google_verifier.verify(id_token)
        except GoogleVerificationError as exc:
            raise AuthenticationError(str(exc)) from exc

        # An unverified address must never be used to match an existing account.
        if not identity.email_verified:
            raise AuthenticationError(
                "Your Google email address is not verified. Verify it with Google first."
            )
        return identity

    # ------------------------------------------------------------- onboarding

    async def complete_onboarding(self, user: User, date_of_birth: date) -> User:
        """Record the date of birth after checking the age requirement.

        The age is computed from the server's clock, never from anything the
        client sends, and nothing is persisted when the check fails.
        """
        if calculate_age(date_of_birth) < MINIMUM_AGE_YEARS:
            logger.info("Onboarding refused: age requirement", extra={"user_id": str(user.id)})
            raise AgeRequirementError()

        user.date_of_birth = date_of_birth
        await self._session.commit()
        await self._session.refresh(user)
        logger.info("Onboarding completed", extra={"user_id": str(user.id)})
        return user

    async def linked_providers(self, user: User) -> list[str]:
        return await self._users.linked_providers(user.id)


# A valid Argon2 hash of a value no password will match. Verifying against it
# when no account exists keeps login timing independent of account existence.
_DUMMY_HASH = hash_password("medanalyser-nonexistent-account-placeholder")


def _parse_uuid(value: object) -> uuid_module.UUID:
    """Parse a token subject into a UUID, raising ValueError if malformed."""
    return uuid_module.UUID(str(value))
