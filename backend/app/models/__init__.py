"""SQLAlchemy ORM models.

Every model module must be imported here so that `Base.metadata` is fully
populated before Alembic autogenerates a migration.
"""

from app.db.base import Base
from app.models.assessment import (
    Assessment,
    AssessmentMessage,
    AssessmentStatus,
    MessageRole,
)
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
from app.models.report import (
    ExtractionMethod,
    MedicalReport,
    ReportStatus,
    ReportValue,
    ValueFlag,
)
from app.models.user import OAuthAccount, User

__all__ = [
    "Allergy",
    "Assessment",
    "AssessmentMessage",
    "AssessmentStatus",
    "AllergySeverity",
    "Base",
    "Condition",
    "ConditionStatus",
    "ExtractionMethod",
    "MedicalReport",
    "Medication",
    "MessageRole",
    "OAuthAccount",
    "ReportStatus",
    "ReportValue",
    "SexAtBirth",
    "TimestampMixin",
    "UUIDPrimaryKeyMixin",
    "User",
    "UserProfile",
    "ValueFlag",
]
