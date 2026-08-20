"""Signup: account creation, validation and password storage."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

SIGNUP = "/api/auth/signup"


async def test_signup_creates_account_and_signs_in(api_client: AsyncClient) -> None:
    response = await api_client.post(
        SIGNUP,
        json={
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "password": "a-strong-passphrase",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] == 30 * 60
    assert body["user"]["email"] == "ada@example.com"
    assert body["user"]["name"] == "Ada Lovelace"
    # Onboarding is a separate step: a brand-new account is not yet age-verified.
    assert body["user"]["onboarding_complete"] is False
    assert body["user"]["has_password"] is True
    assert body["user"]["linked_providers"] == []


async def test_signup_never_returns_password_material(api_client: AsyncClient) -> None:
    response = await api_client.post(
        SIGNUP,
        json={"name": "Ada", "email": "ada@example.com", "password": "a-strong-passphrase"},
    )

    serialised = response.text
    assert "password_hash" not in serialised
    assert "a-strong-passphrase" not in serialised
    assert "token_version" not in serialised


async def test_signup_stores_an_argon2_hash_not_the_password(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    await api_client.post(
        SIGNUP,
        json={"name": "Ada", "email": "ada@example.com", "password": "a-strong-passphrase"},
    )

    user = (
        await db_session.execute(select(User).where(User.email == "ada@example.com"))
    ).scalar_one()
    assert user.password_hash is not None
    assert user.password_hash.startswith("$argon2id$")
    assert "a-strong-passphrase" not in user.password_hash


async def test_signup_sets_an_httponly_refresh_cookie(api_client: AsyncClient) -> None:
    response = await api_client.post(
        SIGNUP,
        json={"name": "Ada", "email": "ada@example.com", "password": "a-strong-passphrase"},
    )

    cookie_header = response.headers["set-cookie"]
    assert "medanalyser_refresh=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "Path=/api/auth" in cookie_header
    assert "SameSite=lax" in cookie_header
    # The refresh token must never be readable from the response body.
    assert "refresh_token" not in response.json()


async def test_signup_rejects_a_duplicate_email(api_client: AsyncClient) -> None:
    payload = {"name": "Ada", "email": "ada@example.com", "password": "a-strong-passphrase"}
    assert (await api_client.post(SIGNUP, json=payload)).status_code == 201

    response = await api_client.post(SIGNUP, json=payload)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_signup_treats_email_case_insensitively(api_client: AsyncClient) -> None:
    await api_client.post(
        SIGNUP,
        json={"name": "Ada", "email": "ada@example.com", "password": "a-strong-passphrase"},
    )

    response = await api_client.post(
        SIGNUP,
        json={"name": "Impostor", "email": "ADA@Example.COM", "password": "another-passphrase"},
    )

    assert response.status_code == 409


@pytest.mark.parametrize(
    "password",
    ["short", "password123", "aaaaaaaaaaaaaa", ""],
    ids=["too-short", "too-common", "single-repeated-char", "empty"],
)
async def test_signup_rejects_weak_passwords(api_client: AsyncClient, password: str) -> None:
    response = await api_client.post(
        SIGNUP, json={"name": "Ada", "email": "ada@example.com", "password": password}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    "email",
    ["not-an-email", "@example.com", "ada@", ""],
    ids=["no-at", "no-local", "no-domain", "empty"],
)
async def test_signup_rejects_invalid_emails(api_client: AsyncClient, email: str) -> None:
    response = await api_client.post(
        SIGNUP, json={"name": "Ada", "email": email, "password": "a-strong-passphrase"}
    )

    assert response.status_code == 422


async def test_signup_rejects_a_blank_name(api_client: AsyncClient) -> None:
    response = await api_client.post(
        SIGNUP, json={"name": "   ", "email": "ada@example.com", "password": "a-strong-passphrase"}
    )

    assert response.status_code == 422


async def test_validation_errors_never_echo_the_submitted_password(
    api_client: AsyncClient,
) -> None:
    """A 422 must not reflect the password back to the client.

    Pydantic includes the offending value in its raw error output; the handler
    strips it. Without that, a rejected signup would return the plaintext
    password in the response body and in any log that captured it.
    """
    secret = "password123"  # rejected as too common

    response = await api_client.post(
        SIGNUP, json={"name": "Ada", "email": "ada@example.com", "password": secret}
    )

    assert response.status_code == 422
    assert secret not in response.text
    errors = response.json()["error"]["details"]["errors"]
    assert errors[0]["field"] == "password"
    assert all("input" not in error for error in errors)


async def test_validation_messages_are_readable(api_client: AsyncClient) -> None:
    """Messages reach the UI without Pydantic's internal prefixes."""
    response = await api_client.post(
        SIGNUP, json={"name": "Ada", "email": "ada@example.com", "password": "short"}
    )

    message = response.json()["error"]["details"]["errors"][0]["message"]
    assert message == "Password must be at least 10 characters."
    assert not message.startswith("Value error")
