"""Extract structured symptoms from free-text.

    "I've had a high temperature and been throwing up for 3 days, but no rash."
        ↓
    symptoms: high_fever, vomiting     (rash excluded — negated)
    duration: 3 days
    severity: None

Design notes:

* **Longest phrase wins.** "chest pain" must beat "pain"; the matcher tries
  candidates in descending length so a specific phrase is never shadowed.
* **Negation is explicit.** "no rash", "denies vomiting", "without fever" must
  not add features. Getting this wrong does not merely lose signal — it feeds
  the model the opposite of what the user said.
* **Nothing is invented.** Anything not confidently matched is reported as
  unmatched text so the caller can ask about it, never guessed at.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "symptom_synonyms.json"

#: Words that negate a symptom mentioned after them.
NEGATION_CUES = (
    "no",
    "not",
    "never",
    "without",
    "denies",
    "deny",
    "denied",
    "negative for",
    "free of",
    "absent",
    "havent",
    "haven't",
    "hasnt",
    "hasn't",
    "dont",
    "don't",
    "doesnt",
    "doesn't",
    "didnt",
    "didn't",
    "isnt",
    "isn't",
    "wasnt",
    "wasn't",
    "nor",
    "neither",
    "lack of",
    "ruled out",
    "no sign of",
    "no signs of",
)

#: Words that close a negation's scope: "no fever but a bad cough".
NEGATION_TERMINATORS = (
    "but",
    "however",
    "although",
    "though",
    "except",
    "apart from",
    "aside from",
    "yet",
    "still",
    "otherwise",
)

#: How many words after a negation cue stay negated.
NEGATION_WINDOW_WORDS = 6

SEVERITY_TERMS: dict[str, tuple[str, ...]] = {
    "mild": ("mild", "slight", "slightly", "a bit", "a little", "minor", "manageable"),
    "moderate": ("moderate", "moderately", "medium", "noticeable"),
    "severe": (
        "severe",
        "severely",
        "terrible",
        "unbearable",
        "excruciating",
        "agonising",
        "agonizing",
        "extreme",
        "extremely",
        "intense",
        "awful",
        "worst",
        "really bad",
        "very bad",
    ),
}

_DURATION_UNITS: dict[str, float] = {
    "hour": 1 / 24,
    "hours": 1 / 24,
    "hr": 1 / 24,
    "hrs": 1 / 24,
    "day": 1,
    "days": 1,
    "week": 7,
    "weeks": 7,
    "fortnight": 14,
    "month": 30,
    "months": 30,
    "year": 365,
    "years": 365,
}

_NUMBER_WORDS: dict[str, int] = {
    "a": 1,
    "an": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "couple": 2,
    "few": 3,
    "several": 4,
}

_DURATION_PATTERN = re.compile(
    r"\b(?:for|since|over|past|last|about|around)?\s*"
    r"(?P<amount>\d+|" + "|".join(_NUMBER_WORDS) + r")\s*"
    r"(?:of\s+)?(?P<unit>" + "|".join(_DURATION_UNITS) + r")\b",
)

_RELATIVE_DURATIONS: dict[str, float] = {
    "today": 1,
    "since this morning": 1,
    "this morning": 1,
    "tonight": 1,
    "yesterday": 2,
    "since yesterday": 2,
    "overnight": 1,
    "last night": 1,
    "the other day": 3,
}

#: Contractions and spellings normalised before matching.
_TEXT_FIXES = (
    (r"\bcan'?t\b", "cannot"),
    (r"\bwon'?t\b", "will not"),
    (r"\bi'?ve\b", "i have"),
    (r"\bi'?m\b", "i am"),
    (r"\bit'?s\b", "it is"),
    (r"\bthere'?s\b", "there is"),
)


@dataclass(frozen=True)
class ExtractedSymptom:
    """One symptom found in the text."""

    symptom: str
    #: The words that produced the match, for showing the user what was read.
    matched_text: str
    negated: bool = False


@dataclass
class SymptomExtraction:
    """Everything the extractor could determine from a piece of text."""

    symptoms: list[str] = field(default_factory=list)
    negated_symptoms: list[str] = field(default_factory=list)
    details: list[ExtractedSymptom] = field(default_factory=list)
    duration_days: float | None = None
    severity: str | None = None
    #: Text that matched nothing. Used to prompt, never to guess.
    unmatched_text: str = ""

    @property
    def is_empty(self) -> bool:
        return not self.symptoms


class SymptomExtractor:
    """Maps free text onto the model's canonical symptom vocabulary."""

    def __init__(self, phrase_to_symptom: dict[str, str]) -> None:
        self._phrases = phrase_to_symptom
        # Longest first so "chest pain" is tried before "pain".
        ordered = sorted(phrase_to_symptom, key=len, reverse=True)
        self._pattern = re.compile(
            r"\b(" + "|".join(re.escape(phrase) for phrase in ordered) + r")\b"
        )

    @classmethod
    def from_file(cls, path: Path = DATA_FILE) -> SymptomExtractor:
        """Build from the synonym data file.

        The canonical name (underscores as spaces) is always matchable, so the
        data file only needs to carry genuine alternative phrasings.
        """
        payload = json.loads(path.read_text())
        mapping: dict[str, str] = {}
        for symptom, synonyms in payload["symptoms"].items():
            mapping[symptom.replace("_", " ")] = symptom
            for synonym in synonyms:
                mapping[synonym.strip().lower()] = symptom
        return cls(mapping)

    @property
    def vocabulary(self) -> set[str]:
        return set(self._phrases.values())

    def extract(self, text: str) -> SymptomExtraction:
        """Pull symptoms, duration and severity out of *text*."""
        if not text or not text.strip():
            return SymptomExtraction()

        normalised = self._normalise(text)
        result = SymptomExtraction(
            duration_days=self._extract_duration(normalised),
            severity=self._extract_severity(normalised),
        )

        consumed: list[tuple[int, int]] = []
        seen: set[str] = set()
        for match in self._pattern.finditer(normalised):
            phrase = match.group(1)
            symptom = self._phrases[phrase]
            consumed.append(match.span())
            negated = self._is_negated(normalised, match.start())

            if symptom in seen:
                continue
            seen.add(symptom)
            result.details.append(
                ExtractedSymptom(symptom=symptom, matched_text=phrase, negated=negated)
            )
            (result.negated_symptoms if negated else result.symptoms).append(symptom)

        result.symptoms.sort()
        result.negated_symptoms.sort()
        result.unmatched_text = self._remaining_text(normalised, consumed)
        return result

    # ------------------------------------------------------------- internals

    @staticmethod
    def _normalise(text: str) -> str:
        lowered = text.lower()
        for pattern, replacement in _TEXT_FIXES:
            lowered = re.sub(pattern, replacement, lowered)
        # Keep letters, digits and spaces; punctuation only ever separates.
        lowered = re.sub(r"[^a-z0-9\s()]+", " ", lowered)
        return re.sub(r"\s+", " ", lowered).strip()

    def _is_negated(self, text: str, match_start: int) -> bool:
        """True when a negation cue governs the match.

        Scans backwards a fixed number of words, stopping at a terminator so
        "no fever but a cough" negates only the fever.
        """
        preceding = text[:match_start].split()
        window = preceding[-NEGATION_WINDOW_WORDS:]
        for word in reversed(window):
            if word in NEGATION_TERMINATORS:
                return False
            if word in NEGATION_CUES:
                return True
        # Multi-word cues ("negative for", "no sign of") need a substring check.
        tail = " ".join(window)
        return any(cue in tail for cue in NEGATION_CUES if " " in cue)

    @staticmethod
    def _extract_duration(text: str) -> float | None:
        for phrase, days in _RELATIVE_DURATIONS.items():
            if phrase in text:
                return days
        match = _DURATION_PATTERN.search(text)
        if not match:
            return None
        raw_amount = match.group("amount")
        amount = float(raw_amount) if raw_amount.isdigit() else _NUMBER_WORDS.get(raw_amount, 1)
        return round(amount * _DURATION_UNITS[match.group("unit")], 2)

    @staticmethod
    def _extract_severity(text: str) -> str | None:
        # Most severe wins: "mild headache but severe chest pain" is severe.
        for level in ("severe", "moderate", "mild"):
            if any(re.search(rf"\b{re.escape(term)}\b", text) for term in SEVERITY_TERMS[level]):
                return level
        return None

    @staticmethod
    def _remaining_text(text: str, consumed: list[tuple[int, int]]) -> str:
        if not consumed:
            return text
        pieces, cursor = [], 0
        for start, end in sorted(consumed):
            pieces.append(text[cursor:start])
            cursor = end
        pieces.append(text[cursor:])
        return re.sub(r"\s+", " ", " ".join(pieces)).strip()


@lru_cache(maxsize=1)
def get_symptom_extractor() -> SymptomExtractor:
    """The process-wide extractor. Building the pattern is not free."""
    return SymptomExtractor.from_file()
