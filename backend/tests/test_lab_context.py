"""Laboratory evidence attached to an assessment.

The property these tests defend: lab values inform *what is shown* and *what is
asked*, but never enter the condition model. The model is trained on symptoms
only, so a lab value in its feature vector would be a number it has never
learned anything from.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest

from app.models.report import ReportValue, ValueFlag
from app.services.ml.lab_context import LabContextService, get_lab_context_service
from app.services.ml.lab_context.service import PROMPTS_FILE

REPORT_ID = uuid.uuid4()
REPORT_NAMES = {str(REPORT_ID): "cbc.pdf"}


def _value(
    analyte: str,
    value: float,
    flag: ValueFlag,
    *,
    display: str | None = None,
    minutes_old: int = 0,
) -> ReportValue:
    row = ReportValue(
        report_id=REPORT_ID,
        user_id=uuid.uuid4(),
        analyte=analyte,
        display_name=display or analyte.replace("_", " ").capitalize(),
        value=value,
        unit="g/dL",
        flag=flag,
        reference_text="13.0 - 17.0",
    )
    # created_at is normally set by the database.
    row.created_at = datetime.now(UTC).replace(microsecond=minutes_old)
    return row


@pytest.fixture
def service() -> LabContextService:
    return get_lab_context_service()


# ------------------------------------------------------------------ findings


def test_findings_carry_their_provenance(service: LabContextService) -> None:
    """A client must be able to tell a measured value from a model output."""
    context = service.build([_value("hemoglobin", 10.8, ValueFlag.LOW)], REPORT_NAMES)

    assert context.findings[0].source == "report"
    assert context.findings[0].report_filename == "cbc.pdf"


def test_abnormal_findings_are_identified(service: LabContextService) -> None:
    context = service.build(
        [
            _value("hemoglobin", 10.8, ValueFlag.LOW),
            _value("platelets", 200000, ValueFlag.NORMAL),
            _value("tsh", 3.0, ValueFlag.UNKNOWN),
        ],
        REPORT_NAMES,
    )

    assert [finding.analyte for finding in context.abnormal] == ["hemoglobin"]
    assert len(context.findings) == 3


def test_a_value_with_no_printed_range_is_never_abnormal(
    service: LabContextService,
) -> None:
    """`unknown` means the report gave no range, not that the value is fine."""
    context = service.build([_value("tsh", 99.0, ValueFlag.UNKNOWN)], REPORT_NAMES)

    assert context.abnormal == []
    assert context.findings[0].flag is ValueFlag.UNKNOWN


def test_abnormal_findings_are_listed_first(service: LabContextService) -> None:
    context = service.build(
        [
            _value("platelets", 200000, ValueFlag.NORMAL),
            _value("hemoglobin", 10.8, ValueFlag.LOW),
        ],
        REPORT_NAMES,
    )

    assert context.findings[0].analyte == "hemoglobin"


def test_only_the_most_recent_value_per_analyte_is_carried(
    service: LabContextService,
) -> None:
    """An assessment is about the current state; three historical haemoglobins
    shown side by side would read as three separate results to weigh."""
    context = service.build(
        [
            _value("hemoglobin", 9.0, ValueFlag.LOW, minutes_old=1),
            _value("hemoglobin", 12.0, ValueFlag.LOW, minutes_old=5),
        ],
        REPORT_NAMES,
    )

    assert len(context.findings) == 1
    assert context.findings[0].value == 12.0


def test_no_values_gives_an_empty_context(service: LabContextService) -> None:
    context = service.build([], {})

    assert context.is_empty
    assert context.prompted_symptoms == []


# ------------------------------------------------------------------- prompts


def test_an_abnormal_value_prompts_related_symptoms(
    service: LabContextService,
) -> None:
    context = service.build([_value("hemoglobin", 8.0, ValueFlag.LOW)], REPORT_NAMES)

    assert "fatigue" in context.prompted_symptoms
    assert "breathlessness" in context.prompted_symptoms


def test_normal_values_prompt_nothing(service: LabContextService) -> None:
    context = service.build([_value("hemoglobin", 14.0, ValueFlag.NORMAL)], REPORT_NAMES)

    assert context.prompted_symptoms == []


def test_direction_matters(service: LabContextService) -> None:
    """High and low TSH point at opposite symptoms."""
    low = service.build([_value("tsh", 0.1, ValueFlag.LOW)], REPORT_NAMES)
    high = service.build([_value("tsh", 12.0, ValueFlag.HIGH)], REPORT_NAMES)

    assert "weight_loss" in low.prompted_symptoms
    assert "weight_gain" in high.prompted_symptoms
    assert "weight_gain" not in low.prompted_symptoms


def test_symptoms_pointed_at_by_several_results_rank_first(
    service: LabContextService,
) -> None:
    """Three out-of-range values agreeing on fatigue beats one borderline result."""
    context = service.build(
        [
            _value("hemoglobin", 8.0, ValueFlag.LOW),
            _value("ferritin", 5.0, ValueFlag.LOW),
            _value("vitamin_b12", 90.0, ValueFlag.LOW),
        ],
        REPORT_NAMES,
    )

    assert context.prompted_symptoms[0] == "fatigue"


def test_symptoms_already_settled_are_not_prompted(
    service: LabContextService,
) -> None:
    """Neither reported nor explicitly denied symptoms are worth re-asking."""
    context = service.build(
        [_value("hemoglobin", 8.0, ValueFlag.LOW)],
        REPORT_NAMES,
        already_known={"fatigue", "breathlessness"},
    )

    assert "fatigue" not in context.prompted_symptoms
    assert "breathlessness" not in context.prompted_symptoms


def test_prompt_count_is_bounded(service: LabContextService) -> None:
    context = service.build(
        [
            _value("hemoglobin", 8.0, ValueFlag.LOW),
            _value("tsh", 12.0, ValueFlag.HIGH),
            _value("creatinine", 3.0, ValueFlag.HIGH),
            _value("alt", 200.0, ValueFlag.HIGH),
            _value("glucose_fasting", 200.0, ValueFlag.HIGH),
        ],
        REPORT_NAMES,
    )

    assert len(context.prompted_symptoms) <= 6


# ------------------------------------------------------------ the data file


def test_every_prompted_symptom_exists_in_the_model_vocabulary() -> None:
    """A prompt for a symptom the model cannot represent is a dead end: the
    user answers and nothing can use it."""
    from pathlib import Path

    metadata = (
        Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "condition_model_metadata.json"
    )
    if not metadata.exists():
        pytest.skip("Model metadata not present; run training first.")

    vocabulary = set(json.loads(metadata.read_text())["features"]["names"])
    prompts = json.loads(PROMPTS_FILE.read_text())["prompts"]

    unknown = {
        key: [symptom for symptom in symptoms if symptom not in vocabulary]
        for key, symptoms in prompts.items()
    }
    assert {key: value for key, value in unknown.items() if value} == {}


def test_every_prompt_key_names_an_extractable_analyte_and_direction() -> None:
    from pathlib import Path

    analytes_file = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "services"
        / "reports"
        / "data"
        / "lab_analytes.json"
    )
    analytes = set(json.loads(analytes_file.read_text())["analytes"])
    prompts = json.loads(PROMPTS_FILE.read_text())["prompts"]

    for key in prompts:
        analyte, _, direction = key.rpartition("_")
        assert analyte in analytes, f"{key}: '{analyte}' is not an extractable analyte"
        assert direction in ("low", "high"), f"{key}: bad direction '{direction}'"


def test_the_prompt_file_records_that_it_is_unreviewed() -> None:
    """The mapping is general knowledge, not clinically reviewed, and the file
    has to say so."""
    payload = json.loads(PROMPTS_FILE.read_text())

    readme = " ".join(payload["_readme"]).lower()
    assert "not been reviewed" in readme
    assert "never a conclusion" in readme
