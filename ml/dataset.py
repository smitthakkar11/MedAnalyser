"""Load and clean the disease–symptom dataset.

The raw file is one row per case with up to 17 free-form symptom columns. This
module turns it into a tidy structure — one record of ``(label, symptom set)``
— and, critically, **deduplicates it**.

Why deduplication matters here is documented at length in `ml/README.md`: the
source contains exactly 120 rows per disease, 93.8% of which are exact
duplicates of another row. Splitting before removing them puts copies of the
same record in both train and test, which is textbook leakage and produces a
meaningless ~100% score.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.services.ml.condition_prediction.features import normalise_label, normalise_symptom
from ml.config import RAW_DIR

DATASET_FILE = "dataset.csv"
LABEL_COLUMN = "Disease"


@dataclass(frozen=True)
class Case:
    """One deduplicated case: a disease and the symptom set that describes it."""

    label: str
    symptoms: frozenset[str]


@dataclass
class DatasetStats:
    """Facts about the load, reported by EDA and the training run."""

    raw_rows: int
    duplicate_rows: int
    unique_cases: int
    n_labels: int
    n_symptoms: int
    ambiguous_symptom_sets: int
    label_counts: dict[str, int]

    @property
    def duplicate_fraction(self) -> float:
        return self.duplicate_rows / self.raw_rows if self.raw_rows else 0.0


def _read_raw(raw_dir: Path) -> pd.DataFrame:
    path = raw_dir / DATASET_FILE
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python -m ml.ingest` first to download the dataset."
        )
    return pd.read_csv(path)


def load_raw_cases(raw_dir: Path = RAW_DIR) -> list[Case]:
    """Every row as-is, duplicates included.

    Only used to demonstrate how much score inflation the deduplication step
    prevents. Never used for training.
    """
    frame = _read_raw(raw_dir)
    symptom_columns = [column for column in frame.columns if column != LABEL_COLUMN]
    records: list[Case] = []
    for row in frame.itertuples(index=False):
        values = row._asdict()
        label = normalise_label(str(values[LABEL_COLUMN]))
        symptoms = {
            normalised
            for column in symptom_columns
            if isinstance(value := values[column], str)
            and (normalised := normalise_symptom(value))
        }
        if label and symptoms:
            records.append(Case(label=label, symptoms=frozenset(symptoms)))
    return records


def load_cases(raw_dir: Path = RAW_DIR) -> tuple[list[Case], DatasetStats]:
    """Return deduplicated cases plus the statistics describing the cleanup."""
    frame = _read_raw(raw_dir)
    symptom_columns = [column for column in frame.columns if column != LABEL_COLUMN]

    raw_records: list[Case] = []
    for row in frame.itertuples(index=False):
        values = row._asdict()
        label = normalise_label(str(values[LABEL_COLUMN]))
        symptoms = {
            normalised
            for column in symptom_columns
            if isinstance(value := values[column], str)
            and (normalised := normalise_symptom(value))
        }
        # A row with no symptoms carries no signal and cannot be vectorised.
        if label and symptoms:
            raw_records.append(Case(label=label, symptoms=frozenset(symptoms)))

    unique = sorted(set(raw_records), key=lambda case: (case.label, sorted(case.symptoms)))

    # A symptom set mapping to more than one disease means the label is not a
    # function of the features — worth knowing before trusting any accuracy.
    by_symptoms: dict[frozenset[str], set[str]] = {}
    for case in unique:
        by_symptoms.setdefault(case.symptoms, set()).add(case.label)
    ambiguous = sum(1 for labels in by_symptoms.values() if len(labels) > 1)

    stats = DatasetStats(
        raw_rows=len(raw_records),
        duplicate_rows=len(raw_records) - len(unique),
        unique_cases=len(unique),
        n_labels=len({case.label for case in unique}),
        n_symptoms=len({symptom for case in unique for symptom in case.symptoms}),
        ambiguous_symptom_sets=ambiguous,
        label_counts=dict(sorted(Counter(case.label for case in unique).items())),
    )
    return unique, stats


def load_symptom_severity(raw_dir: Path = RAW_DIR) -> dict[str, int]:
    """Symptom -> severity weight, from the dataset's companion file.

    Not a model feature: used later by the safety layer and for ordering
    follow-up questions, where asking about the most severe unknown symptom
    first is more useful than asking in alphabetical order.
    """
    path = raw_dir / "Symptom-severity.csv"
    if not path.exists():
        return {}
    frame = pd.read_csv(path)
    return {
        normalise_symptom(str(row.Symptom)): int(row.weight)
        for row in frame.itertuples(index=False)
        if str(row.Symptom).strip()
    }
