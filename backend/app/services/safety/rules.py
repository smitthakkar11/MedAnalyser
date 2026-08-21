"""Red-flag rule definitions and loading."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

RULES_FILE = Path(__file__).parent / "data" / "red_flags.json"

#: Ordered least to most urgent, so severities can be compared.
SEVERITY_ORDER: tuple[str, ...] = ("mild", "moderate", "severe")


class SafetyLevel(StrEnum):
    """How urgently the user should seek care.

    Ordered: `NONE < URGENT < EMERGENCY`. The engine always reports the highest
    level any rule reached — a single emergency finding is never diluted by
    other rules that only reached urgent.
    """

    NONE = "none"
    URGENT = "urgent"
    EMERGENCY = "emergency"

    @property
    def rank(self) -> int:
        return {"none": 0, "urgent": 1, "emergency": 2}[self.value]


class RuleError(ValueError):
    """Raised when the rule file is malformed."""


@dataclass(frozen=True)
class RedFlagRule:
    """One deterministic red-flag rule.

    Triggers fall into two kinds, and the distinction matters:

    * **Evidence** — `any_symptoms` and `text_patterns`. These are alternative
      routes to the same finding, so satisfying *either* is enough. Someone who
      writes "I passed out" has reported loss of consciousness just as surely as
      someone who ticks the symptom, and requiring both would silently drop the
      emergency.
    * **Constraints** — `all_symptoms`, `min_severity`, `min_duration_days`.
      Every one that is declared must hold.

    A rule fires when its evidence matches (if it declares any) and every
    constraint holds.
    """

    id: str
    level: SafetyLevel
    title: str
    advice: str
    source: str
    source_url: str
    any_symptoms: frozenset[str] = frozenset()
    all_symptoms: frozenset[str] = frozenset()
    text_patterns: tuple[re.Pattern[str], ...] = ()
    min_severity: str | None = None
    min_duration_days: float | None = None

    def matches(
        self,
        *,
        symptoms: set[str],
        text: str,
        severity: str | None,
        duration_days: float | None,
    ) -> bool:
        """True when the evidence matches and every constraint holds.

        Triggers fall into two kinds, and conflating them loses emergencies:

        * **Evidence** — `any_symptoms` and `text_patterns` are alternative
          routes to the same finding, so *either* suffices. Someone writing
          "I passed out" has reported loss of consciousness just as surely as
          someone ticking the symptom; requiring both silently drops it.
        * **Constraints** — `all_symptoms`, `min_severity` and
          `min_duration_days`. Every one declared must hold.
        """
        # --- constraints: all declared ones must hold -----------------------
        if self.all_symptoms and not self.all_symptoms <= symptoms:
            return False
        if self.min_severity is not None and (
            severity is None or _severity_rank(severity) < _severity_rank(self.min_severity)
        ):
            return False
        if self.min_duration_days is not None and (
            duration_days is None or duration_days < self.min_duration_days
        ):
            return False

        # --- evidence: either route is enough -------------------------------
        if not self.any_symptoms and not self.text_patterns:
            return True
        return bool(self.any_symptoms & symptoms) or any(
            pattern.search(text) for pattern in self.text_patterns
        )

    @property
    def is_pure_text_rule(self) -> bool:
        return bool(self.text_patterns) and not (self.any_symptoms or self.all_symptoms)


def _severity_rank(severity: str) -> int:
    try:
        return SEVERITY_ORDER.index(severity)
    except ValueError:
        return -1


def load_rules(path: Path = RULES_FILE) -> list[RedFlagRule]:
    """Read and validate the rule file.

    Validation is strict and raises: a rule that silently fails to load is a
    red flag that silently never fires.
    """
    payload = json.loads(path.read_text())
    rules: list[RedFlagRule] = []

    for entry in payload["rules"]:
        try:
            patterns = tuple(
                re.compile(pattern, re.IGNORECASE) for pattern in entry.get("text_patterns", [])
            )
        except re.error as exc:
            raise RuleError(f"Rule {entry.get('id')!r} has an invalid pattern: {exc}") from exc

        if not (entry.get("any_symptoms") or entry.get("all_symptoms") or patterns):
            raise RuleError(f"Rule {entry.get('id')!r} declares no triggers and can never fire.")
        if not entry.get("source_url"):
            raise RuleError(f"Rule {entry.get('id')!r} has no source. Every rule must cite one.")

        rules.append(
            RedFlagRule(
                id=entry["id"],
                level=SafetyLevel(entry["level"]),
                title=entry["title"],
                advice=entry["advice"],
                source=entry["source"],
                source_url=entry["source_url"],
                any_symptoms=frozenset(entry.get("any_symptoms", [])),
                all_symptoms=frozenset(entry.get("all_symptoms", [])),
                text_patterns=patterns,
                min_severity=entry.get("min_severity"),
                min_duration_days=entry.get("min_duration_days"),
            )
        )

    identifiers = [rule.id for rule in rules]
    if len(identifiers) != len(set(identifiers)):
        raise RuleError("Duplicate rule ids in the red-flag file.")
    return rules
