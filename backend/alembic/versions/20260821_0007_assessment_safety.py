"""Record the red-flag outcome on each assessment

`safety_level` and `safety_flags` are produced by the deterministic red-flag
engine, never by the model. They are stored so a completed assessment is a
record of what the user was actually warned about at the time — the rules may
change later, and an old assessment should still show what it showed.

Defaults to "none" so existing rows are valid without a backfill.

Revision ID: 0007_assessment_safety
Revises: 0006_assessment_reports
Create Date: 2026-08-21 12:00:50.340683
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_assessment_safety"
down_revision: str | None = "0006_assessment_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assessments",
        sa.Column("safety_level", sa.String(length=20), server_default="none", nullable=False),
    )
    op.add_column(
        "assessments",
        sa.Column("safety_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assessments", "safety_flags")
    op.drop_column("assessments", "safety_level")
