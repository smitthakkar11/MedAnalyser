"""Record the specialty recommendation on each assessment

Stored rather than recomputed so a completed assessment keeps showing what the
user was actually told, even after the mapping is corrected. `specialty_basis`
records whether the suggestion came from a predicted condition, a symptom, the
default, or a red flag overriding all of them.

All nullable: assessments created before this migration simply have none.

Revision ID: 0008_specialty
Revises: 0007_assessment_safety
Create Date: 2026-08-21 12:22:33.286716
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_specialty"
down_revision: str | None = "0007_assessment_safety"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "assessments", sa.Column("recommended_specialty", sa.String(length=60), nullable=True)
    )
    op.add_column(
        "assessments", sa.Column("specialty_display", sa.String(length=80), nullable=True)
    )
    op.add_column(
        "assessments", sa.Column("specialty_reason", sa.String(length=400), nullable=True)
    )
    op.add_column("assessments", sa.Column("specialty_basis", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("assessments", "specialty_basis")
    op.drop_column("assessments", "specialty_reason")
    op.drop_column("assessments", "specialty_display")
    op.drop_column("assessments", "recommended_specialty")
