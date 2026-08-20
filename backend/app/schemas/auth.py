"""Request and response schemas for authentication and onboarding."""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import MAXIMUM_AGE_YEARS, MINIMUM_AGE_YEARS

#: Passwords must be long enough to resist offline attack. Length is the single
#: most valuable requirement; complexity rules mostly push users toward
#: predictable substitutions, so only a minimum length and a blocklist apply.
PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128

#: Rejected outright regardless of length.
_COMMON_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "password123",
        "12345678",
        "123456789",
        "1234567890",
        "qwertyuiop",
        "letmein123",
        "iloveyou1",
        "administrator",
        "medanalyser",
    }
)


def _validate_password(value: str) -> str:
    if len(value) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"Password must be at least {PASSWORD_MIN_LENGTH} characters.")
    if len(value) > PASSWORD_MAX_LENGTH:
        raise ValueError(f"Password must be at most {PASSWORD_MAX_LENGTH} characters.")
    if value.lower() in _COMMON_PASSWORDS:
        raise ValueError("This password is too common. Please choose another.")
    if re.fullmatch(r"(.)\1*", value):
        raise ValueError("Password must not be a single repeated character.")
    return value


class SignupRequest(BaseModel):
    """Create an account with an email address and password."""

    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    # Length is checked in `_validate_password` rather than by Field constraints,
    # so the user sees a written explanation instead of Pydantic's generic
    # "String should have at least N characters".
    password: str = Field(description=f"At least {PASSWORD_MIN_LENGTH} characters.")

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Name must not be blank.")
        return stripped

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        return _validate_password(value)


class LoginRequest(BaseModel):
    """Authenticate with an email address and password."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("email")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return value.strip().lower()


class GoogleAuthRequest(BaseModel):
    """Sign in (or sign up) with a Google ID token obtained by the browser."""

    id_token: str = Field(min_length=1, description="A Google-issued OpenID Connect ID token.")


class OnboardingRequest(BaseModel):
    """Complete onboarding by supplying a date of birth.

    The age requirement is enforced in the service layer against the server's
    clock — this validator only rejects values that cannot be a date of birth at
    all, so that an under-age user receives a clear age message rather than a
    generic validation error.
    """

    date_of_birth: date

    @field_validator("date_of_birth")
    @classmethod
    def _plausible_date(cls, value: date) -> date:
        today = datetime.now().date()
        if value > today:
            raise ValueError("Date of birth cannot be in the future.")
        if value.year < today.year - MAXIMUM_AGE_YEARS:
            raise ValueError("Please enter a valid date of birth.")
        return value


class UserResponse(BaseModel):
    """The authenticated user, as returned to the client.

    Deliberately excludes `password_hash` and `token_version`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
    date_of_birth: date | None
    onboarding_complete: bool
    has_password: bool
    linked_providers: list[str] = Field(default_factory=list)
    created_at: datetime


class AuthResponse(BaseModel):
    """Successful authentication.

    The refresh token is *not* in this body — it is set as an httpOnly cookie so
    that browser scripts cannot read it.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds.")
    user: UserResponse


class MessageResponse(BaseModel):
    """A simple acknowledgement."""

    message: str


class AgeRequirementResponse(BaseModel):
    """Returned when a user does not meet the minimum age."""

    message: str
    minimum_age: int = MINIMUM_AGE_YEARS
