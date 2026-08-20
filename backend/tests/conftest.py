"""Shared pytest fixtures.

Two flavours of test are supported:

* **Unit tests** need no database. They use `app` / `client`, whose database
  dependency is either unused or stubbed.
* **Integration tests** exercise real SQL. They use `db_session` /
  `api_client`, which run against a dedicated test database. Every test runs
  inside a transaction that is rolled back afterwards, so tests never see each
  other's rows and the database needs no cleanup between runs.

The test database is created automatically. If PostgreSQL is unreachable the
integration tests skip with an explanatory message rather than erroring.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import Environment, Settings
from app.db.session import get_db_session
from app.main import create_app
from app.models import Base
from tests.fakes import FakeGoogleVerifier

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://medanalyser:medanalyser@localhost:5432/medanalyser_test",
)
_ADMIN_DATABASE_URL = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
_TEST_DATABASE_NAME = TEST_DATABASE_URL.rsplit("/", 1)[1]

#: Set by the session fixture; integration fixtures skip when it is not None.
_database_unavailable: str | None = None


async def _provision_database() -> None:
    """Create the test database, its extensions and the current schema."""
    admin_engine = create_async_engine(
        _ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    try:
        async with admin_engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": _TEST_DATABASE_NAME},
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{_TEST_DATABASE_NAME}"'))
    finally:
        await admin_engine.dispose()

    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            # Mirrors migration 0001; the schema itself is created from the
            # models, with `alembic check` guarding against drift.
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "vector"'))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database_schema() -> Iterator[None]:
    """Provision the test database once per session."""
    global _database_unavailable
    try:
        asyncio.run(_provision_database())
    except Exception as exc:  # noqa: BLE001 - reported as a skip, not an error
        _database_unavailable = (
            f"PostgreSQL is not reachable at {TEST_DATABASE_URL.rsplit('@', 1)[-1]} "
            f"({type(exc).__name__}). Start it to run the integration tests."
        )
    yield


# --------------------------------------------------------------------- unit


@pytest.fixture
def settings() -> Settings:
    """Settings for tests, isolated from any developer `.env` values."""
    return Settings(
        environment=Environment.TEST,
        debug=True,
        log_level="WARNING",
        database_url=TEST_DATABASE_URL,
        cors_origins=["http://localhost:5173"],
        jwt_secret="test-secret-not-used-outside-the-test-suite",
        access_token_expire_minutes=30,
        refresh_token_expire_days=14,
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


# -------------------------------------------------------------- integration


@pytest.fixture
async def db_connection() -> AsyncIterator[AsyncConnection]:
    """A connection wrapped in a transaction that is always rolled back."""
    if _database_unavailable:
        pytest.skip(_database_unavailable)

    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()
    await engine.dispose()


@pytest.fixture
async def db_session(db_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """A session bound to the rolled-back connection.

    `join_transaction_mode="create_savepoint"` means the service layer's own
    `commit()` calls become savepoint releases inside the outer transaction, so
    production code paths run unchanged while the test still rolls everything
    back.
    """
    factory = async_sessionmaker(
        bind=db_connection,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    async with factory() as session:
        yield session


@pytest.fixture
def google_verifier() -> FakeGoogleVerifier:
    """A stub Google verifier; tests register the identities they need."""
    return FakeGoogleVerifier()


@pytest.fixture
def api_app(
    settings: Settings,
    db_session: AsyncSession,
    google_verifier: FakeGoogleVerifier,
) -> Iterator[FastAPI]:
    """An app wired to the test database and a stub Google verifier."""
    application = create_app(settings)
    application.state.google_verifier = google_verifier

    async def _override() -> AsyncIterator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_db_session] = _override
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def api_client(api_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """HTTP client backed by the real test database."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
