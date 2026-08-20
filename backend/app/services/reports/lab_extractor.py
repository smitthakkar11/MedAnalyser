"""Turn report text into structured laboratory values.

    "Hemoglobin      10.8 g/dL      (13.0 - 17.0)"
        ↓
    hemoglobin = 10.8 g/dL, reference 13.0–17.0, below range

Two rules govern everything in this module:

* **Never invent a value.** If a number is not on the page it is absent from
  the output. There is no imputation, no defaulting, no "probably".
* **Never invent a reference range.** Normal ranges vary by laboratory, assay,
  age and sex, so abnormality is decided *only* from a range printed on the
  report itself. Where the report gives none, the value is recorded and left
  unflagged rather than judged against a hard-coded number.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "lab_analytes.json"

#: A number, optionally with thousands separators or a decimal part.
#: Written as one greedy alternative rather than an alternation: an alternation
#: whose first branch caps at three digits matches only the leading "150" of
#: "150000", silently truncating a reference range to a wrong — not missing —
#: value. That would mis-flag a result as abnormal.
_NUMBER = r"\d[\d,]*(?:\.\d+)?"

#: `10.8 g/dL`, `13,500 /uL`, `4.5` — value with an optional unit.
_VALUE_UNIT = re.compile(
    # The unit may lead with "/" — "/uL", "/cumm" and "/mm3" are all real.
    rf"(?P<value>{_NUMBER})\s*(?P<unit>[a-zA-Zµμ%/][a-zA-Zµμ%/^0-9.\s-]{{0,18}})?"
)

#: `13.0 - 17.0`, `13.0–17.0`, `(4000 to 11000)`.
_RANGE = re.compile(rf"(?P<low>{_NUMBER})\s*(?:-|–|—|to)\s*(?P<high>{_NUMBER})")

#: `< 200`, `<=200`, `> 40`.
_OPEN_RANGE = re.compile(rf"(?P<op>[<>]=?)\s*(?P<bound>{_NUMBER})")


class Flag(StrEnum):
    """Where a value sits relative to the range printed on the report."""

    NORMAL = "normal"
    LOW = "low"
    HIGH = "high"
    #: No usable range was printed, so no judgement is made.
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ExtractedValue:
    """One laboratory result read off a report."""

    analyte: str
    display_name: str
    value: float
    unit: str | None
    reference_low: float | None = None
    reference_high: float | None = None
    reference_text: str | None = None
    flag: Flag = Flag.UNKNOWN
    #: True when the unit on the report was not one we recognise, so the value
    #: is stored as printed and must not be compared with other reports.
    unit_unrecognised: bool = False
    #: The line it came from, so a user can check what was read.
    source_line: str = ""


@dataclass(frozen=True)
class _Analyte:
    key: str
    display: str
    unit: str
    unit_aliases: frozenset[str]


class LabExtractor:
    """Finds known analytes and their values in report text."""

    def __init__(self, analytes: dict[str, _Analyte], alias_to_key: dict[str, str]) -> None:
        self._analytes = analytes
        self._alias_to_key = alias_to_key
        # Longest alias first: "total bilirubin" must beat "bilirubin".
        ordered = sorted(alias_to_key, key=len, reverse=True)
        self._alias_pattern = re.compile(
            r"(?<![a-z])(" + "|".join(re.escape(alias) for alias in ordered) + r")(?![a-z])"
        )

    @classmethod
    def from_file(cls, path: Path = DATA_FILE) -> LabExtractor:
        payload = json.loads(path.read_text())
        analytes: dict[str, _Analyte] = {}
        alias_to_key: dict[str, str] = {}

        for key, entry in payload["analytes"].items():
            analytes[key] = _Analyte(
                key=key,
                display=entry["display"],
                unit=entry["unit"],
                unit_aliases=frozenset(
                    alias.lower() for alias in [entry["unit"], *entry["unit_aliases"]]
                ),
            )
            # The canonical name is always matchable without being listed.
            for alias in [key.replace("_", " "), *entry["aliases"]]:
                alias_to_key[alias.lower()] = key
        return cls(analytes, alias_to_key)

    @property
    def known_analytes(self) -> list[str]:
        return sorted(self._analytes)

    def extract(self, text: str) -> list[ExtractedValue]:
        """Read every recognisable laboratory value out of *text*.

        Works line by line: lab reports are tabular, and a value belongs to the
        label on its own row. Scanning across lines invites pairing a label with
        the next row's number.
        """
        results: dict[str, ExtractedValue] = {}

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or len(line) > 300:
                continue

            match = self._alias_pattern.search(line.lower())
            if match is None:
                continue

            key = self._alias_to_key[match.group(1)]
            # Only look after the label; a leading number is a row index or a
            # date, never this analyte's result.
            remainder = line[match.end() :]
            extracted = self._read_value(self._analytes[key], remainder, line)
            # First occurrence wins: reports repeat analytes in summaries, and
            # the detail row comes first.
            if extracted is not None and key not in results:
                results[key] = extracted

        return sorted(results.values(), key=lambda item: item.display_name)

    def _read_value(
        self, analyte: _Analyte, remainder: str, source_line: str
    ) -> ExtractedValue | None:
        """Pull the result, its unit and any printed range from one row."""
        reference_low, reference_high, reference_text = _read_reference(remainder)

        # The reference range is removed before reading the result, or its
        # bounds would be mistaken for the value itself.
        without_reference = remainder
        if reference_text:
            without_reference = remainder.replace(reference_text, " ", 1)

        value_match = _VALUE_UNIT.search(without_reference)
        if value_match is None:
            return None

        try:
            value = float(value_match.group("value").replace(",", ""))
        except ValueError:
            return None

        raw_unit = (value_match.group("unit") or "").strip(" .:;)（(").strip()
        unit, unrecognised = _resolve_unit(analyte, raw_unit)

        return ExtractedValue(
            analyte=analyte.key,
            display_name=analyte.display,
            value=value,
            unit=unit,
            reference_low=reference_low,
            reference_high=reference_high,
            reference_text=reference_text,
            flag=_classify(value, reference_low, reference_high),
            unit_unrecognised=unrecognised,
            source_line=source_line[:200],
        )


def _read_reference(text: str) -> tuple[float | None, float | None, str | None]:
    """Find a reference range printed on the row, if there is one."""
    if match := _RANGE.search(text):
        try:
            low = float(match.group("low").replace(",", ""))
            high = float(match.group("high").replace(",", ""))
        except ValueError:
            return None, None, None
        if low <= high:
            return low, high, match.group(0)

    if match := _OPEN_RANGE.search(text):
        try:
            bound = float(match.group("bound").replace(",", ""))
        except ValueError:
            return None, None, None
        if match.group("op").startswith("<"):
            return None, bound, match.group(0)
        return bound, None, match.group(0)

    return None, None, None


def _resolve_unit(analyte: _Analyte, raw_unit: str) -> tuple[str | None, bool]:
    """Normalise the unit, or keep it verbatim and say so.

    A unit we do not recognise is *not* silently replaced with the canonical
    one: treating mg/dL as g/dL would change the number by a factor of a
    thousand while looking perfectly fine.
    """
    if not raw_unit:
        return None, False

    cleaned = re.sub(r"\s+", "", raw_unit).lower()
    for alias in analyte.unit_aliases:
        if re.sub(r"\s+", "", alias).lower() == cleaned:
            return analyte.unit, False
    return raw_unit, True


def _classify(value: float, low: float | None, high: float | None) -> Flag:
    """Compare a value against the range printed on the report.

    Returns ``UNKNOWN`` when no range was printed. Guessing one would be
    inventing a clinical judgement the report did not make.
    """
    if low is None and high is None:
        return Flag.UNKNOWN
    if low is not None and value < low:
        return Flag.LOW
    if high is not None and value > high:
        return Flag.HIGH
    return Flag.NORMAL


@lru_cache(maxsize=1)
def get_lab_extractor() -> LabExtractor:
    """Process-wide extractor; compiling the alias pattern is not free."""
    return LabExtractor.from_file()
