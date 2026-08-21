"""The red-flag engine.

    symptoms + the user's own words + severity + duration
        ↓
    every rule evaluated, independently of the model
        ↓
    the highest level any rule reached

The engine is intentionally dumb. It does no inference, has no thresholds it
invented, and cannot be persuaded. Every finding it reports carries the rule
that produced it and the public guidance that rule came from, so a clinician
reviewing this project can check each one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import lru_cache

from app.services.ml.feature_extraction import get_symptom_extractor
from app.services.safety.rules import RedFlagRule, SafetyLevel, load_rules

logger = logging.getLogger(__name__)


#: The one message shown above everything else, per level. Defined here rather
#: than at the call site so the stored record and a freshly computed result can
#: never word the same warning differently.
HEADLINES: dict[SafetyLevel, str] = {
    SafetyLevel.NONE: "",
    SafetyLevel.URGENT: (
        "What you have described should be looked at by a doctor today. "
        "Do not wait to see whether it settles."
    ),
    SafetyLevel.EMERGENCY: (
        "What you have described may indicate a serious medical problem. "
        "Do not rely on this assessment — seek emergency medical care now."
    ),
}


def headline_for(level: SafetyLevel | str) -> str:
    """The warning text for a level, accepting the stored string form."""
    resolved = level if isinstance(level, SafetyLevel) else SafetyLevel(level)
    return HEADLINES[resolved]


@dataclass(frozen=True)
class TriggeredRule:
    """A rule that fired, and why it is being shown."""

    id: str
    level: SafetyLevel
    title: str
    advice: str
    source: str
    source_url: str


@dataclass
class SafetyAssessment:
    """The outcome of running every rule.

    ``level`` is the highest any rule reached. It is never softened: a single
    emergency finding alongside five urgent ones is still an emergency.
    """

    level: SafetyLevel = SafetyLevel.NONE
    triggered: list[TriggeredRule] = field(default_factory=list)

    @property
    def is_emergency(self) -> bool:
        return self.level is SafetyLevel.EMERGENCY

    @property
    def needs_attention(self) -> bool:
        return self.level is not SafetyLevel.NONE

    @property
    def headline(self) -> str:
        """The single message to show above everything else."""
        return headline_for(self.level)


class SafetyRuleEngine:
    """Evaluates red-flag rules against an assessment's inputs."""

    def __init__(self, rules: list[RedFlagRule] | None = None) -> None:
        self._rules = rules if rules is not None else load_rules()

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    def evaluate(
        self,
        *,
        symptoms: list[str] | set[str] | None = None,
        text: str = "",
        severity: str | None = None,
        duration_days: float | None = None,
    ) -> SafetyAssessment:
        """Run every rule and return the worst outcome.

        The user's raw text is checked as well as the extracted symptoms,
        because the vocabulary has no way to express "crushing", "worst headache
        of my life" or "passed out" — and those are exactly the phrases that
        matter most here.
        """
        reported = {symptom.strip().lower() for symptom in (symptoms or []) if symptom}
        normalised_text = _normalise(text)

        triggered = [
            TriggeredRule(
                id=rule.id,
                level=rule.level,
                title=rule.title,
                advice=rule.advice,
                source=rule.source,
                source_url=rule.source_url,
            )
            for rule in self._rules
            if rule.matches(
                symptoms=reported,
                text=normalised_text,
                severity=severity,
                duration_days=duration_days,
            )
        ]
        # Most urgent first, so a client rendering only the top item shows the
        # most serious one.
        triggered.sort(key=lambda item: -item.level.rank)

        level = triggered[0].level if triggered else SafetyLevel.NONE
        if triggered:
            # Rule ids only — never the user's words or symptoms.
            logger.info(
                "Red flags triggered",
                extra={"level": level.value, "rules": [item.id for item in triggered]},
            )
        return SafetyAssessment(level=level, triggered=triggered)


def _normalise(text: str) -> str:
    """Fold the user's text so patterns match how people actually write.

    Reuses the symptom extractor's normalisation — contractions expanded,
    punctuation reduced to spaces — so "can't breathe" and "cant breathe" are
    the same input to a rule.
    """
    if not text:
        return ""
    return get_symptom_extractor()._normalise(text)  # noqa: SLF001


@lru_cache(maxsize=1)
def get_safety_engine() -> SafetyRuleEngine:
    """The process-wide engine. Compiling patterns is not free."""
    return SafetyRuleEngine()
