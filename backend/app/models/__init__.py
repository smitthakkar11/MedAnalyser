"""SQLAlchemy ORM models.

Every model module must be imported here so that `Base.metadata` is fully
populated before Alembic autogenerates a migration.
"""

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.profile import (
    Allergy,
    AllergySeverity,
    Condition,
    ConditionStatus,
    Medication,
    SexAtBirth,
    UserProfile,
)
from app.models.user import OAuthAccount, User

__all__ = [
    "Allergy",
    "AllergySeverity",
    "Base",
    "Condition",
    "ConditionStatus",
    "Medication",
    "OAuthAccount",
    "SexAtBirth",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "User",
    "UserProfile",
]
