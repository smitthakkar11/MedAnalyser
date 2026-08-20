"""Feature construction for the condition model.

**This module is imported by the training script as well as the API.** Keeping
one implementation is what guarantees that a symptom vector built at inference
time is identical to the one the model was fitted on — the single most common
source of silent train/serve skew.

The representation is a multi-hot vector over a fixed symptom vocabulary. The
vocabulary is derived from the *training split only* and saved alongside the
model; unseen symptoms are ignored rather than silently shifting the columns.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

import numpy as np

#: Collapses whitespace, underscores and repeated separators.
_SEPARATORS = re.compile(r"[\s_\-]+")


def normalise_symptom(raw: str) -> str:
    """Canonicalise one symptom token.

    The source data is inconsistent — leading spaces, double spaces, and typos
    such as ``"dischromic _patches"``. Everything is folded to
    ``lower_snake_case`` so that the same symptom written two ways maps to one
    feature.

        >>> normalise_symptom(" dischromic _patches")
        'dischromic_patches'
        >>> normalise_symptom("Skin Rash")
        'skin_rash'
    """
    return _SEPARATORS.sub("_", raw.strip().lower()).strip("_")


def normalise_label(raw: str) -> str:
    """Canonicalise a disease label, collapsing the source's double spaces."""
    return re.sub(r"\s+", " ", raw.strip())


class SymptomVectoriser:
    """Turns a set of symptom names into a fixed-width multi-hot vector.

    Deliberately not a scikit-learn transformer subclass: it is small, exactly
    what is needed, and trivially serialisable. It is fitted on the training
    split and then reused verbatim at inference.
    """

    def __init__(self, vocabulary: Sequence[str]) -> None:
        #: Ordered feature names; index in this list is the column index.
        self.vocabulary: list[str] = list(vocabulary)
        self._index = {name: i for i, name in enumerate(self.vocabulary)}

    @classmethod
    def fit(cls, symptom_sets: Iterable[Iterable[str]]) -> SymptomVectoriser:
        """Build a vocabulary from training symptom sets only.

        Fitting on the full dataset before splitting would leak information
        about the test split into the feature space.
        """
        seen: set[str] = set()
        for symptoms in symptom_sets:
            seen.update(normalise_symptom(symptom) for symptom in symptoms if symptom)
        seen.discard("")
        return cls(sorted(seen))

    @property
    def n_features(self) -> int:
        return len(self.vocabulary)

    def transform_one(self, symptoms: Iterable[str]) -> np.ndarray:
        """Vectorise a single symptom set."""
        vector = np.zeros(self.n_features, dtype=np.float32)
        for symptom in symptoms:
            index = self._index.get(normalise_symptom(symptom))
            if index is not None:
                vector[index] = 1.0
        return vector

    def transform(self, symptom_sets: Iterable[Iterable[str]]) -> np.ndarray:
        """Vectorise many symptom sets into a 2-D array."""
        rows = [self.transform_one(symptoms) for symptoms in symptom_sets]
        if not rows:
            return np.zeros((0, self.n_features), dtype=np.float32)
        return np.vstack(rows)

    def known(self, symptoms: Iterable[str]) -> list[str]:
        """Return the symptoms present in the vocabulary, canonicalised."""
        return [
            normalised
            for symptom in symptoms
            if (normalised := normalise_symptom(symptom)) in self._index
        ]

    def unknown(self, symptoms: Iterable[str]) -> list[str]:
        """Return symptoms the model has no feature for.

        Surfaced to the caller rather than dropped silently: a prediction made
        while ignoring half the user's input should be visibly caveated.
        """
        return [
            normalised
            for symptom in symptoms
            if (normalised := normalise_symptom(symptom)) and normalised not in self._index
        ]
