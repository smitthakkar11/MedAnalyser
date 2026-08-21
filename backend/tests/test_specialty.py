"""Specialty recommendation.

A transparent lookup, not a model. The precedence rules are what matter most,
and the emergency override above all: telling someone with crushing chest pain
to book a cardiologist would be actively dangerous.
"""

from __future__ import annotations

import json

import pytest

from app.services.doctors import DoctorSpecialtyService, get_specialty_service
from app.services.doctors.specialty import MAPPING_FILE
from app.services.safety import SafetyLevel


@pytest.fixture(scope="module")
def service() -> DoctorSpecialtyService:
    return get_specialty_service()


# ------------------------------------------------------------- from condition


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ("Fungal infection", "dermatologist"),
        ("Psoriasis", "dermatologist"),
        ("Heart attack", "cardiologist"),
        ("Hypertension", "cardiologist"),
        ("GERD", "gastroenterologist"),
        ("Peptic ulcer diseae", "gastroenterologist"),
        ("Migraine", "neurologist"),
        ("Diabetes", "endocrinologist"),
        ("Bronchial Asthma", "pulmonologist"),
        ("Hepatitis B", "hepatologist"),
        ("Arthritis", "rheumatologist"),
        ("(vertigo) Paroymsal Positional Vertigo", "ent"),
    ],
)
def test_conditions_map_to_a_specialty(
    service: DoctorSpecialtyService, condition: str, expected: str
) -> None:
    assert service.recommend(conditions=[condition]).specialty == expected


def test_the_highest_ranked_condition_wins(service: DoctorSpecialtyService) -> None:
    """Predictions arrive best-first; the top one drives the recommendation."""
    result = service.recommend(conditions=["GERD", "Migraine", "Acne"])

    assert result.specialty == "gastroenterologist"
    assert result.basis == "condition"


def test_double_spaced_condition_names_still_match(
    service: DoctorSpecialtyService,
) -> None:
    """The source data contains "(vertigo) Paroymsal  Positional Vertigo"."""
    assert (
        service.recommend(conditions=["(vertigo) Paroymsal  Positional Vertigo"]).specialty == "ent"
    )


def test_the_reason_uses_careful_language(service: DoctorSpecialtyService) -> None:
    """Never "you must see"; always "may be appropriate for evaluation"."""
    reason = service.recommend(conditions=["Heart attack"]).reason.lower()

    assert "may be an appropriate specialty" in reason
    for forbidden in ("you have", "you must", "diagnosed with", "definitely"):
        assert forbidden not in reason


# --------------------------------------------------------------- from symptom


def test_symptoms_are_used_when_no_condition_maps(
    service: DoctorSpecialtyService,
) -> None:
    result = service.recommend(conditions=[], symptoms=["joint_pain"])

    assert result.specialty == "rheumatologist"
    assert result.basis == "symptom"


def test_an_unmapped_condition_falls_through_to_symptoms(
    service: DoctorSpecialtyService,
) -> None:
    result = service.recommend(conditions=["Something Unmapped"], symptoms=["skin_rash"])

    assert result.specialty == "dermatologist"
    assert result.basis == "symptom"


def test_nothing_at_all_gives_a_general_physician(
    service: DoctorSpecialtyService,
) -> None:
    """The honest answer when there is nothing to go on."""
    result = service.recommend()

    assert result.specialty == "general_physician"
    assert result.basis == "default"


# ----------------------------------------------------------- safety override


def test_an_emergency_overrides_the_specialty(service: DoctorSpecialtyService) -> None:
    """Sending someone having a heart attack to an outpatient clinic would be
    the most dangerous thing this feature could do."""
    result = service.recommend(conditions=["Heart attack"], safety_level=SafetyLevel.EMERGENCY)

    assert result.overridden_by_safety is True
    assert result.basis == "emergency"
    assert result.display_name == "Emergency care"
    assert "emergency assessment now" in result.reason


def test_an_urgent_flag_does_not_override(service: DoctorSpecialtyService) -> None:
    """Urgent means see a doctor today, which a specialty suggestion still
    serves. Only an emergency replaces it."""
    result = service.recommend(conditions=["GERD"], safety_level=SafetyLevel.URGENT)

    assert result.overridden_by_safety is False
    assert result.specialty == "gastroenterologist"


def test_the_override_accepts_the_stored_string_form(
    service: DoctorSpecialtyService,
) -> None:
    result = service.recommend(conditions=["Heart attack"], safety_level="emergency")

    assert result.overridden_by_safety is True


# ------------------------------------------------------------- the data file


def test_every_model_condition_is_mapped() -> None:
    """An unmapped condition silently degrades to General Physician."""
    from pathlib import Path

    metadata = (
        Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "condition_model_metadata.json"
    )
    if not metadata.exists():
        pytest.skip("Model metadata not present; run training first.")

    labels = {" ".join(label.split()) for label in json.loads(metadata.read_text())["labels"]}
    mapped = {
        " ".join(condition.split())
        for condition in json.loads(MAPPING_FILE.read_text())["conditions"]
    }

    assert labels - mapped == set()


def test_a_mapping_referencing_an_unknown_specialty_is_rejected() -> None:
    """Fail at load rather than recommending a specialty that does not exist."""
    payload = {
        "default_specialty": "general_physician",
        "specialties": {"general_physician": {"display": "General Physician", "description": "d"}},
        "conditions": {"Acne": {"specialty": "wizard"}},
        "symptom_fallback": {},
    }

    with pytest.raises(ValueError, match="unknown specialties"):
        DoctorSpecialtyService(payload)


def test_divergences_from_the_source_are_documented() -> None:
    """Where this project overrides its source, it must say why."""
    conditions = json.loads(MAPPING_FILE.read_text())["conditions"]
    diverging = {
        name: entry["diverges"] for name, entry in conditions.items() if "diverges" in entry
    }

    assert len(diverging) >= 10
    assert all(len(reason) > 20 for reason in diverging.values())


def test_the_adults_only_divergence_is_present() -> None:
    """The source sends Typhoid to a paediatrician; this product is 18+."""
    service = get_specialty_service()

    note = service.divergence_note("Typhoid")

    assert note is not None
    assert "adults" in note.lower()
    assert service.recommend(conditions=["Typhoid"]).specialty == "infectious_disease"


def test_the_mapping_records_that_it_is_unreviewed() -> None:
    readme = " ".join(json.loads(MAPPING_FILE.read_text())["_readme"]).lower()

    assert "not reviewed by a clinician" in readme
    assert "not a model" in readme or "not a model" in readme
