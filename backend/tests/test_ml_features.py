"""Feature construction — the shared train/serve boundary.

These are the highest-value ML unit tests in the project: if vectorisation
drifts between training and inference, every prediction is silently wrong while
every other test still passes.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.services.ml.condition_prediction.features import (
    SymptomVectoriser,
    normalise_label,
    normalise_symptom,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" dischromic _patches", "dischromic_patches"),
        ("Skin Rash", "skin_rash"),
        ("skin_rash", "skin_rash"),
        ("  JOINT   PAIN  ", "joint_pain"),
        ("stomach-pain", "stomach_pain"),
        ("_leading_and_trailing_", "leading_and_trailing"),
    ],
)
def test_symptom_normalisation(raw: str, expected: str) -> None:
    """The source data is inconsistently formatted; one symptom, one feature."""
    assert normalise_symptom(raw) == expected


def test_label_normalisation_collapses_double_spaces() -> None:
    assert normalise_label("(vertigo) Paroymsal  Positional Vertigo") == (
        "(vertigo) Paroymsal Positional Vertigo"
    )


def test_vocabulary_is_sorted_and_deduplicated() -> None:
    vectoriser = SymptomVectoriser.fit([["fever", "cough"], ["Cough", " FEVER "], ["rash"]])

    assert vectoriser.vocabulary == ["cough", "fever", "rash"]
    assert vectoriser.n_features == 3


def test_vectorisation_is_multi_hot_in_vocabulary_order() -> None:
    vectoriser = SymptomVectoriser(["cough", "fever", "rash"])

    vector = vectoriser.transform_one(["fever", "rash"])

    assert vector.tolist() == [0.0, 1.0, 1.0]
    assert vector.dtype == np.float32


def test_vectorisation_is_order_independent() -> None:
    """A symptom set is a set; the order the user mentions them cannot matter."""
    vectoriser = SymptomVectoriser(["cough", "fever", "rash"])

    assert vectoriser.transform_one(["rash", "fever"]).tolist() == (
        vectoriser.transform_one(["fever", "rash"]).tolist()
    )


def test_unknown_symptoms_do_not_shift_columns() -> None:
    """An unseen symptom must be ignored, never appended.

    Appending would change the vector width and silently misalign every
    downstream feature against what the model was fitted on.
    """
    vectoriser = SymptomVectoriser(["cough", "fever"])

    vector = vectoriser.transform_one(["fever", "an_unseen_symptom"])

    assert vector.tolist() == [0.0, 1.0]
    assert len(vector) == vectoriser.n_features


def test_known_and_unknown_partition_the_input() -> None:
    vectoriser = SymptomVectoriser(["cough", "fever"])

    assert vectoriser.known(["Fever", "made_up"]) == ["fever"]
    assert vectoriser.unknown(["Fever", "made_up"]) == ["made_up"]


def test_duplicate_symptoms_do_not_double_count() -> None:
    vectoriser = SymptomVectoriser(["cough", "fever"])

    assert vectoriser.transform_one(["fever", "Fever", " fever "]).tolist() == [0.0, 1.0]


def test_transform_matches_transform_one_row_for_row() -> None:
    """The batch path used in training and the single path used at inference
    must produce identical vectors."""
    vectoriser = SymptomVectoriser(["cough", "fever", "rash"])
    sets = [["fever"], ["cough", "rash"], []]

    matrix = vectoriser.transform(sets)

    assert matrix.shape == (3, 3)
    for row, symptoms in zip(matrix, sets, strict=True):
        assert row.tolist() == vectoriser.transform_one(symptoms).tolist()


def test_transform_of_nothing_keeps_the_feature_width() -> None:
    vectoriser = SymptomVectoriser(["cough", "fever"])

    assert vectoriser.transform([]).shape == (0, 2)


def test_empty_and_whitespace_symptoms_are_dropped_from_the_vocabulary() -> None:
    vectoriser = SymptomVectoriser.fit([["fever", "", "   ", "cough"]])

    assert vectoriser.vocabulary == ["cough", "fever"]
