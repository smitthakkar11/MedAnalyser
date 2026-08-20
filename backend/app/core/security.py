"""Password hashing and JSON Web Token issuing/verification.

Passwords are hashed with Argon2id, the current password-hashing competition
winner and the default recommendation for new applications. Hashes are never
logged and plaintext passwords never leave this module.

Two token kinds are issued:

* **access**  — short-lived, sent as a ``Bearer`` header, held in memory by the
  client. Not revocable before expiry; kept short for that reason.
* **refresh** — longer-lived, delivered in an httpOnly cookie so that XSS cannot
  read it. Carries the owner's ``token_version``, which lets the server
  invalidate every outstanding refresh token for a user at once.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import Any, Final

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings

#: Argon2id with the library defaults, which track current guidance.
_password_hasher: Final = PasswordHasher()

#: Minimum age required to use the application.
MINIMUM_AGE_YEARS: Final = 18

#: Upper bound on a plausible date of birth, guarding against typos.
MAXIMUM_AGE_YEARS: Final = 120


class TokenType(StrEnum):
    """Distinguishes token kinds so one can never be used in place of another."""

    ACCESS = "access"
    REFRESH = "refresh"


class TokenError(Exception):
    """Raised when a token is absent, malformed, expired or of the wrong type."""


def hash_password(password: str) -> str:
    """Return an Argon2id hash of *password*."""
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Check *password* against *password_hash*, returning False on any mismatch."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True when *password_hash* uses outdated parameters and should be upgraded."""
    try:
        return _password_hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return False


def _create_token(
    *,
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    settings: Settings,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type.value,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, settings: Settings) -> str:
    """Issue a short-lived access token for *subject* (a user id)."""
    return _create_token(
        subject=subject,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
        settings=settings,
    )


def create_refresh_token(subject: str, token_version: int, settings: Settings) -> str:
    """Issue a refresh token carrying the user's current ``token_version``."""
    return _create_token(
        subject=subject,
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
        settings=settings,
        extra_claims={"tv": token_version},
    )


def decode_token(token: str, expected_type: TokenType, settings: Settings) -> dict[str, Any]:
    """Decode and validate *token*, enforcing signature, expiry and token type.

    Raises:
        TokenError: if the token is malformed, expired, signed with the wrong
            key, or is not of *expected_type*.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError("Token is invalid or has expired.") from exc

    if payload.get("type") != expected_type.value:
        raise TokenError("Token is not valid for this operation.")

    return payload


def calculate_age(date_of_birth: date, *, today: date | None = None) -> int:
    """Return the age in completed years on *today* (default: the current date).

    Leap-year birthdays are handled by tuple comparison: someone born 29 February
    has their birthday treated as having occurred on 1 March in non-leap years,
    which is the common legal convention.
    """
    today = today or datetime.now(UTC).date()
    had_birthday = (today.month, today.day) >= (date_of_birth.month, date_of_birth.day)
    return today.year - date_of_birth.year - (0 if had_birthday else 1)


def is_adult(date_of_birth: date, *, today: date | None = None) -> bool:
    """True when the person is at least :data:`MINIMUM_AGE_YEARS` years old."""
    return calculate_age(date_of_birth, today=today) >= MINIMUM_AGE_YEARS
