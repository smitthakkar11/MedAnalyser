"""Doctor specialty recommendation and, from Phase 11, doctor discovery.

Deliberately not under `services/ml/`: this is a transparent lookup, not a
model, and filing it beside the classifier would imply otherwise.
"""

from app.services.doctors.specialty import (
    DoctorSpecialtyService,
    SpecialtyRecommendation,
    get_specialty_service,
)

__all__ = [
    "DoctorSpecialtyService",
    "SpecialtyRecommendation",
    "get_specialty_service",
]
