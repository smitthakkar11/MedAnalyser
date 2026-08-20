"""Dataset loading and deduplication.

Deduplication is the load-bearing step of this pipeline: without it, 93.8% of
the source rows are duplicates and any train/test split leaks. These tests run
against a synthetic fixture file so they neither require the download nor break
if upstream changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# The offline ML workspace lives outside the installed application package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.dataset import load_cases, load_raw_cases  # noqa: E402

RAW_CSV = """Disease,Symptom_1,Symptom_2,Symptom_3
Fungal infection,itching, skin_rash, dischromic _patches
Fungal infection,itching, skin_rash, dischromic _patches
Fungal infection,itching, skin_rash,
Migraine,headache, nausea,
Migraine,headache, nausea,
Migraine, HEADACHE , nausea,
Migraine,headache,,
Empty case,,,
"""


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    (tmp_path / "dataset.csv").write_text(RAW_CSV)
    return tmp_path


def test_missing_dataset_gives_an_actionable_error(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="python -m ml.ingest"):
        load_cases(tmp_path)


def test_exact_duplicates_are_removed(raw_dir: Path) -> None:
    cases, stats = load_cases(raw_dir)

    # 7 rows carry symptoms; 4 distinct cases survive.
    assert stats.raw_rows == 7
    assert stats.unique_cases == 4
    assert stats.duplicate_rows == 3
    assert len(cases) == 4


def test_duplicates_differing_only_in_formatting_are_removed(raw_dir: Path) -> None:
    """ " HEADACHE " and "headache" are the same symptom, so those rows are one case."""
    cases, _ = load_cases(raw_dir)

    migraine = [case for case in cases if case.label == "Migraine"]
    symptom_sets = [case.symptoms for case in migraine]
    assert len(symptom_sets) == len(set(symptom_sets))
    assert frozenset({"headache", "nausea"}) in symptom_sets


def test_rows_without_symptoms_are_discarded(raw_dir: Path) -> None:
    """A row with no features cannot be vectorised and carries no signal."""
    cases, _ = load_cases(raw_dir)

    assert all(case.symptoms for case in cases)
    assert "Empty case" not in {case.label for case in cases}


def test_symptoms_are_normalised_on_load(raw_dir: Path) -> None:
    cases, _ = load_cases(raw_dir)

    every_symptom = {symptom for case in cases for symptom in case.symptoms}
    assert "dischromic_patches" in every_symptom
    assert not any(symptom != symptom.strip() for symptom in every_symptom)
    assert not any(symptom.upper() == symptom and symptom.isalpha() for symptom in every_symptom)


def test_stats_describe_the_cleaned_data(raw_dir: Path) -> None:
    _, stats = load_cases(raw_dir)

    assert stats.n_labels == 2
    assert stats.duplicate_fraction == pytest.approx(3 / 7)
    assert sum(stats.label_counts.values()) == stats.unique_cases


def test_label_ambiguity_is_detected() -> None:
    """If one symptom set maps to two diseases, the label is not a function of
    the features — and any accuracy figure needs that caveat."""
    import tempfile

    ambiguous = "Disease,Symptom_1,Symptom_2\nDisease A,fever,cough\nDisease B,fever,cough\n"
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        (path / "dataset.csv").write_text(ambiguous)

        _, stats = load_cases(path)

    assert stats.ambiguous_symptom_sets == 1


def test_raw_loader_keeps_duplicates(raw_dir: Path) -> None:
    """The leakage demonstration needs the un-deduplicated population."""
    raw = load_raw_cases(raw_dir)

    assert len(raw) == 7
    assert len(set(raw)) == 4


def test_cases_are_hashable_so_overlap_can_be_measured(raw_dir: Path) -> None:
    """Set arithmetic over cases is how train/test overlap is quantified."""
    cases, _ = load_cases(raw_dir)

    assert len(set(cases)) == len(cases)
    assert set(cases[:2]) & set(cases[1:]) == {cases[1]}
