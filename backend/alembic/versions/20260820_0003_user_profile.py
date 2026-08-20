"""Add user profile tables

Creates the standing medical profile and its three user-owned collections:

* ``user_profiles``  — scalar fields, exactly one row per user (unique index).
* ``allergies``      — substances the user reacts to.
* ``conditions``     — existing conditions, as reported by the user.
* ``medications``    — what they take, recorded verbatim.

Every table cascades on user deletion and is indexed by ``user_id``, which is
the column each ownership check filters on. Date of birth is not duplicated
here: it lives on ``users`` so age verification has one source of truth.

Revision ID: 0003_user_profile
Revises: 0002_users_and_oauth
Create Date: 2026-08-20 18:36:21.583812
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_user_profile"
down_revision: str | None = "0002_users_and_oauth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "allergies",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("substance", sa.String(length=120), nullable=False),
        sa.Column("reaction", sa.String(length=200), nullable=True),
        sa.Column(
            "severity",
            sa.Enum("mild", "moderate", "severe", "unknown", name="allergy_severity"),
            nullable=False,
        ),
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
            ["user_id"], ["users.id"], name=op.f("fk_allergies_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_allergies")),
    )
    op.create_index(op.f("ix_allergies_user_id"), "allergies", ["user_id"], unique=False)
    op.create_table(
        "conditions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "managed", "resolved", name="condition_status"),
            nullable=False,
        ),
        sa.Column("diagnosed_year", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
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
            ["user_id"], ["users.id"], name=op.f("fk_conditions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conditions")),
    )
    op.create_index(op.f("ix_conditions_user_id"), "conditions", ["user_id"], unique=False)
    op.create_table(
        "medications",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("dosage", sa.String(length=80), nullable=True),
        sa.Column("frequency", sa.String(length=80), nullable=True),
        sa.Column("started_on", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.String(length=500), nullable=True),
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
            ["user_id"], ["users.id"], name=op.f("fk_medications_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_medications")),
    )
    op.create_index(op.f("ix_medications_user_id"), "medications", ["user_id"], unique=False)
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "sex_at_birth",
            sa.Enum("female", "male", "intersex", "prefer_not_to_say", name="sex_at_birth"),
            nullable=True,
        ),
        sa.Column("gender_identity", sa.String(length=80), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("emergency_contact_name", sa.String(length=120), nullable=True),
        sa.Column("emergency_contact_relationship", sa.String(length=60), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(length=40), nullable=True),
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
            name=op.f("fk_user_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_profiles")),
    )
    op.create_index(op.f("ix_user_profiles_user_id"), "user_profiles", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_profiles_user_id"), table_name="user_profiles")
    op.drop_table("user_profiles")
    op.drop_index(op.f("ix_medications_user_id"), table_name="medications")
    op.drop_table("medications")
    op.drop_index(op.f("ix_conditions_user_id"), table_name="conditions")
    op.drop_table("conditions")
    op.drop_index(op.f("ix_allergies_user_id"), table_name="allergies")
    op.drop_table("allergies")

    # `drop_table` does not remove the enum types the columns referenced, so
    # without this the migration cannot be re-applied: CREATE TYPE fails with
    # "type already exists".
    for enum_name in ("sex_at_birth", "condition_status", "allergy_severity"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
