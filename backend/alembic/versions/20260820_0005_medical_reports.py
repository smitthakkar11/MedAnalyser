"""Add medical reports and extracted values

Two tables:

* ``medical_reports`` — the uploaded document, its storage handle, and how its
  text was obtained (native text layer or OCR).
* ``report_values``   — one row per laboratory result read off the page.

``report_values.user_id`` is denormalised from the parent report so the medical
timeline can query a user's values across reports without a join, and so every
ownership filter in the codebase looks the same.

Reference ranges are stored only when the report printed them; this schema
holds no normal ranges of its own, because they vary by laboratory and assay.

Revision ID: 0005_medical_reports
Revises: 0004_assessments
Create Date: 2026-08-20 23:36:45.659676
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_medical_reports"
down_revision: str | None = "0004_assessments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "medical_reports",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "processed", "failed", name="report_status"),
            nullable=False,
        ),
        sa.Column(
            "extraction_method",
            sa.Enum("text_layer", "ocr", "mixed", "none", name="extraction_method"),
            nullable=True,
        ),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("error_message", sa.String(length=300), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
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
            ["user_id"],
            ["users.id"],
            name=op.f("fk_medical_reports_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_medical_reports")),
    )
    op.create_index(
        op.f("ix_medical_reports_checksum"), "medical_reports", ["checksum"], unique=False
    )
    op.create_index(op.f("ix_medical_reports_status"), "medical_reports", ["status"], unique=False)
    op.create_index(
        op.f("ix_medical_reports_user_id"), "medical_reports", ["user_id"], unique=False
    )
    op.create_table(
        "report_values",
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("analyte", sa.String(length=60), nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("reference_low", sa.Float(), nullable=True),
        sa.Column("reference_high", sa.Float(), nullable=True),
        sa.Column("reference_text", sa.String(length=80), nullable=True),
        sa.Column(
            "flag", sa.Enum("normal", "low", "high", "unknown", name="value_flag"), nullable=False
        ),
        sa.Column("unit_unrecognised", sa.Boolean(), nullable=False),
        sa.Column("source_line", sa.String(length=200), nullable=True),
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
            ["report_id"],
            ["medical_reports.id"],
            name=op.f("fk_report_values_report_id_medical_reports"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_report_values_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_report_values")),
    )
    op.create_index(op.f("ix_report_values_analyte"), "report_values", ["analyte"], unique=False)
    op.create_index(
        op.f("ix_report_values_report_id"), "report_values", ["report_id"], unique=False
    )
    op.create_index(op.f("ix_report_values_user_id"), "report_values", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_report_values_user_id"), table_name="report_values")
    op.drop_index(op.f("ix_report_values_report_id"), table_name="report_values")
    op.drop_index(op.f("ix_report_values_analyte"), table_name="report_values")
    op.drop_table("report_values")
    op.drop_index(op.f("ix_medical_reports_user_id"), table_name="medical_reports")
    op.drop_index(op.f("ix_medical_reports_status"), table_name="medical_reports")
    op.drop_index(op.f("ix_medical_reports_checksum"), table_name="medical_reports")
    op.drop_table("medical_reports")

    # `drop_table` leaves the enum types behind, so without this the migration
    # cannot be re-applied.
    for enum_name in ("value_flag", "extraction_method", "report_status"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
