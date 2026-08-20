"""Schemas for condition prediction.

Wording is deliberate. The model outputs a **score**, not a calibrated
probability: no calibration has been performed or validated, so calling these
values probabilities would overstate what they mean.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ConditionPrediction(BaseModel):
    """One candidate condition."""

    condition: str
    score: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Relative model score for this condition, not a calibrated "
            "probability and not a measure of clinical likelihood."
        ),
    )
    #: Symptoms the user reported that this model treats as most informative.
    contributing_symptoms: list[str] = Field(default_factory=list)


class ConditionPredictionResult(BaseModel):
    """The model's ranked candidates, plus what it could and could not use."""

    model_config = ConfigDict(protected_namespaces=())

    predictions: list[ConditionPrediction]
    #: Reported symptoms the model has a feature for.
    recognised_symptoms: list[str]
    #: Reported symptoms outside the model's vocabulary; ignored in the vector.
    unrecognised_symptoms: list[str]
    model_name: str
    model_version: str
    #: True when too little was recognised for the ranking to mean much.
    low_information: bool = Field(
        description=(
            "Set when fewer than three symptoms were recognised. Accuracy "
            "degrades sharply below that, so the caller should collect more "
            "before presenting results."
        )
    )
