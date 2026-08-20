"""The rule file and its tiny predicate language.

`asked_when` expressions are parsed, not `eval`'d. The grammar is deliberately
minimal — enough to express the real dependencies between intake questions and
nothing more. Anything richer belongs in Python where it can be tested.

Supported clauses, combined with ``and``:

* ``<field> is unknown``     — not yet answered
* ``<field> is known``       — answered with anything
* ``<field> is present``     — answered with a non-empty value
* ``<field> is true`` / ``is false``
* ``<field> < N`` / ``> N``  — numeric comparison
* ``<flag>``                 — a bare boolean flag on the state
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

RULES_FILE = Path(__file__).parent / "data" / "question_rules.json"


class State(Protocol):
    """What a predicate can interrogate."""

    def value_of(self, field: str) -> Any: ...
    def is_answered(self, field: str) -> bool: ...


class RuleSyntaxError(ValueError):
    """Raised when a rule file contains an expression the engine cannot parse."""


@dataclass(frozen=True)
class Predicate:
    """One clause of an `asked_when` expression."""

    field: str
    operator: str
    operand: float | None = None

    def evaluate(self, state: State) -> bool:
        answered = state.is_answered(self.field)
        value = state.value_of(self.field)

        match self.operator:
            case "unknown":
                return not answered
            case "known":
                return answered
            case "present":
                return answered and value not in (None, "", [], {})
            case "true":
                return value is True
            case "false":
                return value is False
            case "flag":
                return bool(value)
            case "<":
                return self.operand is not None and _as_number(value) < self.operand
            case ">":
                return self.operand is not None and _as_number(value) > self.operand
        raise RuleSyntaxError(f"Unsupported operator: {self.operator}")


def _as_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


_CLAUSE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^(?P<field>\w+) is unknown$"), "unknown"),
    (re.compile(r"^(?P<field>\w+) is known$"), "known"),
    (re.compile(r"^(?P<field>\w+) is present$"), "present"),
    (re.compile(r"^(?P<field>\w+) is true$"), "true"),
    (re.compile(r"^(?P<field>\w+) is false$"), "false"),
    (re.compile(r"^(?P<field>\w+) < (?P<operand>[\d.]+)$"), "<"),
    (re.compile(r"^(?P<field>\w+) > (?P<operand>[\d.]+)$"), ">"),
    (re.compile(r"^(?P<field>\w+)$"), "flag"),
)


def parse_condition(expression: str) -> list[Predicate]:
    """Parse an `asked_when` expression into predicates joined by AND."""
    predicates: list[Predicate] = []
    for raw_clause in expression.split(" and "):
        clause = raw_clause.strip()
        for pattern, operator in _CLAUSE_PATTERNS:
            if match := pattern.match(clause):
                groups = match.groupdict()
                operand = groups.get("operand")
                predicates.append(
                    Predicate(
                        field=groups["field"],
                        operator=operator,
                        operand=float(operand) if operand else None,
                    )
                )
                break
        else:
            raise RuleSyntaxError(f"Cannot parse condition clause: {clause!r}")
    return predicates


@dataclass(frozen=True)
class QuestionRule:
    """One question and the condition under which it is asked."""

    key: str
    order: int
    text: str
    answer_type: str
    condition: list[Predicate]
    help_text: str | None = None
    choices: tuple[str, ...] = ()
    repeatable: bool = False
    max_repeats: int = 1

    def applies_to(self, state: State) -> bool:
        return all(predicate.evaluate(state) for predicate in self.condition)


def load_rules(path: Path = RULES_FILE) -> list[QuestionRule]:
    """Read and validate the rule file, ordered by `order`."""
    payload = json.loads(path.read_text())
    rules = [
        QuestionRule(
            key=entry["key"],
            order=int(entry["order"]),
            text=entry["text"],
            answer_type=entry["answer_type"],
            condition=parse_condition(entry["asked_when"]),
            help_text=entry.get("help"),
            choices=tuple(entry.get("choices", ())),
            repeatable=bool(entry.get("repeatable", False)),
            max_repeats=int(entry.get("max_repeats", 1)),
        )
        for entry in payload["questions"]
    ]

    keys = [rule.key for rule in rules]
    if len(keys) != len(set(keys)):
        raise RuleSyntaxError("Duplicate question keys in the rule file.")
    return sorted(rules, key=lambda rule: rule.order)
