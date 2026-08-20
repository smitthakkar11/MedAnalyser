"""Shared pytest fixtures.

Phase 1 tests run without a live database: the readiness route's session
dependency is overridden where a database is not the thing under test.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Environment, Settings
from app.db.session import get_db_session
from app.main import create_app


@pytest.fixture
def settings() -> Settings:
    """Settings for tests, isolated from any developer `.env` values."""
    return Settings(
        environment=Environment.TEST,
        debug=True,
        log_level="WARNING",
        database_url="postgresql+asyncpg://test:test@localhost:5432/test",
        cors_origins=["http://localhost:5173"],
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """HTTP client that talks to the ASGI app in-process (no network, no port)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def override_db(app: FastAPI) -> Iterator[list[object]]:
    """Replace the DB session dependency with a stub.

    Yields the list of stub sessions handed out, so a test can assert on usage.
    """
    handed_out: list[object] = []

    class _StubSession:
        async def execute(self, *_args: object, **_kwargs: object) -> object:
            raise RuntimeError("stub session: no database configured")

    async def _override() -> AsyncIterator[object]:
        session = _StubSession()
        handed_out.append(session)
        yield session

    app.dependency_overrides[get_db_session] = _override
    yield handed_out
    app.dependency_overrides.clear()
