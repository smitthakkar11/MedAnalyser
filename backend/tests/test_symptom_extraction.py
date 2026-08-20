"""Free-text symptom extraction.

Negation is the highest-stakes behaviour here: mis-reading "no chest pain" as
chest pain does not merely lose signal, it feeds the model the opposite of what
the user said.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.ml.feature_extraction import get_symptom_extractor
from app.services.ml.feature_extraction.symptom_extractor import (
    DATA_FILE,
    SymptomExtractor,
)


@pytest.fixture(scope="module")
def extractor() -> SymptomExtractor:
    return get_symptom_extractor()


# ------------------------------------------------------------------ matching


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("I have a headache", "headache"),
        ("my stomach ache is bad", "abdominal_pain"),
        ("been throwing up all night", "vomiting"),
        ("I have a high temperature", "high_fever"),
        ("terrible chest pain", "chest_pain"),
        ("shortness of breath", "breathlessness"),
        ("loose motions since morning", "diarrhoea"),
        ("my skin is itchy", "itching"),
        ("feeling nauseous", "nausea"),
        ("cant stop sneezing", "continuous_sneezing"),
        ("the room is spinning", "spinning_movements"),
        ("yellow eyes", "yellowing_of_eyes"),
    ],
)
def test_everyday_phrasing_maps_to_the_model_vocabulary(
    extractor: SymptomExtractor, text: str, expected: str
) -> None:
    assert expected in extractor.extract(text).symptoms


def test_canonical_names_match_without_being_listed_as_synonyms(
    extractor: SymptomExtractor,
) -> None:
    """ "abdominal pain" works because the loader derives it from the key."""
    assert "abdominal_pain" in extractor.extract("abdominal pain").symptoms


def test_longest_phrase_wins(extractor: SymptomExtractor) -> None:
    """ "chest pain" must not be shadowed by a shorter overlapping phrase."""
    result = extractor.extract("I have chest pain")

    assert "chest_pain" in result.symptoms


def test_multiple_symptoms_in_one_sentence(extractor: SymptomExtractor) -> None:
    result = extractor.extract("fever, headache and vomiting for three days")

    assert set(result.symptoms) == {"high_fever", "headache", "vomiting"}


def test_repeated_mentions_are_recorded_once(extractor: SymptomExtractor) -> None:
    result = extractor.extract("headache, really bad headache, my head hurts")

    assert result.symptoms.count("headache") == 1


def test_empty_and_whitespace_input(extractor: SymptomExtractor) -> None:
    assert extractor.extract("").is_empty
    assert extractor.extract("   ").is_empty


def test_text_with_no_recognisable_symptom(extractor: SymptomExtractor) -> None:
    result = extractor.extract("I feel a bit strange lately")

    assert result.symptoms == []
    assert result.is_empty


# ------------------------------------------------------------------ negation


@pytest.mark.parametrize(
    "text",
    [
        "no rash",
        "I do not have a rash",
        "without any rash",
        "denies rash",
        "there is no sign of a rash",
        "I havent had a rash",
    ],
)
def test_negated_symptoms_are_excluded(extractor: SymptomExtractor, text: str) -> None:
    result = extractor.extract(text)

    assert "skin_rash" not in result.symptoms
    assert "skin_rash" in result.negated_symptoms


def test_negation_scope_ends_at_a_contrast_word(extractor: SymptomExtractor) -> None:
    """ "no fever but a bad cough" negates only the fever."""
    result = extractor.extract("no fever but a bad cough")

    assert "high_fever" in result.negated_symptoms
    assert "cough" in result.symptoms


def test_negation_does_not_reach_across_a_long_sentence(
    extractor: SymptomExtractor,
) -> None:
    """A cue must not negate something many words later."""
    result = extractor.extract(
        "no allergies that I know of, and for the past three days I have had a headache"
    )

    assert "headache" in result.symptoms


def test_positive_and_negative_symptoms_are_kept_apart(
    extractor: SymptomExtractor,
) -> None:
    result = extractor.extract("I have a high temperature and vomiting but no diarrhea")

    assert set(result.symptoms) == {"high_fever", "vomiting"}
    assert result.negated_symptoms == ["diarrhoea"]


# ------------------------------------------------------- duration & severity


@pytest.mark.parametrize(
    ("text", "expected_days"),
    [
        ("headache for 3 days", 3),
        ("headache for three days", 3),
        ("cough for 2 weeks", 14),
        ("rash for a month", 30),
        ("fever since yesterday", 2),
        ("vomiting since this morning", 1),
        ("pain for a couple of days", 2),
    ],
)
def test_duration_is_extracted(
    extractor: SymptomExtractor, text: str, expected_days: float
) -> None:
    assert extractor.extract(text).duration_days == expected_days


def test_duration_absent_when_not_stated(extractor: SymptomExtractor) -> None:
    assert extractor.extract("I have a headache").duration_days is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mild headache", "mild"),
        ("a slight cough", "mild"),
        ("moderate pain", "moderate"),
        ("severe chest pain", "severe"),
        ("unbearable headache", "severe"),
        ("really bad stomach ache", "severe"),
    ],
)
def test_severity_is_extracted(extractor: SymptomExtractor, text: str, expected: str) -> None:
    assert extractor.extract(text).severity == expected


def test_the_worst_stated_severity_wins(extractor: SymptomExtractor) -> None:
    """A mild symptom alongside a severe one must not downgrade the episode."""
    assert extractor.extract("mild headache but severe chest pain").severity == "severe"


# ------------------------------------------------------------ the data file


def test_every_synonym_key_exists_in_the_model_vocabulary() -> None:
    """A key that is not a real symptom is a typo that would never match."""
    metadata_path = (
        Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "condition_model_metadata.json"
    )
    if not metadata_path.exists():
        pytest.skip("Model metadata not present; run training first.")

    vocabulary = set(json.loads(metadata_path.read_text())["features"]["names"])
    keys = set(json.loads(DATA_FILE.read_text())["symptoms"])

    assert keys - vocabulary == set(), "synonym keys not in the model vocabulary"
    assert vocabulary - keys == set(), "model symptoms with no synonym entry"


def test_the_data_file_has_no_duplicate_keys() -> None:
    """JSON silently keeps the last of duplicate keys, discarding earlier
    synonyms. Only a parse-time check catches it."""
    import collections

    duplicates: list[str] = []

    def hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        counts = collections.Counter(key for key, _ in pairs)
        duplicates.extend(key for key, count in counts.items() if count > 1)
        return dict(pairs)

    json.loads(DATA_FILE.read_text(), object_pairs_hook=hook)

    assert duplicates == []


def test_extractor_is_cached(extractor: SymptomExtractor) -> None:
    """Compiling the phrase pattern is not free; it must happen once."""
    assert get_symptom_extractor() is extractor
