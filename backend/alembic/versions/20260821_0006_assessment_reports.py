"""Link assessments to the reports they considered

A join table, because an assessment may draw on several reports and a report
stays relevant across later assessments. Unique on (assessment_id, report_id)
so attaching the same report twice is idempotent rather than duplicated.

Attaching a report does not feed its values into the condition model — that
model is trained on symptoms only. Lab results are carried alongside a
prediction as separately-sourced evidence.

Revision ID: 0006_assessment_reports
Revises: 0005_medical_reports
Create Date: 2026-08-21 00:45:50.648551
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_assessment_reports"
down_revision: str | None = "0005_medical_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assessment_reports",
        sa.Column("assessment_id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
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
            name=op.f("fk_assessment_reports_assessment_id_assessments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["report_id"],
            ["medical_reports.id"],
            name=op.f("fk_assessment_reports_report_id_medical_reports"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assessment_reports")),
        sa.UniqueConstraint(
            "assessment_id", "report_id", name=op.f("uq_assessment_reports_assessment_id_report_id")
        ),
    )
    op.create_index(
        op.f("ix_assessment_reports_assessment_id"),
        "assessment_reports",
        ["assessment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_assessment_reports_report_id"), "assessment_reports", ["report_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_assessment_reports_report_id"), table_name="assessment_reports")
    op.drop_index(op.f("ix_assessment_reports_assessment_id"), table_name="assessment_reports")
    op.drop_table("assessment_reports")
