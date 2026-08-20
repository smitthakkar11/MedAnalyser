"""Add users and linked OAuth accounts

Creates the authentication tables:

* ``users``           — account, credentials and date of birth.
* ``oauth_accounts``  — third-party identities linked to a user.

Notes on the constraints:

* ``users.email`` is unique and guarded by a CHECK enforcing lower case, so a
  normalisation bug in application code surfaces as an error rather than as two
  accounts differing only by capitalisation.
* ``uq_oauth_accounts_provider_provider_account_id`` stops two users claiming the
  same provider identity; ``uq_oauth_accounts_user_id_provider`` stops one user
  linking a provider twice.
* Deleting a user cascades to their linked accounts.

Revision ID: 0002_users_and_oauth
Revises: 0001_enable_extensions
Create Date: 2026-08-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_users_and_oauth"
down_revision: str | None = "0001_enable_extensions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.CheckConstraint("email = lower(email)", name="email_lowercase"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "oauth_accounts",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
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
            name=op.f("fk_oauth_accounts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_accounts")),
        sa.UniqueConstraint(
            "provider",
            "provider_account_id",
            name=op.f("uq_oauth_accounts_provider_provider_account_id"),
        ),
        sa.UniqueConstraint("user_id", "provider", name=op.f("uq_oauth_accounts_user_id_provider")),
    )
    op.create_index(op.f("ix_oauth_accounts_user_id"), "oauth_accounts", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_oauth_accounts_user_id"), table_name="oauth_accounts")
    op.drop_table("oauth_accounts")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
