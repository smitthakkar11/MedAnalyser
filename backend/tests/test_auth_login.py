"""Login and session lifecycle: credentials, tokens, refresh and logout."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient

from app.core.config import Settings
from app.core.security import TokenType, create_access_token

SIGNUP = "/api/auth/signup"
LOGIN = "/api/auth/login"
ME = "/api/auth/me"

PASSWORD = "a-strong-passphrase"


async def _register(client: AsyncClient, email: str = "ada@example.com") -> dict:
    response = await client.post(SIGNUP, json={"name": "Ada", "email": email, "password": PASSWORD})
    assert response.status_code == 201
    return response.json()


async def test_login_with_correct_credentials(api_client: AsyncClient) -> None:
    await _register(api_client)

    response = await api_client.post(LOGIN, json={"email": "ada@example.com", "password": PASSWORD})

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "ada@example.com"
    assert response.json()["access_token"]


async def test_login_is_case_insensitive_on_email(api_client: AsyncClient) -> None:
    await _register(api_client)

    response = await api_client.post(LOGIN, json={"email": "ADA@Example.COM", "password": PASSWORD})

    assert response.status_code == 200


async def test_login_rejects_a_wrong_password(api_client: AsyncClient) -> None:
    await _register(api_client)

    response = await api_client.post(
        LOGIN, json={"email": "ada@example.com", "password": "not-the-right-one"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_error"


async def test_login_does_not_reveal_whether_an_account_exists(api_client: AsyncClient) -> None:
    """Unknown address and wrong password must be indistinguishable."""
    await _register(api_client)

    wrong_password = await api_client.post(
        LOGIN, json={"email": "ada@example.com", "password": "not-the-right-one"}
    )
    unknown_account = await api_client.post(
        LOGIN, json={"email": "nobody@example.com", "password": "not-the-right-one"}
    )

    assert wrong_password.status_code == unknown_account.status_code == 401
    assert wrong_password.json()["error"]["message"] == unknown_account.json()["error"]["message"]
    assert wrong_password.json()["error"]["code"] == unknown_account.json()["error"]["code"]


async def test_login_rejects_an_oauth_only_account(
    api_client: AsyncClient, google_verifier
) -> None:
    """An account with no password cannot be signed into with one."""
    google_verifier.register("tok", subject="g-1", email="grace@example.com", name="Grace")
    assert (await api_client.post("/api/auth/google", json={"id_token": "tok"})).status_code == 200

    response = await api_client.post(
        LOGIN, json={"email": "grace@example.com", "password": PASSWORD}
    )

    assert response.status_code == 401


# ------------------------------------------------------------------ /me


async def test_me_returns_the_signed_in_user(api_client: AsyncClient) -> None:
    token = (await _register(api_client))["access_token"]

    response = await api_client.get(ME, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "ada@example.com"


async def test_me_requires_a_token(api_client: AsyncClient) -> None:
    response = await api_client.get(ME)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_error"


@pytest.mark.parametrize(
    "header",
    ["Bearer not-a-jwt", "Bearer ", "Basic abc123", "not-even-a-scheme"],
    ids=["garbage-jwt", "empty", "wrong-scheme", "malformed"],
)
async def test_me_rejects_malformed_authorization_headers(
    api_client: AsyncClient, header: str
) -> None:
    response = await api_client.get(ME, headers={"Authorization": header})

    assert response.status_code == 401


async def test_me_rejects_an_expired_token(api_client: AsyncClient, settings: Settings) -> None:
    await _register(api_client)
    expired = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": TokenType.ACCESS.value,
            "iat": int((datetime.now(UTC) - timedelta(hours=2)).timestamp()),
            "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = await api_client.get(ME, headers={"Authorization": f"Bearer {expired}"})

    assert response.status_code == 401


async def test_me_rejects_a_token_signed_with_another_key(
    api_client: AsyncClient, settings: Settings
) -> None:
    forged = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": TokenType.ACCESS.value,
            "iat": int(datetime.now(UTC).timestamp()),
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
        },
        "an-attacker-controlled-secret-of-sufficient-length",
        algorithm="HS256",
    )

    response = await api_client.get(ME, headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401


async def test_a_refresh_token_cannot_be_used_as_an_access_token(
    api_client: AsyncClient,
) -> None:
    """Token types are not interchangeable."""
    await _register(api_client)
    refresh_cookie = api_client.cookies["medanalyser_refresh"]

    response = await api_client.get(ME, headers={"Authorization": f"Bearer {refresh_cookie}"})

    assert response.status_code == 401


async def test_a_token_for_a_deleted_user_is_rejected(
    api_client: AsyncClient, settings: Settings
) -> None:
    """A well-formed token whose subject no longer exists must not authenticate."""
    token = create_access_token(str(uuid.uuid4()), settings)

    response = await api_client.get(ME, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


# ------------------------------------------------------------- refresh/logout


async def test_refresh_issues_a_new_access_token(api_client: AsyncClient) -> None:
    await _register(api_client)

    response = await api_client.post("/api/auth/refresh")

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert response.json()["user"]["email"] == "ada@example.com"


async def test_refresh_without_a_cookie_is_rejected(api_client: AsyncClient) -> None:
    response = await api_client.post("/api/auth/refresh")

    assert response.status_code == 401


async def test_logout_clears_the_cookie_and_revokes_refresh_tokens(
    api_client: AsyncClient,
) -> None:
    token = (await _register(api_client))["access_token"]
    stolen_refresh = api_client.cookies["medanalyser_refresh"]

    logout = await api_client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})

    assert logout.status_code == 200
    # The browser is told to drop the cookie...
    assert 'medanalyser_refresh=""' in logout.headers["set-cookie"]
    # ...and a copy captured beforehand is now useless, because token_version moved.
    api_client.cookies.set("medanalyser_refresh", stolen_refresh, path="/api/auth")
    replay = await api_client.post("/api/auth/refresh")
    assert replay.status_code == 401


async def test_logout_requires_authentication(api_client: AsyncClient) -> None:
    assert (await api_client.post("/api/auth/logout")).status_code == 401
