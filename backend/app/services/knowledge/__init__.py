"""Curated treatment and medication information.

Retrieved by predicted condition. This package describes what a class of
medicine is generally for and what is worth discussing with a doctor — it does
not prescribe, does not state doses, and never tells anyone to start, stop or
change a medicine.

It is also where the user's own allergy list is put to work: information about a
medication class they react to is flagged rather than shown flat.
"""

from app.services.knowledge.service import (
    ConditionKnowledge,
    KnowledgeService,
    MedicationInfo,
    get_knowledge_service,
)

__all__ = [
    "ConditionKnowledge",
    "KnowledgeService",
    "MedicationInfo",
    "get_knowledge_service",
]
