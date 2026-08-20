"""Turning what a user writes into what the model expects.

Deliberately rule-based: a curated synonym dictionary, longest-phrase matching,
and explicit negation handling. No LLM, no external API, no statistical NLP
model. For mapping a closed vocabulary of 131 symptoms onto everyday phrasing,
rules are more accurate, instant, free, and — most importantly — inspectable:
when an extraction is wrong you can point at the line that caused it.
"""

from app.services.ml.feature_extraction.symptom_extractor import (
    ExtractedSymptom,
    SymptomExtraction,
    SymptomExtractor,
    get_symptom_extractor,
)

__all__ = [
    "ExtractedSymptom",
    "SymptomExtraction",
    "SymptomExtractor",
    "get_symptom_extractor",
]
