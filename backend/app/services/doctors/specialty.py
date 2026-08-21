"""Recommend which kind of doctor to see.

    predicted conditions ─┐
    reported symptoms  ───┼──▶ transparent lookup ──▶ suggested specialty
    red-flag outcome   ───┘

Why a lookup rather than a model: the relationship between this project's 41
conditions and a specialty is one-to-one and already known. A classifier
trained on 41 rows of a deterministic mapping would memorise it, score
perfectly, and demonstrate nothing. The brief rules that out by name.

The red-flag outcome is an input, not an afterthought. Telling someone with
crushing chest pain to book a cardiologist would be actively dangerous: they
need emergency care today, not an outpatient appointment in three weeks.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.services.safety import SafetyLevel

MAPPING_FILE = Path(__file__).parent / "data" / "specialty_mapping.json"

#: How confident the recommendation is. Not a probability — a description of
#: what it was derived from.
BASIS_CONDITION = "condition"
BASIS_SYMPTOM = "symptom"
BASIS_DEFAULT = "default"
BASIS_EMERGENCY = "emergency"


@dataclass(frozen=True)
class SpecialtyRecommendation:
    """A suggested specialty and how it was arrived at."""

    specialty: str
    display_name: str
    description: str
    #: What the suggestion was derived from: a predicted condition, a reported
    #: symptom, the default, or an overriding red flag.
    basis: str
    #: Plain-language explanation shown to the user.
    reason: str
    #: True when a red flag overrode the normal recommendation.
    overridden_by_safety: bool = False


@dataclass(frozen=True)
class _Specialty:
    key: str
    display: str
    description: str


class DoctorSpecialtyService:
    """Maps a prediction to the kind of doctor worth seeing."""

    def __init__(self, mapping: dict | None = None) -> None:
        payload = mapping if mapping is not None else json.loads(MAPPING_FILE.read_text())
        self._specialties = {
            key: _Specialty(key=key, display=entry["display"], description=entry["description"])
            for key, entry in payload["specialties"].items()
        }
        self._conditions: dict[str, str] = {
            condition: entry["specialty"] for condition, entry in payload["conditions"].items()
        }
        self._divergences: dict[str, str] = {
            condition: entry["diverges"]
            for condition, entry in payload["conditions"].items()
            if "diverges" in entry
        }
        self._symptom_fallback: dict[str, str] = {
            symptom: specialty
            for symptom, specialty in payload["symptom_fallback"].items()
            if not symptom.startswith("_")
        }
        self._default = payload["default_specialty"]
        self._validate()

    def _validate(self) -> None:
        """Fail at load rather than silently recommending nothing."""
        unknown = {
            specialty
            for specialty in (
                *self._conditions.values(),
                *self._symptom_fallback.values(),
                self._default,
            )
            if specialty not in self._specialties
        }
        if unknown:
            raise ValueError(f"Mapping references unknown specialties: {sorted(unknown)}")

    @property
    def specialties(self) -> list[str]:
        return sorted(self._specialties)

    def describe(self, key: str) -> str:
        """The description for a specialty key, or empty if unknown."""
        specialty = self._specialties.get(key)
        return specialty.description if specialty else ""

    def divergence_note(self, condition: str) -> str | None:
        """Why this project's mapping differs from its source, if it does."""
        return self._divergences.get(_normalise(condition))

    def recommend(
        self,
        *,
        conditions: list[str] | None = None,
        symptoms: list[str] | None = None,
        safety_level: SafetyLevel | str = SafetyLevel.NONE,
    ) -> SpecialtyRecommendation:
        """Suggest a specialty.

        Order of precedence:

        1. **A red flag overrides everything.** An emergency needs emergency
           care, not a referral.
        2. The highest-ranked predicted condition, if it maps to one.
        3. A reported symptom, which points at a body system rather than a
           diagnosis.
        4. General Physician — the honest answer when nothing is clear.
        """
        level = safety_level if isinstance(safety_level, SafetyLevel) else SafetyLevel(safety_level)

        if level is SafetyLevel.EMERGENCY:
            specialty = self._specialties[self._default]
            return SpecialtyRecommendation(
                specialty=specialty.key,
                display_name="Emergency care",
                description="Immediate assessment, not a scheduled appointment.",
                basis=BASIS_EMERGENCY,
                reason=(
                    "Because of the warning above, this needs emergency assessment now "
                    "rather than an appointment with a specialist."
                ),
                overridden_by_safety=True,
            )

        for condition in conditions or []:
            key = self._conditions.get(_normalise(condition))
            if key:
                specialty = self._specialties[key]
                return SpecialtyRecommendation(
                    specialty=specialty.key,
                    display_name=specialty.display,
                    description=specialty.description,
                    basis=BASIS_CONDITION,
                    reason=(
                        f"Based on the information provided, {specialty.display} may be an "
                        f"appropriate specialty for further evaluation of a possible "
                        f"{condition}."
                    ),
                )

        for symptom in symptoms or []:
            key = self._symptom_fallback.get(symptom)
            if key:
                specialty = self._specialties[key]
                return SpecialtyRecommendation(
                    specialty=specialty.key,
                    display_name=specialty.display,
                    description=specialty.description,
                    basis=BASIS_SYMPTOM,
                    reason=(
                        f"No condition could be identified confidently, but "
                        f"{_humanise(symptom)} points towards {specialty.display}."
                    ),
                )

        specialty = self._specialties[self._default]
        return SpecialtyRecommendation(
            specialty=specialty.key,
            display_name=specialty.display,
            description=specialty.description,
            basis=BASIS_DEFAULT,
            reason=(
                "There is not enough here to point to a particular specialty. A "
                "General Physician can assess and refer you onwards if needed."
            ),
        )


def _normalise(condition: str) -> str:
    """Fold the double spaces the source data contains."""
    return " ".join(condition.split())


def _humanise(symptom: str) -> str:
    return symptom.replace("_", " ")


@lru_cache(maxsize=1)
def get_specialty_service() -> DoctorSpecialtyService:
    return DoctorSpecialtyService()
