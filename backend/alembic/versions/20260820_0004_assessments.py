"""Add assessments and the intake conversation

Two tables:

* ``assessments``         — one symptom-analysis episode per row, including the
  model name and version that produced its predictions, so a stored result
  stays interpretable after the model changes.
* ``assessment_messages`` — the intake conversation, so an assessment can be
  replayed and audited.

Both cascade from ``users`` and are indexed by the column ownership checks
filter on.

Revision ID: 0004_assessments
Revises: 0003_user_profile
Create Date: 2026-08-20 20:30:59.649617
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004_assessments"
down_revision: str | None = "0003_user_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assessments",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.Enum("in_progress", "completed", name="assessment_status"), nullable=False
        ),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("recognised_symptoms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rejected_symptoms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("unrecognised_terms", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("duration_days", sa.Float(), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("previous_consultation", sa.Boolean(), nullable=True),
        sa.Column("previous_diagnosis", sa.String(length=300), nullable=True),
        sa.Column("previous_medication", sa.String(length=300), nullable=True),
        sa.Column("treatment_response", sa.String(length=40), nullable=True),
        sa.Column("still_taking_medication", sa.Boolean(), nullable=True),
        sa.Column("predictions", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("model_name", sa.String(length=80), nullable=True),
        sa.Column("model_version", sa.String(length=40), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_assessments_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessments")),
    )
    op.create_index(op.f("ix_assessments_status"), "assessments", ["status"], unique=False)
    op.create_index(op.f("ix_assessments_user_id"), "assessments", ["user_id"], unique=False)
    op.create_table(
        "assessment_messages",
        sa.Column("assessment_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.Enum("assistant", "user", name="message_role"), nullable=False),
        sa.Column("question_key", sa.String(length=60), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["assessments.id"],
            name=op.f("fk_assessment_messages_assessment_id_assessments"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_messages")),
    )
    op.create_index(
        op.f("ix_assessment_messages_assessment_id"),
        "assessment_messages",
        ["assessment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_assessment_messages_assessment_id"), table_name="assessment_messages")
    op.drop_table("assessment_messages")
    op.drop_index(op.f("ix_assessments_user_id"), table_name="assessments")
    op.drop_index(op.f("ix_assessments_status"), table_name="assessments")
    op.drop_table("assessments")

    # `drop_table` does not remove the enum types its columns referenced;
    # without this the migration cannot be re-applied.
    for enum_name in ("message_role", "assessment_status"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
