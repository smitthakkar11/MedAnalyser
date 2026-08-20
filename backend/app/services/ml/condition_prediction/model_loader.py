"""Load the trained condition model once per process.

Models are trained offline; the API only ever loads artifacts. Loading is
cached so a request never pays for deserialisation, and never — under any
circumstances — triggers training.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib

from app.core.config import Settings, get_settings
from app.services.ml.condition_prediction.features import SymptomVectoriser

logger = logging.getLogger(__name__)


class ModelUnavailableError(RuntimeError):
    """Raised when the artifacts are missing or cannot be loaded."""


@dataclass(frozen=True)
class LoadedModel:
    """A trained estimator with everything needed to use it."""

    estimator: Any
    vectoriser: SymptomVectoriser
    label_encoder: Any
    metadata: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.metadata.get("model_name", "condition_model"))

    @property
    def version(self) -> str:
        return str(self.metadata.get("model_version", "unknown"))

    @property
    def labels(self) -> list[str]:
        return [str(label) for label in self.label_encoder.classes_]


def _artifact_paths(settings: Settings) -> dict[str, Path]:
    base = Path(settings.ml_artifacts_path)
    stem = settings.condition_model_name
    return {
        "estimator": base / f"{stem}.joblib",
        "vectoriser": base / f"{stem}_vectoriser.joblib",
        "label_encoder": base / f"{stem}_label_encoder.joblib",
        "metadata": base / f"{stem}_metadata.json",
    }


def load_condition_model(settings: Settings | None = None) -> LoadedModel:
    """Read the artifacts from disk. Prefer :func:`get_condition_model`."""
    settings = settings or get_settings()
    paths = _artifact_paths(settings)

    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        raise ModelUnavailableError(
            f"Condition model artifacts not found in {settings.ml_artifacts_path}: "
            f"missing {', '.join(sorted(missing))}. "
            "Run `python -m ml.training.train_condition_model` to produce them."
        )

    try:
        return LoadedModel(
            estimator=joblib.load(paths["estimator"]),
            vectoriser=joblib.load(paths["vectoriser"]),
            label_encoder=joblib.load(paths["label_encoder"]),
            metadata=json.loads(paths["metadata"].read_text()),
        )
    except Exception as exc:  # noqa: BLE001 - any load failure is the same to callers
        raise ModelUnavailableError(
            f"Condition model artifacts could not be loaded: {type(exc).__name__}."
        ) from exc


@lru_cache(maxsize=1)
def get_condition_model() -> LoadedModel:
    """Return the process-wide model, loading it on first use."""
    model = load_condition_model()
    logger.info(
        "Condition model loaded",
        extra={
            "model_name": model.name,
            "model_version": model.version,
            "n_features": model.vectoriser.n_features,
            "n_labels": len(model.labels),
        },
    )
    return model


def reset_model_cache() -> None:
    """Drop the cached model. Used by tests and after a redeploy."""
    get_condition_model.cache_clear()
