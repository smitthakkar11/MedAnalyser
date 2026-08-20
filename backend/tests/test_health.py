"""Tests for the liveness and readiness endpoints."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app import __version__
from app.db.session import get_db_session
from app.schemas.health import ComponentStatus


async def test_health_reports_ok(client: AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == ComponentStatus.OK
    assert body["app"] == "MedAnalyser"
    assert body["version"] == __version__
    assert body["environment"] == "test"


async def test_health_does_not_touch_the_database(client: AsyncClient) -> None:
    """Liveness must stay green even with no database configured."""
    response = await client.get("/api/health")
    assert response.status_code == 200


async def test_health_sets_request_id_header(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.headers["X-Request-ID"]


async def test_health_echoes_supplied_request_id(client: AsyncClient) -> None:
    response = await client.get("/api/health", headers={"X-Request-ID": "abc-123"})
    assert response.headers["X-Request-ID"] == "abc-123"


async def test_health_sets_security_headers(client: AsyncClient) -> None:
    response = await client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


async def test_readiness_reports_unavailable_without_database(
    client: AsyncClient, override_db: list[object]
) -> None:
    response = await client.get("/api/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == ComponentStatus.UNAVAILABLE
    database = next(dep for dep in body["dependencies"] if dep["name"] == "database")
    assert database["status"] == ComponentStatus.UNAVAILABLE
    # The failure reason must not leak connection details.
    assert "test:test@" not in database["detail"]


@pytest.mark.parametrize(
    ("installed_extensions", "expected_status", "expected_code"),
    [
        (["vector"], ComponentStatus.OK, 200),
        ([], ComponentStatus.DEGRADED, 200),
    ],
)
async def test_readiness_reflects_extension_state(
    app: FastAPI,
    installed_extensions: list[str],
    expected_status: ComponentStatus,
    expected_code: int,
) -> None:
    """A reachable database missing pgvector is degraded, not ok."""

    class _FakeResult:
        def __init__(self, rows: list[str]) -> None:
            self._rows = rows

        def __iter__(self) -> object:
            return iter([(row,) for row in self._rows])

    class _FakeSession:
        async def execute(self, statement: object) -> object:
            if "pg_extension" in str(statement):
                return _FakeResult(installed_extensions)
            return _FakeResult([])

    async def _override() -> AsyncIterator[object]:
        yield _FakeSession()

    app.dependency_overrides[get_db_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        response = await ac.get("/api/health/ready")
    app.dependency_overrides.clear()

    assert response.status_code == expected_code
    assert response.json()["status"] == expected_status


async def test_unknown_route_returns_error_envelope(client: AsyncClient) -> None:
    response = await client.get("/api/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "http_404"
    assert "request_id" in body["error"]
