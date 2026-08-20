"""Laboratory value extraction from report text.

Two properties are non-negotiable and drive most of these tests: a value that
is not on the page must never appear in the output, and abnormality must only
ever be judged against a range the report itself printed.
"""

from __future__ import annotations

import json

import pytest

from app.services.reports.lab_extractor import (
    DATA_FILE,
    Flag,
    LabExtractor,
    get_lab_extractor,
)


@pytest.fixture(scope="module")
def extractor() -> LabExtractor:
    return get_lab_extractor()


# ------------------------------------------------------------------- parsing


def test_the_specification_example(extractor: LabExtractor) -> None:
    """The exact input from the project specification."""
    text = "Hemoglobin: 10.8 g/dL\nWBC: 13,500 /μL\nPlatelets: 180,000 /μL"

    values = {value.analyte: value.value for value in extractor.extract(text)}

    assert values == {"hemoglobin": 10.8, "wbc": 13500.0, "platelets": 180000.0}


@pytest.mark.parametrize(
    ("line", "analyte", "value"),
    [
        ("Haemoglobin 12.4 g/dL", "hemoglobin", 12.4),
        ("Hb        11.0 g/dL", "hemoglobin", 11.0),
        ("Total Leucocyte Count  9,200 /cumm", "wbc", 9200.0),
        ("SGPT (ALT)   42 U/L", "alt", 42.0),
        ("Serum Creatinine: 1.1 mg/dL", "creatinine", 1.1),
        ("TSH 2.9 uIU/mL", "tsh", 2.9),
        ("Vitamin D 18 ng/mL", "vitamin_d", 18.0),
        ("HbA1c 6.4 %", "hba1c", 6.4),
    ],
)
def test_common_report_lines(
    extractor: LabExtractor, line: str, analyte: str, value: float
) -> None:
    extracted = extractor.extract(line)

    assert len(extracted) == 1
    assert extracted[0].analyte == analyte
    assert extracted[0].value == value


def test_thousands_separators_are_parsed(extractor: LabExtractor) -> None:
    assert extractor.extract("Platelets 2,50,000 /uL")[0].value == 250000.0


def test_longest_alias_wins(extractor: LabExtractor) -> None:
    """ "Total bilirubin" must not be read as plain "bilirubin"."""
    extracted = extractor.extract("Total Bilirubin 1.4 mg/dL")

    assert extracted[0].analyte == "bilirubin_total"


def test_unknown_analytes_are_ignored_not_guessed(extractor: LabExtractor) -> None:
    assert extractor.extract("Unobtainium Level 42 mg/dL") == []


def test_a_label_with_no_number_yields_nothing(extractor: LabExtractor) -> None:
    """A test that was ordered but has no result must not become a value."""
    assert extractor.extract("Hemoglobin  ---  pending") == []


def test_the_first_occurrence_wins(extractor: LabExtractor) -> None:
    """Reports repeat analytes in a summary; the detail row comes first."""
    text = "Hemoglobin 10.8 g/dL\nSummary\nHemoglobin 99.9 g/dL"

    extracted = extractor.extract(text)

    assert len(extracted) == 1
    assert extracted[0].value == 10.8


def test_values_are_read_per_line(extractor: LabExtractor) -> None:
    """A label must not be paired with the next row's number."""
    text = "Hemoglobin\n13,500"

    assert extractor.extract(text) == []


def test_the_source_line_is_kept(extractor: LabExtractor) -> None:
    """The user must be able to check what was read."""
    extracted = extractor.extract("Hemoglobin 10.8 g/dL  (13.0 - 17.0)")

    assert "Hemoglobin" in extracted[0].source_line


# ---------------------------------------------------------- reference ranges


@pytest.mark.parametrize(
    ("line", "low", "high", "flag"),
    [
        ("Hemoglobin 10.8 g/dL 13.0 - 17.0", 13.0, 17.0, Flag.LOW),
        ("Hemoglobin 15.0 g/dL 13.0 - 17.0", 13.0, 17.0, Flag.NORMAL),
        ("Hemoglobin 18.2 g/dL 13.0 - 17.0", 13.0, 17.0, Flag.HIGH),
        ("WBC 13500 /uL 4000 - 11000", 4000.0, 11000.0, Flag.HIGH),
        ("WBC 9000 /uL 4000 to 11000", 4000.0, 11000.0, Flag.NORMAL),
        ("Platelets 180000 /uL 150000 - 410000", 150000.0, 410000.0, Flag.NORMAL),
    ],
)
def test_printed_ranges_drive_the_flag(
    extractor: LabExtractor, line: str, low: float, high: float, flag: Flag
) -> None:
    extracted = extractor.extract(line)[0]

    assert extracted.reference_low == low
    assert extracted.reference_high == high
    assert extracted.flag == flag


def test_large_ranges_are_not_truncated(extractor: LabExtractor) -> None:
    """Regression: a range regex capped at three digits read "150000 - 410000"
    as "150000 - 410", which mis-flagged a normal platelet count as high."""
    extracted = extractor.extract("Platelets 180000 /uL 150000 - 410000")[0]

    assert extracted.reference_high == 410000.0
    assert extracted.flag == Flag.NORMAL


def test_open_ended_ranges(extractor: LabExtractor) -> None:
    below = extractor.extract("SGPT 65 U/L < 50")[0]
    above = extractor.extract("HDL Cholesterol 32 mg/dL > 40")[0]

    assert below.reference_high == 50.0 and below.flag == Flag.HIGH
    assert above.reference_low == 40.0 and above.flag == Flag.LOW


def test_no_printed_range_means_no_judgement(extractor: LabExtractor) -> None:
    """MedAnalyser supplies no normal ranges of its own.

    Ranges vary by laboratory, assay, age and sex, so a value with no printed
    range is recorded and left unflagged rather than judged.
    """
    extracted = extractor.extract("Hemoglobin 10.8 g/dL")[0]

    assert extracted.reference_low is None
    assert extracted.reference_high is None
    assert extracted.flag == Flag.UNKNOWN


def test_the_reference_range_is_not_mistaken_for_the_value(
    extractor: LabExtractor,
) -> None:
    extracted = extractor.extract("Hemoglobin  13.0 - 17.0  10.8 g/dL")[0]

    assert extracted.value == 10.8


def test_the_data_file_declares_no_reference_ranges() -> None:
    """A hard-coded normal range would be a clinical judgement this project is
    not entitled to make."""
    payload = DATA_FILE.read_text().lower()

    assert "reference_low" not in payload
    assert "reference_high" not in payload
    assert "normal_range" not in payload


# ---------------------------------------------------------------------- units


def test_known_unit_spellings_are_normalised(extractor: LabExtractor) -> None:
    assert extractor.extract("Hemoglobin 10.8 gm/dl")[0].unit == "g/dL"
    assert extractor.extract("WBC 9000 cells/cumm")[0].unit == "/uL"


def test_an_unrecognised_unit_is_kept_and_flagged(extractor: LabExtractor) -> None:
    """Silently treating mg/dL as g/dL would change the number a thousandfold."""
    extracted = extractor.extract("Hemoglobin 108 mg/dL")[0]

    assert extracted.unit == "mg/dL"
    assert extracted.unit_unrecognised is True


def test_a_missing_unit_is_absent_not_assumed(extractor: LabExtractor) -> None:
    extracted = extractor.extract("Hemoglobin 10.8")[0]

    assert extracted.unit is None
    assert extracted.unit_unrecognised is False


# ------------------------------------------------------------- the data file


def test_no_duplicate_analyte_keys() -> None:
    """JSON keeps the last of duplicate keys, silently discarding aliases."""
    import collections

    duplicates: list[str] = []

    def hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        counts = collections.Counter(key for key, _ in pairs)
        duplicates.extend(key for key, count in counts.items() if count > 1)
        return dict(pairs)

    json.loads(DATA_FILE.read_text(), object_pairs_hook=hook)

    assert duplicates == []


def test_no_alias_belongs_to_two_analytes() -> None:
    """An ambiguous alias would silently attribute a value to the wrong test."""
    analytes = json.loads(DATA_FILE.read_text())["analytes"]
    owner: dict[str, str] = {}
    collisions: list[tuple[str, str, str]] = []

    for key, entry in analytes.items():
        for alias in [key.replace("_", " "), *entry["aliases"]]:
            if alias in owner and owner[alias] != key:
                collisions.append((alias, owner[alias], key))
            owner[alias] = key

    assert collisions == []


def test_every_analyte_declares_a_unit() -> None:
    analytes = json.loads(DATA_FILE.read_text())["analytes"]

    assert all(entry.get("unit") for entry in analytes.values())


def test_extractor_is_cached(extractor: LabExtractor) -> None:
    assert get_lab_extractor() is extractor
