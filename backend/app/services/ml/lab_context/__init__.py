"""Laboratory results as assessment evidence.

Lab values sit **beside** a model prediction, never inside it. The condition
model is trained on symptoms only, so concatenating haemoglobin into its feature
vector would produce a model that appears multimodal while having learned
nothing from the number. That is the "fake multimodal" this project's brief
explicitly rules out.

What lab results legitimately do:

* **Get shown**, labelled as extracted from the document, next to predictions
  that are labelled as produced by the model.
* **Steer the questions.** An abnormal value makes certain symptoms worth
  asking about — a prompt, never a conclusion.
"""

from app.services.ml.lab_context.service import (
    LabContext,
    LabContextService,
    LabFinding,
    get_lab_context_service,
)

__all__ = [
    "LabContext",
    "LabContextService",
    "LabFinding",
    "get_lab_context_service",
]
