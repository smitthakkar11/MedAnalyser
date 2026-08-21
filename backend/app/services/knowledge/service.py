"""Look up treatment and medication information for a predicted condition."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
CONDITIONS_FILE = DATA_DIR / "condition_knowledge.json"
CLASSES_FILE = DATA_DIR / "medication_classes.json"

#: Shown with every piece of medication information, without exception.
PRESCRIPTION_DISCLAIMER = (
    "This information is educational and is not a prescription. Consult a "
    "qualified healthcare professional before taking, stopping, or changing "
    "any medication."
)


@dataclass(frozen=True)
class MedicationInfo:
    """What a class of medicine is for, and what to ask about it.

    A class, never a product with a dose. `allergy_warning` is set when the
    user's own profile lists something in this class.
    """

    key: str
    display_name: str
    common_uses: str
    considerations: str
    source: str
    source_url: str
    allergy_warning: str | None = None

    @property
    def conflicts_with_allergy(self) -> bool:
        return self.allergy_warning is not None


@dataclass
class ConditionKnowledge:
    """Everything the knowledge base holds about one condition."""

    condition: str
    summary: str = ""
    summary_source: str | None = None
    summary_source_url: str | None = None
    approaches: list[str] = field(default_factory=list)
    medications: list[MedicationInfo] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    disclaimer: str = PRESCRIPTION_DISCLAIMER

    @property
    def is_empty(self) -> bool:
        return not (self.summary or self.approaches or self.medications)

    @property
    def allergy_conflicts(self) -> list[MedicationInfo]:
        return [medicine for medicine in self.medications if medicine.conflicts_with_allergy]


class KnowledgeService:
    """Serves curated information for a predicted condition."""

    def __init__(self, conditions: dict | None = None, classes: dict | None = None) -> None:
        self._conditions = (
            conditions
            if conditions is not None
            else json.loads(CONDITIONS_FILE.read_text())["conditions"]
        )
        self._classes = (
            classes if classes is not None else json.loads(CLASSES_FILE.read_text())["classes"]
        )
        self._validate()

    def _validate(self) -> None:
        """Fail at load rather than silently omitting information."""
        unknown = {
            key
            for entry in self._conditions.values()
            for key in entry.get("medication_classes", [])
            if key not in self._classes
        }
        if unknown:
            raise ValueError(
                f"Knowledge base references unknown medication classes: {sorted(unknown)}"
            )

    @property
    def known_conditions(self) -> list[str]:
        return sorted(self._conditions)

    def for_condition(
        self, condition: str, *, allergies: list[str] | None = None
    ) -> ConditionKnowledge | None:
        """Information for *condition*, or None when it is not in the base.

        Returning None rather than a generic filler is deliberate: showing
        plausible-looking treatment text for a condition nothing is known about
        would be worse than showing nothing.
        """
        entry = self._conditions.get(_normalise(condition))
        if entry is None:
            return None

        return ConditionKnowledge(
            condition=condition,
            summary=entry.get("summary", ""),
            summary_source=entry.get("summary_source"),
            summary_source_url=entry.get("summary_source_url"),
            approaches=list(entry.get("approaches", [])),
            medications=[
                self._medication(key, allergies or [])
                for key in entry.get("medication_classes", [])
            ],
            questions=list(entry.get("questions", [])),
        )

    def _medication(self, key: str, allergies: list[str]) -> MedicationInfo:
        entry = self._classes[key]
        return MedicationInfo(
            key=key,
            display_name=entry["display"],
            common_uses=entry["common_uses"],
            considerations=entry["considerations"],
            source=entry["source"],
            source_url=entry["source_url"],
            allergy_warning=_allergy_warning(entry, allergies),
        )


def _allergy_warning(entry: dict, allergies: list[str]) -> str | None:
    """Flag a class the user has recorded an allergy to.

    Substring matching in both directions, deliberately loose: "penicillin" on a
    profile should match an "amoxicillin (penicillin family)" keyword and vice
    versa. Over-warning is the safe direction — a spurious flag prompts a
    conversation, a missed one does not.
    """
    keywords = [keyword.lower() for keyword in entry.get("allergy_keywords", [])]
    if not keywords:
        return None

    matched = sorted(
        {
            allergy.strip()
            for allergy in allergies
            if allergy
            and any(
                keyword in allergy.lower() or allergy.lower() in keyword for keyword in keywords
            )
        }
    )
    if not matched:
        return None

    listed = ", ".join(matched)
    return (
        f"Your profile records an allergy to {listed}, which may relate to this "
        f"group of medicines. Make sure your doctor knows before anything is prescribed."
    )


def _normalise(condition: str) -> str:
    """Fold the double spaces the source data contains."""
    return " ".join(condition.split())


@lru_cache(maxsize=1)
def get_knowledge_service() -> KnowledgeService:
    return KnowledgeService()
