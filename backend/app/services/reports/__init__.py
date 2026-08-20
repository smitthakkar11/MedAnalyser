"""Medical report processing.

    PDF → text (PyMuPDF) → OCR fallback (Tesseract) → lab value extraction

Everything here is deterministic parsing. Nothing is inferred, and nothing is
filled in: a value that is not on the page does not appear in the output.
"""

from app.services.reports.lab_extractor import (
    ExtractedValue,
    LabExtractor,
    get_lab_extractor,
)
from app.services.reports.pdf_extractor import (
    ExtractedDocument,
    ExtractionMethod,
    PdfExtractionError,
    extract_document,
)

__all__ = [
    "ExtractedDocument",
    "ExtractedValue",
    "ExtractionMethod",
    "LabExtractor",
    "PdfExtractionError",
    "extract_document",
    "get_lab_extractor",
]
