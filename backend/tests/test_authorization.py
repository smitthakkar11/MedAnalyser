"""Authorization: cross-user isolation and the onboarding gate.

MedAnalyser holds medical data, so the rule these tests defend is absolute:
one user's token must never reach another user's information, and the frontend
is never trusted to enforce it.
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, OnboardedUser
from app.core.config import Settings
from app.db.session import get_db_session
from app.main import create_app

SIGNUP = "/api/auth/signup"
PASSWORD = "a-strong-passphrase"


async def _register(client: AsyncClient, name: str, email: str) -> dict:
    response = await client.post(SIGNUP, json={"name": name, "email": email, "password": PASSWORD})
    assert response.status_code == 201
    return response.json()


async def test_each_token_resolves_only_to_its_own_user(api_client: AsyncClient) -> None:
    ada = await _register(api_client, "Ada", "ada@example.com")
    grace = await _register(api_client, "Grace", "grace@example.com")

    ada_me = await api_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {ada['access_token']}"}
    )
    grace_me = await api_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {grace['access_token']}"}
    )

    assert ada_me.json()["email"] == "ada@example.com"
    assert grace_me.json()["email"] == "grace@example.com"
    assert ada_me.json()["id"] != grace_me.json()["id"]


async def test_one_users_token_cannot_act_as_another(api_client: AsyncClient) -> None:
    """Linking with Ada's token must affect Ada, never Grace."""
    ada = await _register(api_client, "Ada", "ada@example.com")
    grace = await _register(api_client, "Grace", "grace@example.com")

    response = await api_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {ada['access_token']}"}
    )

    assert response.json()["id"] == ada["user"]["id"]
    assert response.json()["id"] != grace["user"]["id"]


async def test_logging_out_one_user_does_not_affect_another(
    api_client: AsyncClient,
) -> None:
    ada = await _register(api_client, "Ada", "ada@example.com")
    grace = await _register(api_client, "Grace", "grace@example.com")

    await api_client.post(
        "/api/auth/logout", headers={"Authorization": f"Bearer {ada['access_token']}"}
    )

    still_valid = await api_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {grace['access_token']}"}
    )
    assert still_valid.status_code == 200


def _app_with_protected_routes(settings: Settings, db_session: AsyncSession) -> FastAPI:
    """An app exposing routes that use each auth dependency.

    Phase 2 has no user-owned medical resources yet, so the guards are exercised
    directly here; from Phase 3 onwards real resources depend on them.
    """
    app = create_app(settings)
    router = APIRouter()

    @router.get("/api/_test/authenticated")
    async def authenticated(user: CurrentUser) -> dict[str, str]:
        return {"user_id": str(user.id)}

    @router.get("/api/_test/onboarded")
    async def onboarded(user: OnboardedUser) -> dict[str, str]:
        return {"user_id": str(user.id)}

    app.include_router(router)

    async def _override():
        yield db_session

    app.dependency_overrides[get_db_session] = _override
    return app


async def test_protected_route_rejects_anonymous_callers(
    settings: Settings, db_session: AsyncSession
) -> None:
    app = _app_with_protected_routes(settings, db_session)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/_test/authenticated")

    assert response.status_code == 401


async def test_protected_route_accepts_a_valid_token(
    settings: Settings, db_session: AsyncSession
) -> None:
    app = _app_with_protected_routes(settings, db_session)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        signup = await _register(client, "Ada", "ada@example.com")
        response = await client.get(
            "/api/_test/authenticated",
            headers={"Authorization": f"Bearer {signup['access_token']}"},
        )

    assert response.status_code == 200
    assert response.json()["user_id"] == signup["user"]["id"]


async def test_onboarding_gate_blocks_users_without_a_verified_age(
    settings: Settings, db_session: AsyncSession
) -> None:
    """Signed in but not onboarded must not reach an age-restricted resource."""
    app = _app_with_protected_routes(settings, db_session)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        signup = await _register(client, "Ada", "ada@example.com")
        headers = {"Authorization": f"Bearer {signup['access_token']}"}

        blocked = await client.get("/api/_test/onboarded", headers=headers)
        assert blocked.status_code == 403
        assert blocked.json()["error"]["code"] == "onboarding_required"

        await client.post(
            "/api/auth/onboarding", json={"date_of_birth": "1990-05-04"}, headers=headers
        )
        allowed = await client.get("/api/_test/onboarded", headers=headers)

    assert allowed.status_code == 200
