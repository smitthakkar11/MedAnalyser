"""The red-flag engine.

These are the highest-consequence tests in the project. A missed emergency is
the worst failure this system can have, so the cases below are written as
scenarios a person would actually describe, not as unit tests of the matcher.

The engine must also stay independent of the model: nothing here imports a
predictor, and no test needs trained artifacts.
"""

from __future__ import annotations

import json

import pytest

from app.services.safety import SafetyLevel, SafetyRuleEngine, get_safety_engine
from app.services.safety.rules import RULES_FILE, RuleError, load_rules


@pytest.fixture(scope="module")
def engine() -> SafetyRuleEngine:
    return get_safety_engine()


def _level(engine: SafetyRuleEngine, **kwargs: object) -> SafetyLevel:
    return engine.evaluate(**kwargs).level  # type: ignore[arg-type]


# ---------------------------------------------------------------- emergencies


@pytest.mark.parametrize(
    ("text", "expected_rule"),
    [
        ("I have crushing chest pain going down my arm", "crushing_chest_pain_text"),
        ("my chest feels tight and heavy", "crushing_chest_pain_text"),
        ("I passed out this morning", "loss_of_consciousness"),
        ("she collapsed and was unresponsive", "loss_of_consciousness"),
        ("my face is drooping and I cant speak properly", "stroke_text"),
        ("sudden numbness down one side", "stroke_text"),
        ("I cant breathe properly", "cannot_breathe_text"),
        ("gasping for air", "cannot_breathe_text"),
        ("my throat is swelling after eating peanuts", "anaphylaxis"),
        ("I used my epipen", "anaphylaxis"),
        ("bleeding heavily and cannot stop the bleeding", "severe_bleeding"),
        ("I am vomiting blood", "severe_bleeding"),
        ("worst headache of my life", "severe_neurological"),
        ("I had a seizure", "severe_neurological"),
        ("the rash does not fade when pressed", "meningitis_rash_text"),
        ("my skin is mottled and grey", "sepsis_text"),
    ],
)
async def test_described_emergencies_are_caught(
    engine: SafetyRuleEngine, text: str, expected_rule: str
) -> None:
    """The user's own words matter: the symptom vocabulary cannot express
    "crushing", "worst headache of my life" or "passed out"."""
    result = engine.evaluate(text=text)

    assert result.level is SafetyLevel.EMERGENCY
    assert expected_rule in {flag.id for flag in result.triggered}


def test_loss_of_consciousness_from_either_route(engine: SafetyRuleEngine) -> None:
    """Regression: the rule declares both a symptom and text patterns.

    Requiring both meant "I passed out" — with no symptom ticked — silently
    returned no red flag at all.
    """
    from_text = engine.evaluate(text="I passed out")
    from_symptom = engine.evaluate(symptoms=["coma"], text="")

    assert from_text.level is SafetyLevel.EMERGENCY
    assert from_symptom.level is SafetyLevel.EMERGENCY


def test_cardiac_combination(engine: SafetyRuleEngine) -> None:
    """Chest pain alone is not enough; chest pain with a cardiac sign is."""
    alone = engine.evaluate(symptoms=["chest_pain"], severity="mild")
    combined = engine.evaluate(symptoms=["chest_pain", "breathlessness"])

    assert alone.level is SafetyLevel.NONE
    assert combined.level is SafetyLevel.EMERGENCY


def test_severity_escalates(engine: SafetyRuleEngine) -> None:
    mild = engine.evaluate(symptoms=["chest_pain"], severity="mild")
    severe = engine.evaluate(symptoms=["chest_pain"], severity="severe")

    assert mild.level is SafetyLevel.NONE
    assert severe.level is SafetyLevel.EMERGENCY


def test_meningitis_needs_both_symptoms(engine: SafetyRuleEngine) -> None:
    assert engine.evaluate(symptoms=["high_fever"]).level is SafetyLevel.NONE
    assert engine.evaluate(symptoms=["high_fever", "stiff_neck"]).level is SafetyLevel.EMERGENCY


def test_self_harm_is_treated_as_an_emergency(engine: SafetyRuleEngine) -> None:
    result = engine.evaluate(text="I want to kill myself")

    assert result.level is SafetyLevel.EMERGENCY
    flag = next(item for item in result.triggered if item.id == "self_harm")
    # The advice must point somewhere concrete, not just say "seek help".
    assert "116 123" in flag.advice or "999" in flag.advice


# -------------------------------------------------------------------- urgent


def test_severe_abdominal_pain_is_urgent_not_emergency(
    engine: SafetyRuleEngine,
) -> None:
    """Proportionality matters: over-escalating everything trains people to
    ignore the warnings that count."""
    result = engine.evaluate(symptoms=["abdominal_pain"], severity="severe")

    assert result.level is SafetyLevel.URGENT


def test_a_long_fever_is_urgent(engine: SafetyRuleEngine) -> None:
    assert engine.evaluate(symptoms=["high_fever"], duration_days=7).level is SafetyLevel.URGENT
    assert engine.evaluate(symptoms=["high_fever"], duration_days=2).level is SafetyLevel.NONE


def test_the_worst_level_wins(engine: SafetyRuleEngine) -> None:
    """An emergency alongside urgent findings is still an emergency."""
    result = engine.evaluate(
        symptoms=["chest_pain", "breathlessness", "abdominal_pain"], severity="severe"
    )

    assert result.level is SafetyLevel.EMERGENCY
    assert result.triggered[0].level is SafetyLevel.EMERGENCY  # most urgent first


# ------------------------------------------------------------- no false alarm


@pytest.mark.parametrize(
    "scenario",
    [
        {"text": "I have a mild headache", "symptoms": ["headache"], "severity": "mild"},
        {"text": "runny nose and sneezing", "symptoms": ["runny_nose", "continuous_sneezing"]},
        {"text": "itchy skin rash for a week", "symptoms": ["itching", "skin_rash"]},
        {"text": "I feel a bit tired lately", "symptoms": ["fatigue"]},
        {"text": "", "symptoms": []},
    ],
)
async def test_ordinary_complaints_do_not_raise_a_flag(
    engine: SafetyRuleEngine, scenario: dict
) -> None:
    """False alarms have a real cost: they teach people to dismiss the warning."""
    assert engine.evaluate(**scenario).level is SafetyLevel.NONE


def test_negated_emergencies_are_not_flagged(engine: SafetyRuleEngine) -> None:
    """A symptom the user denied must not come back as a red flag.

    The extractor puts denied symptoms in `rejected_symptoms`, so they never
    reach the engine as reported symptoms.
    """
    result = engine.evaluate(symptoms=["headache"], text="no chest pain at all")

    assert result.level is SafetyLevel.NONE


def test_empty_input_is_safe(engine: SafetyRuleEngine) -> None:
    result = engine.evaluate()

    assert result.level is SafetyLevel.NONE
    assert result.triggered == []
    assert result.headline == ""


# ------------------------------------------------------------------ contract


def test_every_finding_cites_its_source(engine: SafetyRuleEngine) -> None:
    """A clinician reviewing this must be able to check each rule."""
    result = engine.evaluate(symptoms=["chest_pain", "breathlessness"])

    for flag in result.triggered:
        assert flag.source
        assert flag.source_url.startswith("https://")


def test_headlines_never_reassure(engine: SafetyRuleEngine) -> None:
    """The warning must not be softened by hedging language."""
    emergency = engine.evaluate(symptoms=["chest_pain"], severity="severe")
    urgent = engine.evaluate(symptoms=["abdominal_pain"], severity="severe")

    assert "emergency medical care now" in emergency.headline
    assert "today" in urgent.headline
    for headline in (emergency.headline, urgent.headline):
        for reassurance in ("probably", "unlikely", "may be nothing", "don't worry"):
            assert reassurance not in headline.lower()


def test_results_are_deterministic(engine: SafetyRuleEngine) -> None:
    """Same input, same warning — always."""
    first = engine.evaluate(symptoms=["chest_pain", "breathlessness"], text="chest pain")
    second = engine.evaluate(symptoms=["chest_pain", "breathlessness"], text="chest pain")

    assert [flag.id for flag in first.triggered] == [flag.id for flag in second.triggered]


def test_the_engine_does_not_depend_on_the_model() -> None:
    """Independence is the point. Red flags must work with no artifacts."""
    from pathlib import Path

    import app.services.safety.engine as engine_module

    source = engine_module.__file__
    assert source is not None
    text = Path(source).read_text()
    for forbidden in ("condition_prediction", "predict", "model_loader"):
        assert forbidden not in text


# ---------------------------------------------------------------- rule file


def test_all_rules_load() -> None:
    rules = load_rules()

    assert len(rules) >= 15
    assert all(rule.source_url.startswith("https://") for rule in rules)


def test_a_rule_with_no_triggers_is_rejected(tmp_path) -> None:
    """A rule that can never fire is worse than no rule: it looks like cover."""
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "empty",
                        "level": "emergency",
                        "title": "t",
                        "advice": "a",
                        "source": "s",
                        "source_url": "https://example.test",
                    }
                ]
            }
        )
    )

    with pytest.raises(RuleError, match="no triggers"):
        load_rules(path)


def test_a_rule_without_a_source_is_rejected(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "rules": [
                    {
                        "id": "unsourced",
                        "level": "emergency",
                        "title": "t",
                        "advice": "a",
                        "source": "s",
                        "any_symptoms": ["chest_pain"],
                    }
                ]
            }
        )
    )

    with pytest.raises(RuleError, match="no source"):
        load_rules(path)


def test_duplicate_rule_ids_are_rejected(tmp_path) -> None:
    entry = {
        "id": "dup",
        "level": "urgent",
        "title": "t",
        "advice": "a",
        "source": "s",
        "source_url": "https://example.test",
        "any_symptoms": ["chest_pain"],
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"rules": [entry, entry]}))

    with pytest.raises(RuleError, match="Duplicate"):
        load_rules(path)


def test_every_rule_symptom_exists_in_the_model_vocabulary() -> None:
    """A rule naming a symptom nothing can report is a rule that never fires."""
    from pathlib import Path

    metadata = (
        Path(__file__).resolve().parents[2] / "ml" / "artifacts" / "condition_model_metadata.json"
    )
    if not metadata.exists():
        pytest.skip("Model metadata not present; run training first.")

    vocabulary = set(json.loads(metadata.read_text())["features"]["names"])
    for rule in load_rules():
        unknown = (rule.any_symptoms | rule.all_symptoms) - vocabulary
        assert unknown == set(), f"{rule.id} names unknown symptoms: {sorted(unknown)}"


def test_the_rule_file_records_that_it_is_unreviewed() -> None:
    readme = " ".join(json.loads(RULES_FILE.read_text())["_readme"]).lower()

    assert "not been reviewed" in readme
    assert "take priority" in readme
