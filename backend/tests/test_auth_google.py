"""Google sign-in, account creation and deliberate account linking."""

from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.main import create_app
from app.models.user import OAuthAccount, User

GOOGLE = "/api/auth/google"
LINK = "/api/auth/link-google"
SIGNUP = "/api/auth/signup"
PASSWORD = "a-strong-passphrase"


async def test_new_google_user_gets_an_account_and_a_linked_identity(
    api_client: AsyncClient, google_verifier, db_session: AsyncSession
) -> None:
    google_verifier.register(
        "tok", subject="google-sub-1", email="grace@example.com", name="Grace Hopper"
    )

    response = await api_client.post(GOOGLE, json={"id_token": "tok"})

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "grace@example.com"
    assert body["user"]["name"] == "Grace Hopper"
    # No password was set, and Google is recorded as a linked provider.
    assert body["user"]["has_password"] is False
    assert body["user"]["linked_providers"] == ["google"]
    # Google is not a trustworthy source for date of birth.
    assert body["user"]["onboarding_complete"] is False

    account = (
        await db_session.execute(
            select(OAuthAccount).where(OAuthAccount.provider_account_id == "google-sub-1")
        )
    ).scalar_one()
    assert account.provider == "google"


async def test_returning_google_user_reuses_the_same_account(
    api_client: AsyncClient, google_verifier, db_session: AsyncSession
) -> None:
    google_verifier.register("tok", subject="google-sub-1", email="grace@example.com")

    first = await api_client.post(GOOGLE, json={"id_token": "tok"})
    second = await api_client.post(GOOGLE, json={"id_token": "tok"})

    assert first.status_code == second.status_code == 200
    assert first.json()["user"]["id"] == second.json()["user"]["id"]
    count = await db_session.scalar(select(func.count()).select_from(User))
    assert count == 1


async def test_google_identity_is_keyed_on_subject_not_email(
    api_client: AsyncClient, google_verifier, db_session: AsyncSession
) -> None:
    """A user who changes their Google email keeps the same account."""
    google_verifier.register("first", subject="google-sub-1", email="grace@example.com")
    original = await api_client.post(GOOGLE, json={"id_token": "first"})

    google_verifier.register("second", subject="google-sub-1", email="grace.hopper@example.com")
    returning = await api_client.post(GOOGLE, json={"id_token": "second"})

    assert returning.json()["user"]["id"] == original.json()["user"]["id"]
    assert await db_session.scalar(select(func.count()).select_from(User)) == 1


async def test_google_email_colliding_with_a_password_account_is_refused(
    api_client: AsyncClient, google_verifier, db_session: AsyncSession
) -> None:
    """No silent second account, and no silent link either.

    The user must prove they control the existing account by signing in, then
    link Google deliberately.
    """
    await api_client.post(
        SIGNUP, json={"name": "Ada", "email": "ada@example.com", "password": PASSWORD}
    )
    google_verifier.register("tok", subject="google-sub-9", email="ada@example.com")

    response = await api_client.post(GOOGLE, json={"id_token": "tok"})

    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "google_link_required"
    # Exactly one account still exists, and nothing was linked to it.
    assert await db_session.scalar(select(func.count()).select_from(User)) == 1
    assert await db_session.scalar(select(func.count()).select_from(OAuthAccount)) == 0


async def test_unverified_google_email_is_rejected(
    api_client: AsyncClient, google_verifier
) -> None:
    """An unverified address must never be used to identify an account."""
    google_verifier.register(
        "tok", subject="google-sub-1", email="grace@example.com", email_verified=False
    )

    response = await api_client.post(GOOGLE, json={"id_token": "tok"})

    assert response.status_code == 401


async def test_an_unverifiable_token_is_rejected(api_client: AsyncClient) -> None:
    response = await api_client.post(GOOGLE, json={"id_token": "forged-token"})

    assert response.status_code == 401


async def test_google_sign_in_reports_unavailable_when_unconfigured(
    settings: Settings, db_session: AsyncSession
) -> None:
    """With no GOOGLE_CLIENT_ID the endpoint must not pretend to work."""
    from app.db.session import get_db_session

    app: FastAPI = create_app(settings)  # no google_verifier on app.state

    async def _override():
        yield db_session

    app.dependency_overrides[get_db_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(GOOGLE, json={"id_token": "anything"})
    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"


# --------------------------------------------------------------- linking


async def test_linking_google_to_the_signed_in_account(
    api_client: AsyncClient, google_verifier, db_session: AsyncSession
) -> None:
    signup = await api_client.post(
        SIGNUP, json={"name": "Ada", "email": "ada@example.com", "password": PASSWORD}
    )
    token = signup.json()["access_token"]
    google_verifier.register("tok", subject="google-sub-9", email="ada@example.com")

    response = await api_client.post(
        LINK, json={"id_token": "tok"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["linked_providers"] == ["google"]
    assert response.json()["has_password"] is True
    # Still one account, now with one linked identity.
    assert await db_session.scalar(select(func.count()).select_from(User)) == 1
    assert await db_session.scalar(select(func.count()).select_from(OAuthAccount)) == 1


async def test_after_linking_google_sign_in_succeeds(
    api_client: AsyncClient, google_verifier
) -> None:
    """The full recovery path: refused, sign in, link, then Google works."""
    signup = await api_client.post(
        SIGNUP, json={"name": "Ada", "email": "ada@example.com", "password": PASSWORD}
    )
    token = signup.json()["access_token"]
    google_verifier.register("tok", subject="google-sub-9", email="ada@example.com")

    assert (await api_client.post(GOOGLE, json={"id_token": "tok"})).status_code == 409
    await api_client.post(
        LINK, json={"id_token": "tok"}, headers={"Authorization": f"Bearer {token}"}
    )

    response = await api_client.post(GOOGLE, json={"id_token": "tok"})

    assert response.status_code == 200
    assert response.json()["user"]["id"] == signup.json()["user"]["id"]


async def test_linking_requires_authentication(api_client: AsyncClient, google_verifier) -> None:
    google_verifier.register("tok", subject="google-sub-9", email="ada@example.com")

    response = await api_client.post(LINK, json={"id_token": "tok"})

    assert response.status_code == 401


async def test_cannot_link_a_google_account_owned_by_someone_else(
    api_client: AsyncClient, google_verifier, db_session: AsyncSession
) -> None:
    """A provider identity belongs to exactly one user."""
    google_verifier.register("grace-tok", subject="google-sub-1", email="grace@example.com")
    await api_client.post(GOOGLE, json={"id_token": "grace-tok"})

    signup = await api_client.post(
        SIGNUP, json={"name": "Ada", "email": "ada@example.com", "password": PASSWORD}
    )
    token = signup.json()["access_token"]

    response = await api_client.post(
        LINK, json={"id_token": "grace-tok"}, headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 409
    assert await db_session.scalar(select(func.count()).select_from(OAuthAccount)) == 1


async def test_relinking_the_same_google_account_is_idempotent(
    api_client: AsyncClient, google_verifier, db_session: AsyncSession
) -> None:
    signup = await api_client.post(
        SIGNUP, json={"name": "Ada", "email": "ada@example.com", "password": PASSWORD}
    )
    token = signup.json()["access_token"]
    google_verifier.register("tok", subject="google-sub-9", email="ada@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    await api_client.post(LINK, json={"id_token": "tok"}, headers=headers)
    second = await api_client.post(LINK, json={"id_token": "tok"}, headers=headers)

    assert second.status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(OAuthAccount)) == 1
