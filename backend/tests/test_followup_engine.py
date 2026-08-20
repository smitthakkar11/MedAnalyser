"""The follow-up question engine and its rule language."""

from __future__ import annotations

import pytest

from app.services.ml.followup import AssessmentState, FollowUpQuestionEngine
from app.services.ml.followup.rules import (
    RuleSyntaxError,
    load_rules,
    parse_condition,
)

CONDITION_SYMPTOMS = {
    "Migraine": ["headache", "nausea", "visual_disturbances", "irritability"],
    "Gastroenteritis": ["vomiting", "diarrhoea", "abdominal_pain", "dehydration"],
    "Typhoid": ["high_fever", "headache", "abdominal_pain", "vomiting"],
}


@pytest.fixture
def engine() -> FollowUpQuestionEngine:
    return FollowUpQuestionEngine(condition_symptoms=CONDITION_SYMPTOMS)


# ---------------------------------------------------------- rule expressions


@pytest.mark.parametrize(
    "expression",
    [
        "duration_days is unknown",
        "previous_consultation is true",
        "previous_medication is present",
        "recognised_symptom_count < 6",
        "candidate_symptoms_available",
        "previous_consultation is true and previous_diagnosis is unknown",
    ],
)
def test_supported_expressions_parse(expression: str) -> None:
    assert parse_condition(expression)


@pytest.mark.parametrize(
    "expression",
    ["duration_days ~= 4", "previous_consultation or something", "is unknown"],
)
def test_unsupported_expressions_are_rejected(expression: str) -> None:
    """A rule the engine cannot parse must fail loudly, not be skipped."""
    with pytest.raises(RuleSyntaxError):
        parse_condition(expression)


def test_shipped_rules_load_and_are_ordered() -> None:
    rules = load_rules()

    assert [rule.order for rule in rules] == sorted(rule.order for rule in rules)
    assert len({rule.key for rule in rules}) == len(rules)


# ----------------------------------------------------------------- ordering


def test_first_question_is_duration_when_nothing_is_known(
    engine: FollowUpQuestionEngine,
) -> None:
    question = engine.next_question(AssessmentState(recognised_symptoms=["headache"]))

    assert question is not None
    assert question.key == "duration"


def test_a_fact_taken_from_the_free_text_is_not_asked_again(
    engine: FollowUpQuestionEngine,
) -> None:
    """The user wrote "for 3 days"; asking the duration would ignore them."""
    state = AssessmentState(recognised_symptoms=["headache"], duration_days=3.0)
    state.answered.add("duration")

    question = engine.next_question(state)

    assert question is not None
    assert question.key != "duration"


def test_questions_are_not_repeated(engine: FollowUpQuestionEngine) -> None:
    state = AssessmentState(recognised_symptoms=["headache"])
    first = engine.next_question(state)
    assert first is not None

    state.asked[first.key] += 1
    state.answered.add(first.key)
    second = engine.next_question(state)

    assert second is not None
    assert second.key != first.key


def test_the_intake_terminates(engine: FollowUpQuestionEngine) -> None:
    """Answering everything must eventually yield no question at all."""
    state = AssessmentState(
        recognised_symptoms=["headache", "nausea", "vomiting", "high_fever", "chills", "fatigue"],
        candidate_conditions=list(CONDITION_SYMPTOMS),
    )

    for _ in range(25):
        question = engine.next_question(state)
        if question is None:
            break
        state.asked[question.key] += 1
        state.answered.add(question.key)
        if question.key == "previous_consultation":
            state.previous_consultation = False
    else:
        pytest.fail("the question engine never finished")

    assert engine.next_question(state) is None


# -------------------------------------------------------------- conditionals


def test_diagnosis_is_only_asked_after_a_consultation(
    engine: FollowUpQuestionEngine,
) -> None:
    """No doctor seen means no diagnosis to report."""
    state = AssessmentState(
        recognised_symptoms=["headache", "nausea", "vomiting"],
        duration_days=3.0,
        severity="moderate",
        previous_consultation=False,
    )
    state.answered.update({"duration", "severity", "previous_consultation", "additional_symptoms"})
    state.asked["additional_symptoms"] = 2

    remaining = []
    for _ in range(6):
        question = engine.next_question(state)
        if question is None:
            break
        remaining.append(question.key)
        state.asked[question.key] += 1
        state.answered.add(question.key)

    assert "previous_diagnosis" not in remaining
    assert "previous_medication" not in remaining


def test_the_documented_consultation_chain_is_asked_in_order(
    engine: FollowUpQuestionEngine,
) -> None:
    """Consultation -> diagnosis -> medication -> did it help."""
    state = AssessmentState(
        recognised_symptoms=["abdominal_pain", "vomiting", "nausea"],
        duration_days=3.0,
        severity="moderate",
    )
    state.answered.update({"duration", "severity", "additional_symptoms"})
    state.asked["additional_symptoms"] = 2

    asked: list[str] = []
    answers = {
        "previous_consultation": True,
        "previous_diagnosis": "gastritis",
        "previous_medication": "pantoprazole",
        "treatment_response": "improved",
        "still_taking_medication": False,
    }
    for _ in range(8):
        question = engine.next_question(state)
        if question is None:
            break
        asked.append(question.key)
        state.asked[question.key] += 1
        state.record_answer(question.key, answers.get(question.key))

    assert asked == [
        "previous_consultation",
        "previous_diagnosis",
        "previous_medication",
        "treatment_response",
        "still_taking_medication",
    ]


def test_treatment_response_is_skipped_without_a_medication(
    engine: FollowUpQuestionEngine,
) -> None:
    state = AssessmentState(recognised_symptoms=["headache"], previous_consultation=True)
    state.answered.update(
        {
            "duration",
            "severity",
            "additional_symptoms",
            "previous_consultation",
            "previous_diagnosis",
            "previous_medication",
        }
    )
    state.asked["additional_symptoms"] = 2

    assert engine.next_question(state) is None


# -------------------------------------------------- ML-informed symptom asks


def test_offered_symptoms_discriminate_between_candidates(
    engine: FollowUpQuestionEngine,
) -> None:
    """A symptom shared by every candidate cannot tell them apart."""
    state = AssessmentState(
        recognised_symptoms=["headache"],
        duration_days=2.0,
        severity="mild",
        candidate_conditions=["Migraine", "Gastroenteritis", "Typhoid"],
    )
    state.answered.update({"duration", "severity"})

    question = engine.next_question(state)

    assert question is not None
    assert question.key == "additional_symptoms"
    assert question.symptom_options
    # Already reported, so pointless to ask about.
    assert "headache" not in question.symptom_options


def test_already_rejected_symptoms_are_not_offered_again(
    engine: FollowUpQuestionEngine,
) -> None:
    """Offering the same list twice is what made the engine loop."""
    state = AssessmentState(
        recognised_symptoms=["headache"],
        rejected_symptoms=["nausea", "vomiting", "diarrhoea"],
        duration_days=2.0,
        severity="mild",
        candidate_conditions=["Migraine", "Gastroenteritis", "Typhoid"],
    )
    state.answered.update({"duration", "severity"})

    question = engine.next_question(state)

    assert question is not None
    assert set(question.symptom_options).isdisjoint({"nausea", "vomiting", "diarrhoea"})


def test_no_symptom_question_once_enough_are_known(
    engine: FollowUpQuestionEngine,
) -> None:
    """Phase 4 measured accuracy flattening around six symptoms."""
    state = AssessmentState(
        recognised_symptoms=["headache", "nausea", "vomiting", "high_fever", "chills", "fatigue"],
        duration_days=2.0,
        severity="mild",
        candidate_conditions=list(CONDITION_SYMPTOMS),
    )
    state.answered.update({"duration", "severity"})

    question = engine.next_question(state)

    assert question is None or question.key != "additional_symptoms"


def test_no_symptom_question_without_candidates(engine: FollowUpQuestionEngine) -> None:
    """With no prediction to refine there is nothing informative to offer."""
    state = AssessmentState(recognised_symptoms=["headache"], duration_days=2.0, severity="mild")
    state.answered.update({"duration", "severity"})

    question = engine.next_question(state)

    assert question is None or question.key != "additional_symptoms"


def test_engine_works_without_a_model(engine: FollowUpQuestionEngine) -> None:
    """Questions must still function when no artifacts are present."""
    bare = FollowUpQuestionEngine(condition_symptoms={})
    state = AssessmentState(recognised_symptoms=["headache"])

    question = bare.next_question(state)

    assert question is not None
    assert question.key == "duration"
