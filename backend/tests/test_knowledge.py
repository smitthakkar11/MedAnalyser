"""Treatment and medication knowledge.

The rules this must never break: no doses, and no telling anyone to start, stop
or change a medicine. Several tests below scan the shipped content rather than
a fixture, so adding an unsafe entry later fails the build.
"""

from __future__ import annotations

import json
import re

import pytest

from app.services.knowledge import KnowledgeService, get_knowledge_service
from app.services.knowledge.service import (
    CLASSES_FILE,
    CONDITIONS_FILE,
    PRESCRIPTION_DISCLAIMER,
)


@pytest.fixture(scope="module")
def service() -> KnowledgeService:
    return get_knowledge_service()


# ------------------------------------------------------------------ lookup


def test_a_known_condition_returns_information(service: KnowledgeService) -> None:
    entry = service.for_condition("Fungal infection")

    assert entry is not None
    assert entry.summary
    assert entry.approaches
    assert entry.medications
    assert entry.questions


def test_an_unknown_condition_returns_nothing(service: KnowledgeService) -> None:
    """Better to show nothing than plausible-looking filler."""
    assert service.for_condition("Something Invented") is None


def test_double_spaced_names_still_resolve(service: KnowledgeService) -> None:
    assert service.for_condition("(vertigo) Paroymsal  Positional Vertigo") is not None
    assert service.for_condition("(vertigo) Paroymsal Positional Vertigo") is not None


def test_summaries_are_attributed(service: KnowledgeService) -> None:
    entry = service.for_condition("Malaria")

    assert entry is not None
    assert entry.summary_source
    assert entry.summary_source_url and entry.summary_source_url.startswith("https://")


def test_medication_entries_cite_a_source(service: KnowledgeService) -> None:
    entry = service.for_condition("Pneumonia")

    assert entry is not None
    for medicine in entry.medications:
        assert medicine.source
        assert medicine.source_url.startswith("https://")


def test_every_condition_carries_the_disclaimer(service: KnowledgeService) -> None:
    for condition in service.known_conditions:
        entry = service.for_condition(condition)
        assert entry is not None
        assert entry.disclaimer == PRESCRIPTION_DISCLAIMER


# ------------------------------------------------------------ allergy check


def test_an_allergy_on_file_flags_the_matching_class(
    service: KnowledgeService,
) -> None:
    entry = service.for_condition("Urinary tract infection", allergies=["Penicillin"])

    assert entry is not None
    flagged = entry.allergy_conflicts
    assert flagged, "a penicillin allergy should flag the antibiotic entry"
    assert "Penicillin" in flagged[0].allergy_warning


def test_the_allergy_warning_says_what_to_do(service: KnowledgeService) -> None:
    entry = service.for_condition("Urinary tract infection", allergies=["Penicillin"])

    assert entry is not None
    warning = entry.allergy_conflicts[0].allergy_warning
    assert warning is not None
    assert "doctor knows" in warning


def test_matching_is_loose_in_both_directions(service: KnowledgeService) -> None:
    """ "Amoxicillin" on a profile should reach the antibiotic class, and so
    should a broader "antibiotics". Over-warning is the safe direction."""
    for allergy in ("Amoxicillin", "amoxicillin", "penicillin V"):
        entry = service.for_condition("Impetigo", allergies=[allergy])
        assert entry is not None
        assert entry.allergy_conflicts, f"{allergy} should have flagged"


def test_an_unrelated_allergy_does_not_flag(service: KnowledgeService) -> None:
    entry = service.for_condition("Urinary tract infection", allergies=["Pollen", "Latex"])

    assert entry is not None
    assert entry.allergy_conflicts == []


def test_no_allergies_flags_nothing(service: KnowledgeService) -> None:
    entry = service.for_condition("Urinary tract infection", allergies=[])

    assert entry is not None
    assert all(not medicine.conflicts_with_allergy for medicine in entry.medications)


# ------------------------------------------------- what must never be shown


def _user_facing_text() -> str:
    """Every string a user could actually be shown.

    Scans the payload rather than the raw files: both `_readme` blocks quote the
    forbidden phrases in order to document why they were excluded, and matching
    those would be a false positive.
    """
    parts: list[str] = []
    for path, section in ((CONDITIONS_FILE, "conditions"), (CLASSES_FILE, "classes")):
        payload = json.loads(path.read_text())[section]
        parts.append(json.dumps(payload))
    return " ".join(parts)


def test_no_content_states_a_dose() -> None:
    """The single most dangerous thing this feature could do."""
    doses = re.findall(r"\b\d+\s*(?:mg|ml|mcg|µg|g|iu|units?)\b", _user_facing_text(), re.I)

    assert doses == [], f"knowledge base states doses: {doses}"


def test_no_content_instructs_a_medication_change() -> None:
    """Do not tell anyone to start, stop or change a prescription."""
    directives = re.findall(
        r"\b(?:stop taking|start taking|you should take|take \d|"
        r"increase your dose|decrease your dose|double the dose)\b",
        _user_facing_text(),
        re.I,
    )

    assert directives == [], f"knowledge base issues instructions: {directives}"


def test_the_precaution_file_was_not_used() -> None:
    """The source dataset's precautions include "stop taking drug", "take
    radioactive iodine treatment" and "salt baths" for hypertension. None of it
    may reach the knowledge base."""
    blob = json.dumps(json.loads(CONDITIONS_FILE.read_text())["conditions"]).lower()

    for phrase in (
        "stop taking drug",
        "radioactive iodine treatment",
        "otc pain reliver",
        "salt baths",
        "consume neem",
        "consume witch hazel",
        "milk thistle",
    ):
        assert phrase not in blob, f"unsafe source precaution leaked in: {phrase!r}"


def test_the_disclaimer_says_what_it_must() -> None:
    lowered = PRESCRIPTION_DISCLAIMER.lower()

    assert "is not a prescription" in lowered
    assert "before taking, stopping, or changing" in lowered


# ------------------------------------------------------------- the data files


def test_every_model_condition_has_an_entry() -> None:
    from pathlib import Path

    metadata = (
        Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "condition_model_metadata.json"
    )
    if not metadata.exists():
        pytest.skip("Model metadata not present; run training first.")

    labels = {" ".join(label.split()) for label in json.loads(metadata.read_text())["labels"]}
    known = {
        " ".join(name.split()) for name in json.loads(CONDITIONS_FILE.read_text())["conditions"]
    }

    assert labels - known == set()


def test_an_unknown_medication_class_is_rejected() -> None:
    """Fail at load rather than silently dropping the information."""
    conditions = {"Acne": {"medication_classes": ["nonexistent"]}}

    with pytest.raises(ValueError, match="unknown medication classes"):
        KnowledgeService(conditions=conditions, classes={})


def test_both_data_files_record_that_they_are_unreviewed() -> None:
    for path in (CONDITIONS_FILE, CLASSES_FILE):
        readme = " ".join(json.loads(path.read_text())["_readme"]).lower()
        assert "not reviewed by a clinician" in readme
