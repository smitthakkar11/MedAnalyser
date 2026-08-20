"""Decide what to ask next.

The engine walks the rule table in order and returns the first question whose
condition holds. Anything already answered is skipped, so the user is never
asked something they have told us — including facts the extractor pulled out of
their free text.

One question is chosen with help from the model: `additional_symptoms` asks
about symptoms that would best separate the current candidate conditions,
rather than about symptoms in arbitrary order. That is where the measured
robustness result from Phase 4 pays off — accuracy climbs steeply between one
and five reported symptoms, so eliciting the *right* extra symptom is the single
most valuable thing the intake can do.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.services.ml.followup.rules import QuestionRule, load_rules

#: How many symptoms to offer in one `additional_symptoms` question.
SYMPTOM_CHOICES_PER_QUESTION = 6

#: Stop asking for more symptoms once the model has enough to work with.
#: Phase 4 measured accuracy at ~0.79 with three symptoms and ~1.00 with a full
#: set; six is where the curve has flattened.
SYMPTOM_SUFFICIENCY_TARGET = 6


@dataclass
class AssessmentState:
    """Everything known about an in-progress assessment.

    Implements the `State` protocol the rule predicates read. `answered` records
    which fields have been *asked and answered*, which is distinct from a field
    being falsy — "no, I have not seen a doctor" is an answer.
    """

    recognised_symptoms: list[str] = field(default_factory=list)
    rejected_symptoms: list[str] = field(default_factory=list)
    duration_days: float | None = None
    severity: str | None = None
    previous_consultation: bool | None = None
    previous_diagnosis: str | None = None
    previous_medication: str | None = None
    treatment_response: str | None = None
    still_taking_medication: bool | None = None
    #: Candidate conditions from the latest prediction, best first.
    candidate_conditions: list[str] = field(default_factory=list)
    #: Symptoms worth asking about because an attached report is out of range.
    #: Populated from lab evidence, never from the model.
    lab_prompted_symptoms: list[str] = field(default_factory=list)
    #: Question keys already asked, with how many times.
    asked: Counter[str] = field(default_factory=Counter)
    answered: set[str] = field(default_factory=set)

    def value_of(self, name: str) -> Any:
        if name == "recognised_symptom_count":
            return len(self.recognised_symptoms)
        if name == "candidate_symptoms_available":
            return bool(self.candidate_conditions)
        if name == "lab_prompts_available":
            return bool(self._unasked_lab_prompts())
        return getattr(self, name, None)

    def is_answered(self, name: str) -> bool:
        if name in (
            "recognised_symptom_count",
            "candidate_symptoms_available",
            "lab_prompts_available",
        ):
            return True
        return name in self.answered

    def _unasked_lab_prompts(self) -> list[str]:
        """Lab-prompted symptoms the user has not already settled either way."""
        settled = set(self.recognised_symptoms) | set(self.rejected_symptoms)
        return [symptom for symptom in self.lab_prompted_symptoms if symptom not in settled]

    def record_answer(self, key: str, value: Any) -> None:
        """Mark *key* answered and store the value if it maps to a field."""
        self.answered.add(key)
        if hasattr(self, key):
            setattr(self, key, value)


@dataclass(frozen=True)
class FollowUpQuestion:
    """A question to put to the user."""

    key: str
    text: str
    answer_type: str
    help_text: str | None = None
    choices: tuple[str, ...] = ()
    #: For `symptom_check`, the canonical symptoms being offered.
    symptom_options: tuple[str, ...] = ()


class FollowUpQuestionEngine:
    """Chooses the next question, or none when the intake has what it needs."""

    def __init__(
        self,
        rules: list[QuestionRule] | None = None,
        condition_symptoms: dict[str, list[str]] | None = None,
    ) -> None:
        self._rules = rules if rules is not None else load_rules()
        # Injectable so the engine is testable without model artifacts.
        self._condition_symptoms = condition_symptoms or {}

    @property
    def question_keys(self) -> list[str]:
        return [rule.key for rule in self._rules]

    def next_question(self, state: AssessmentState) -> FollowUpQuestion | None:
        """The first applicable unanswered question, or None when done."""
        for rule in self._rules:
            if state.asked[rule.key] >= (rule.max_repeats if rule.repeatable else 1):
                continue
            if not rule.repeatable and rule.key in state.answered:
                continue
            if not rule.applies_to(state):
                continue

            if rule.answer_type == "symptom_check":
                options = (
                    state._unasked_lab_prompts()
                    if rule.key == "lab_prompted_symptoms"
                    else self._discriminating_symptoms(state)
                )
                if not options:
                    # Nothing useful left to offer; do not ask an empty question.
                    continue
                return FollowUpQuestion(
                    key=rule.key,
                    text=rule.text,
                    answer_type=rule.answer_type,
                    help_text=rule.help_text,
                    symptom_options=tuple(options),
                )

            return FollowUpQuestion(
                key=rule.key,
                text=rule.text,
                answer_type=rule.answer_type,
                help_text=rule.help_text,
                choices=rule.choices,
            )
        return None

    def _discriminating_symptoms(self, state: AssessmentState) -> list[str]:
        """Symptoms that would best separate the current candidates.

        A symptom present in *some* candidate conditions but not all carries
        information; one shared by every candidate cannot tell them apart, and
        one in none of them is irrelevant. Ranked by how close a symptom comes
        to splitting the candidate set in half.
        """
        if len(state.recognised_symptoms) >= SYMPTOM_SUFFICIENCY_TARGET:
            return []

        already_covered = set(state.recognised_symptoms) | set(state.rejected_symptoms)
        candidates = [
            condition
            for condition in state.candidate_conditions
            if condition in self._condition_symptoms
        ]
        if len(candidates) < 2:
            return []

        occurrences: Counter[str] = Counter()
        for condition in candidates:
            for symptom in self._condition_symptoms[condition]:
                if symptom not in already_covered:
                    occurrences[symptom] += 1

        half = len(candidates) / 2
        ranked = sorted(
            occurrences.items(),
            # Closest to splitting the candidates evenly, then most common.
            key=lambda item: (abs(item[1] - half), -item[1], item[0]),
        )
        return [symptom for symptom, _ in ranked[:SYMPTOM_CHOICES_PER_QUESTION]]


@lru_cache(maxsize=1)
def get_question_engine() -> FollowUpQuestionEngine:
    """Process-wide engine, wired to the trained model's condition map."""
    condition_symptoms: dict[str, list[str]] = {}
    try:
        from app.services.ml.condition_prediction.model_loader import get_condition_model

        condition_symptoms = get_condition_model().metadata.get("condition_symptoms", {})
    except Exception:  # noqa: BLE001 - questions still work without the model
        condition_symptoms = {}
    return FollowUpQuestionEngine(condition_symptoms=condition_symptoms)
