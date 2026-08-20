"""Tests for application wiring (docs exposure, CORS, routing)."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from app.core.config import Environment, Settings
from app.main import create_app


async def test_openapi_docs_available_outside_production(client: AsyncClient) -> None:
    assert (await client.get("/openapi.json")).status_code == 200


async def test_openapi_docs_disabled_in_production() -> None:
    app = create_app(
        Settings(
            environment=Environment.PRODUCTION,
            log_level="WARNING",
            jwt_secret="x" * 64,
        )
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        assert (await ac.get("/openapi.json")).status_code == 404
        assert (await ac.get("/docs")).status_code == 404


async def test_cors_allows_configured_origin(client: AsyncClient) -> None:
    response = await client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_cors_rejects_unconfigured_origin(client: AsyncClient) -> None:
    response = await client.get("/api/health", headers={"Origin": "http://evil.test"})
    assert "access-control-allow-origin" not in response.headers


async def test_routes_are_mounted_under_the_api_prefix(client: AsyncClient) -> None:
    assert (await client.get("/health")).status_code == 404
    assert (await client.get("/api/health")).status_code == 200
