"""Metric helpers.

Accuracy alone is the wrong headline for an imbalanced multi-class medical
problem: a model can look strong while failing every rare class. Macro-averaged
F1 weights each disease equally regardless of how many cases it has, so it is
what model selection uses.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)


@dataclass(frozen=True)
class Scores:
    """Headline metrics for one model on one split."""

    accuracy: float
    precision_macro: float
    recall_macro: float
    f1_macro: float
    f1_weighted: float

    def as_dict(self) -> dict[str, float]:
        return {key: round(value, 4) for key, value in asdict(self).items()}


def score(y_true: np.ndarray, y_pred: np.ndarray) -> Scores:
    """Compute headline metrics.

    `zero_division=0` keeps a class the model never predicts at 0 rather than
    raising — that is a real result worth seeing, not an error to suppress.
    """
    common = {"average": "macro", "zero_division": 0}
    return Scores(
        accuracy=float(accuracy_score(y_true, y_pred)),
        precision_macro=float(precision_score(y_true, y_pred, **common)),
        recall_macro=float(recall_score(y_true, y_pred, **common)),
        f1_macro=float(f1_score(y_true, y_pred, **common)),
        f1_weighted=float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
    )


def top_k_accuracy(probabilities: np.ndarray, y_true: np.ndarray, k: int) -> float:
    """Share of cases whose true label is in the model's top *k* predictions.

    The product surfaces several candidate conditions rather than one answer,
    so top-k reflects what the user actually sees.
    """
    if probabilities.size == 0:
        return 0.0
    top = np.argsort(-probabilities, axis=1)[:, :k]
    return float(np.mean([y_true[i] in top[i] for i in range(len(y_true))]))
