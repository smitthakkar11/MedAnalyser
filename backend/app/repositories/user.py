"""Data access for users and their linked OAuth accounts.

All query construction lives here. Services never build queries themselves, so
lookup semantics (notably email normalisation) exist in exactly one place.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import OAuthAccount, User


class UserRepository:
    """Reads and writes for the `users` and `oauth_accounts` tables."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        """Look up a user by email, normalising case the same way writes do."""
        result = await self._session.execute(
            select(User).where(User.email == email.strip().lower())
        )
        return result.scalar_one_or_none()

    async def get_by_oauth_account(self, provider: str, provider_account_id: str) -> User | None:
        """Return the user who owns a provider identity, if any."""
        result = await self._session.execute(
            select(User)
            .join(OAuthAccount)
            .where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_account_id == provider_account_id,
            )
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        result = await self._session.execute(
            select(User.id).where(User.email == email.strip().lower())
        )
        return result.first() is not None

    def add(self, user: User) -> User:
        """Stage a new user. The caller commits."""
        self._session.add(user)
        return user

    def add_oauth_account(self, account: OAuthAccount) -> OAuthAccount:
        """Stage a new linked provider identity. The caller commits."""
        self._session.add(account)
        return account

    async def linked_providers(self, user_id: uuid.UUID) -> list[str]:
        result = await self._session.execute(
            select(OAuthAccount.provider)
            .where(OAuthAccount.user_id == user_id)
            .order_by(OAuthAccount.provider)
        )
        return list(result.scalars().all())
