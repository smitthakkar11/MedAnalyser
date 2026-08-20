"""Condition prediction service.

Takes the symptoms a user reported and returns a ranked list of candidate
conditions. This is the only place the trained estimator is invoked.

What this service deliberately does **not** do:

* train, or fall back to training, on any code path;
* call an external API of any kind;
* present its scores as probabilities or as a diagnosis.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence

import numpy as np

from app.services.ml.condition_prediction.model_loader import (
    LoadedModel,
    get_condition_model,
)
from app.services.ml.condition_prediction.schemas import (
    ConditionPrediction,
    ConditionPredictionResult,
)

logger = logging.getLogger(__name__)

#: How many candidates to return by default.
DEFAULT_TOP_K = 5

#: Below this many recognised symptoms the ranking is unreliable. Measured, not
#: guessed: the evaluation report records accuracy falling from ~1.00 with a
#: full symptom set to ~0.79 at three symptoms and ~0.39 at one.
MIN_INFORMATIVE_SYMPTOMS = 3

#: Contributing symptoms shown per prediction.
MAX_CONTRIBUTING_SYMPTOMS = 5


class ConditionPredictionService:
    """Ranks candidate conditions for a set of reported symptoms."""

    def __init__(self, model: LoadedModel | None = None) -> None:
        # Injectable so tests can supply a fixture model without touching disk.
        self._model = model or get_condition_model()

    @property
    def known_symptoms(self) -> list[str]:
        """The vocabulary the model understands, for UI autocomplete."""
        return list(self._model.vectoriser.vocabulary)

    @property
    def known_conditions(self) -> list[str]:
        return self._model.labels

    def predict(
        self,
        symptoms: Iterable[str],
        *,
        top_k: int = DEFAULT_TOP_K,
    ) -> ConditionPredictionResult:
        """Rank candidate conditions for *symptoms*.

        Unknown symptoms are reported back rather than silently dropped: a
        ranking produced while ignoring half the user's input needs to be
        visibly caveated, not quietly returned.
        """
        symptoms = list(symptoms)
        vectoriser = self._model.vectoriser
        recognised = sorted(set(vectoriser.known(symptoms)))
        unrecognised = sorted(set(vectoriser.unknown(symptoms)))

        if not recognised:
            # Nothing to predict from. An empty ranking is the honest answer;
            # inventing one from a zero vector would return whichever class the
            # model happens to favour by default.
            return ConditionPredictionResult(
                predictions=[],
                recognised_symptoms=[],
                unrecognised_symptoms=unrecognised,
                model_name=self._model.name,
                model_version=self._model.version,
                low_information=True,
            )

        features = vectoriser.transform_one(recognised).reshape(1, -1)
        scores = self._model.estimator.predict_proba(features)[0]
        ranked = np.argsort(-scores)[: max(1, top_k)]

        contributing = self._contributing_symptoms(recognised)
        predictions = [
            ConditionPrediction(
                condition=str(self._model.label_encoder.inverse_transform([index])[0]),
                score=round(float(scores[index]), 4),
                contributing_symptoms=contributing,
            )
            for index in ranked
            # A zero score means the model gave this class no support at all.
            if scores[index] > 0.0
        ]

        logger.info(
            "Condition prediction",
            extra={
                "model_version": self._model.version,
                "n_recognised": len(recognised),
                "n_unrecognised": len(unrecognised),
                "n_predictions": len(predictions),
            },
        )

        return ConditionPredictionResult(
            predictions=predictions,
            recognised_symptoms=recognised,
            unrecognised_symptoms=unrecognised,
            model_name=self._model.name,
            model_version=self._model.version,
            low_information=len(recognised) < MIN_INFORMATIVE_SYMPTOMS,
        )

    def _contributing_symptoms(self, recognised: Sequence[str]) -> list[str]:
        """The reported symptoms the model weighs most heavily.

        Ranked by the estimator's global feature importance, restricted to what
        the user actually reported. This is a **model explanation** — which
        inputs the model relies on — and says nothing about causation. Returns
        the symptoms unranked if the estimator exposes no importances.
        """
        importances = getattr(self._model.estimator, "feature_importances_", None)
        if importances is None:
            return list(recognised[:MAX_CONTRIBUTING_SYMPTOMS])

        vocabulary = self._model.vectoriser.vocabulary
        index_of = {name: i for i, name in enumerate(vocabulary)}
        ranked = sorted(
            recognised,
            key=lambda symptom: float(importances[index_of[symptom]]),
            reverse=True,
        )
        return ranked[:MAX_CONTRIBUTING_SYMPTOMS]
