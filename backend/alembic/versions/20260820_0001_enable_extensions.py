"""Enable required PostgreSQL extensions

Creates the extensions the application depends on before any table exists:

* ``vector``    — pgvector, used by the RAG knowledge base (Phase 6).
* ``pgcrypto``  — provides ``gen_random_uuid()`` for server-side UUID primary
                  keys. (Built in from PG13, but declaring it keeps the schema
                  explicit and portable.)

Revision ID: 0001_enable_extensions
Revises:
Create Date: 2026-08-20
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_enable_extensions"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXTENSIONS = ("vector", "pgcrypto")


def upgrade() -> None:
    for extension in EXTENSIONS:
        op.execute(f'CREATE EXTENSION IF NOT EXISTS "{extension}"')


def downgrade() -> None:
    # Extensions are dropped in reverse order. `DROP EXTENSION` fails if objects
    # still depend on it, which is the desired safety behaviour.
    for extension in reversed(EXTENSIONS):
        op.execute(f'DROP EXTENSION IF EXISTS "{extension}"')
