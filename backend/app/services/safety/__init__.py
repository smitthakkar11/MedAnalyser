"""Deterministic red-flag detection.

This package is **deliberately outside `services/ml/`**. Its whole purpose is
to be independent of the model: a language or classification model can be
argued out of an emergency finding by unusual phrasing or a thin symptom set,
and the condition model here was trained on synthetic data with no notion of
severity at all. A rule table cannot be talked round, can be read by a
clinician, and fails loudly rather than quietly.

Safety output takes priority over every prediction. Nothing in this package
consults the model, and the model never sees its result.
"""

from app.services.safety.engine import (
    HEADLINES,
    SafetyAssessment,
    SafetyLevel,
    SafetyRuleEngine,
    TriggeredRule,
    get_safety_engine,
    headline_for,
)

__all__ = [
    "HEADLINES",
    "SafetyAssessment",
    "SafetyLevel",
    "SafetyRuleEngine",
    "TriggeredRule",
    "get_safety_engine",
    "headline_for",
]
