"""Condition prediction service.

Uses a small model trained in-fixture rather than the committed artifacts, so
the tests are hermetic and do not depend on anyone having run training. One
test does exercise the real artifacts, and skips when they are absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder

from app.core.config import Environment, Settings
from app.services.ml.condition_prediction.features import SymptomVectoriser
from app.services.ml.condition_prediction.inference import (
    MIN_INFORMATIVE_SYMPTOMS,
    ConditionPredictionService,
)
from app.services.ml.condition_prediction.model_loader import (
    LoadedModel,
    ModelUnavailableError,
    load_condition_model,
)

# A deliberately tiny, fully separable training set.
TRAINING_CASES: list[tuple[str, list[str]]] = [
    ("Common Cold", ["cough", "runny_nose", "sore_throat"]),
    ("Common Cold", ["cough", "runny_nose"]),
    ("Common Cold", ["cough", "sore_throat"]),
    ("Migraine", ["headache", "nausea", "light_sensitivity"]),
    ("Migraine", ["headache", "nausea"]),
    ("Migraine", ["headache", "light_sensitivity"]),
    ("Food Poisoning", ["vomiting", "diarrhoea", "abdominal_pain"]),
    ("Food Poisoning", ["vomiting", "diarrhoea"]),
    ("Food Poisoning", ["vomiting", "abdominal_pain"]),
]


@pytest.fixture
def model() -> LoadedModel:
    """A real, trained model — small enough to fit in a fixture."""
    labels = [label for label, _ in TRAINING_CASES]
    symptom_sets = [symptoms for _, symptoms in TRAINING_CASES]

    vectoriser = SymptomVectoriser.fit(symptom_sets)
    encoder = LabelEncoder().fit(labels)
    estimator = RandomForestClassifier(n_estimators=50, random_state=42).fit(
        vectoriser.transform(symptom_sets), encoder.transform(labels)
    )
    return LoadedModel(
        estimator=estimator,
        vectoriser=vectoriser,
        label_encoder=encoder,
        metadata={"model_name": "test_model", "model_version": "v0"},
    )


@pytest.fixture
def service(model: LoadedModel) -> ConditionPredictionService:
    return ConditionPredictionService(model)


def test_predicts_the_expected_condition(service: ConditionPredictionService) -> None:
    result = service.predict(["cough", "runny_nose", "sore_throat"])

    assert result.predictions[0].condition == "Common Cold"


def test_predictions_are_ranked_by_descending_score(
    service: ConditionPredictionService,
) -> None:
    result = service.predict(["headache", "nausea"])

    scores = [prediction.score for prediction in result.predictions]
    assert scores == sorted(scores, reverse=True)


def test_scores_are_within_the_declared_range(
    service: ConditionPredictionService,
) -> None:
    result = service.predict(["vomiting", "diarrhoea"])

    assert all(0.0 <= prediction.score <= 1.0 for prediction in result.predictions)


def test_top_k_limits_the_number_of_candidates(
    service: ConditionPredictionService,
) -> None:
    assert len(service.predict(["cough"], top_k=2).predictions) <= 2


def test_result_reports_the_model_identity(service: ConditionPredictionService) -> None:
    """Every stored assessment must be attributable to a model version."""
    result = service.predict(["cough"])

    assert result.model_name == "test_model"
    assert result.model_version == "v0"


def test_input_is_normalised_before_matching(
    service: ConditionPredictionService,
) -> None:
    """The service accepts what a caller would realistically send."""
    result = service.predict([" Runny Nose ", "COUGH"])

    assert result.recognised_symptoms == ["cough", "runny_nose"]
    assert result.unrecognised_symptoms == []


def test_unrecognised_symptoms_are_reported_not_dropped(
    service: ConditionPredictionService,
) -> None:
    result = service.predict(["cough", "levitation", "telepathy"])

    assert result.recognised_symptoms == ["cough"]
    assert result.unrecognised_symptoms == ["levitation", "telepathy"]


def test_entirely_unknown_input_returns_no_predictions(
    service: ConditionPredictionService,
) -> None:
    """Better to return nothing than to rank classes from an all-zero vector."""
    result = service.predict(["levitation"])

    assert result.predictions == []
    assert result.low_information is True


def test_empty_input_returns_no_predictions(
    service: ConditionPredictionService,
) -> None:
    result = service.predict([])

    assert result.predictions == []
    assert result.recognised_symptoms == []
    assert result.low_information is True


def test_low_information_is_flagged_below_the_threshold(
    service: ConditionPredictionService,
) -> None:
    """Accuracy degrades sharply on thin input; the caller must be able to see it."""
    assert service.predict(["cough"]).low_information is True
    assert service.predict(["cough", "runny_nose"]).low_information is True

    full = service.predict(["cough", "runny_nose", "sore_throat"])
    assert len(full.recognised_symptoms) >= MIN_INFORMATIVE_SYMPTOMS
    assert full.low_information is False


def test_duplicate_symptoms_are_collapsed(service: ConditionPredictionService) -> None:
    result = service.predict(["cough", "Cough", " cough "])

    assert result.recognised_symptoms == ["cough"]


def test_explanation_only_cites_symptoms_the_user_reported(
    service: ConditionPredictionService,
) -> None:
    """A model explanation must never mention input the user did not give."""
    reported = ["headache", "nausea"]

    result = service.predict(reported)

    for prediction in result.predictions:
        assert set(prediction.contributing_symptoms) <= set(reported)


def test_prediction_is_deterministic(service: ConditionPredictionService) -> None:
    """The same input must give the same output; assessments are stored."""
    first = service.predict(["cough", "runny_nose"])
    second = service.predict(["cough", "runny_nose"])

    assert first.model_dump() == second.model_dump()


def test_service_exposes_its_vocabulary(service: ConditionPredictionService) -> None:
    assert "cough" in service.known_symptoms
    assert set(service.known_conditions) == {"Common Cold", "Migraine", "Food Poisoning"}


# ------------------------------------------------------------- model loading


def test_loading_reports_missing_artifacts_clearly(tmp_path: Path) -> None:
    settings = Settings(
        environment=Environment.TEST,
        ml_artifacts_path=tmp_path,
        _env_file=None,  # type: ignore[call-arg]
    )

    with pytest.raises(ModelUnavailableError, match="not found"):
        load_condition_model(settings)


def test_loading_reports_corrupt_artifacts_clearly(tmp_path: Path) -> None:
    """A truncated or unreadable artifact must not surface as a raw pickle error."""
    for name in (
        "condition_model.joblib",
        "condition_model_vectoriser.joblib",
        "condition_model_label_encoder.joblib",
    ):
        (tmp_path / name).write_bytes(b"not a joblib file")
    (tmp_path / "condition_model_metadata.json").write_text("{}")
    settings = Settings(
        environment=Environment.TEST,
        ml_artifacts_path=tmp_path,
        _env_file=None,  # type: ignore[call-arg]
    )

    with pytest.raises(ModelUnavailableError, match="could not be loaded"):
        load_condition_model(settings)


def test_round_trip_through_disk_preserves_predictions(model: LoadedModel, tmp_path: Path) -> None:
    """Serialisation must not change behaviour.

    This is the check that the artifacts the API loads behave exactly like the
    objects training produced.
    """
    joblib.dump(model.estimator, tmp_path / "condition_model.joblib")
    joblib.dump(model.vectoriser, tmp_path / "condition_model_vectoriser.joblib")
    joblib.dump(model.label_encoder, tmp_path / "condition_model_label_encoder.joblib")
    (tmp_path / "condition_model_metadata.json").write_text(
        json.dumps({"model_name": "test_model", "model_version": "v0"})
    )
    settings = Settings(
        environment=Environment.TEST,
        ml_artifacts_path=tmp_path,
        _env_file=None,  # type: ignore[call-arg]
    )

    reloaded = ConditionPredictionService(load_condition_model(settings))

    symptoms = ["cough", "runny_nose", "sore_throat"]
    before = ConditionPredictionService(model).predict(symptoms)
    after = reloaded.predict(symptoms)
    assert before.model_dump() == after.model_dump()


def test_the_real_trained_model_loads_and_predicts() -> None:
    """Exercises the committed pipeline end to end.

    Skips rather than fails when training has not been run: a fresh checkout has
    no artifacts, and that is a documented state, not a broken one.
    """
    try:
        loaded = load_condition_model()
    except ModelUnavailableError as exc:
        pytest.skip(f"Trained artifacts not present: {exc}")

    service = ConditionPredictionService(loaded)
    result = service.predict(
        ["itching", "skin_rash", "nodal_skin_eruptions", "dischromic _patches"]
    )

    assert result.predictions, "the real model should rank at least one condition"
    assert result.predictions[0].condition == "Fungal infection"
    assert result.low_information is False
    assert len(service.known_conditions) == 41
