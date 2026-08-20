"""User and linked OAuth account models."""

from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An application user.

    A user may authenticate with a password, with a linked OAuth provider, or
    both — hence ``password_hash`` is nullable. ``date_of_birth`` is nullable
    because it is collected during onboarding, which happens after the account
    exists (OAuth providers are not a trustworthy source for it).
    """

    __tablename__ = "users"
    __table_args__ = (
        # Defence in depth: normalisation happens in the schema layer, and the
        # database refuses anything that slipped through.
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)

    #: Stored lower-cased and unique. Normalisation happens in the schema layer
    #: so that lookups and the unique constraint always agree.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)

    #: Argon2id hash. NULL for accounts that only sign in through a provider.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    #: Incremented to invalidate every outstanding refresh token for this user
    #: (logout-everywhere, password change, suspected compromise).
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    oauth_accounts: Mapped[list[OAuthAccount]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None

    @property
    def onboarding_complete(self) -> bool:
        """Onboarding is complete once a date of birth has been recorded.

        A stored date of birth always satisfies the age requirement: the check
        runs before it is persisted and it can never be edited to a failing value.
        """
        return self.date_of_birth is not None


class OAuthAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A third-party identity linked to a :class:`User`.

    ``provider_account_id`` is the provider's stable subject identifier — for
    Google, the ``sub`` claim of a verified ID token. Email is deliberately not
    stored here: it can change at the provider, whereas the subject cannot.
    """

    __tablename__ = "oauth_accounts"
    __table_args__ = (
        # One account per provider identity: prevents two users claiming the
        # same Google account.
        UniqueConstraint("provider", "provider_account_id"),
        # A user links at most one account per provider.
        UniqueConstraint("user_id", "provider"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)

    user: Mapped[User] = relationship(back_populates="oauth_accounts")
