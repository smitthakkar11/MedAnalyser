"""Paths and constants for the offline ML workspace."""

from __future__ import annotations

from pathlib import Path

ML_DIR = Path(__file__).resolve().parent
REPO_ROOT = ML_DIR.parent

DATA_DIR = ML_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
ARTIFACTS_DIR = ML_DIR / "artifacts"
REPORTS_DIR = ML_DIR / "reports"

#: Reproducibility. Every split, shuffle and model uses this seed.
RANDOM_SEED = 42

#: Fraction of the deduplicated dataset held out for the final evaluation.
TEST_SIZE = 0.2

#: Folds for model-selection cross-validation on the training split.
#: Four, not five: the rarest disease has 5 unique cases, so after an 80/20
#: split only 4 remain for training and 5-fold stratified CV cannot place one
#: in every fold.
CV_FOLDS = 4

for _directory in (RAW_DIR, ARTIFACTS_DIR, REPORTS_DIR):
    _directory.mkdir(parents=True, exist_ok=True)
