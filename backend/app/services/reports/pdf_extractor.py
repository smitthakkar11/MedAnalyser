"""Get text out of an uploaded report.

    PDF → PyMuPDF text layer → (if that yields too little) → OCR each page

Most lab reports are generated digitally and carry a text layer, which is exact
and fast. Scans and photographed printouts have none, so those fall back to
Tesseract. The method used is recorded on the report: OCR output is materially
less reliable, and a user reviewing extracted values deserves to know which
they are looking at.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from enum import StrEnum

import pymupdf
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

#: Below this many characters a page is treated as having no usable text layer.
#: A scanned PDF often carries a few stray characters from a header stamp.
MIN_CHARS_FOR_TEXT_LAYER = 80

#: Rendering scale for OCR. Tesseract needs roughly 300 DPI; PDFs default to 72.
OCR_ZOOM = 300 / 72

#: Refuse documents large enough to be a denial-of-service rather than a report.
MAX_PAGES = 30


class ExtractionMethod(StrEnum):
    """How the text was obtained."""

    TEXT_LAYER = "text_layer"
    OCR = "ocr"
    #: Some pages had text, others needed OCR.
    MIXED = "mixed"
    NONE = "none"


class PdfExtractionError(Exception):
    """Raised when a document cannot be read at all."""


@dataclass(frozen=True)
class ExtractedDocument:
    """The text of an uploaded report, and how it was obtained."""

    text: str
    method: ExtractionMethod
    page_count: int
    #: Pages that needed OCR, 1-indexed.
    ocr_pages: tuple[int, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


def extract_document(content: bytes, *, allow_ocr: bool = True) -> ExtractedDocument:
    """Extract text from a PDF, falling back to OCR page by page.

    The fallback is per page, not per document: a report whose results table is
    a scanned image pasted into a digital letterhead would otherwise lose
    exactly the part that matters.
    """
    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - any parse failure reads the same
        raise PdfExtractionError("This file could not be read as a PDF.") from exc

    with document:
        if document.needs_pass:
            raise PdfExtractionError("This PDF is password protected.")
        if document.page_count == 0:
            raise PdfExtractionError("This PDF has no pages.")
        if document.page_count > MAX_PAGES:
            raise PdfExtractionError(
                f"This PDF has {document.page_count} pages; the limit is {MAX_PAGES}."
            )

        pages: list[str] = []
        ocr_pages: list[int] = []
        used_text_layer = False

        # Indexed rather than iterating the Document directly: PyMuPDF's stubs
        # do not describe it as an iterable of pages.
        for index in range(1, document.page_count + 1):
            page: pymupdf.Page = document.load_page(index - 1)
            text = str(page.get_text("text")).strip()

            if len(text) >= MIN_CHARS_FOR_TEXT_LAYER:
                used_text_layer = True
            elif allow_ocr:
                ocr_text = _ocr_page(page, index)
                if ocr_text:
                    text = ocr_text
                    ocr_pages.append(index)
            pages.append(text)

        page_count = document.page_count

    return ExtractedDocument(
        text="\n".join(pages).strip(),
        method=_method(used_text_layer, bool(ocr_pages)),
        page_count=page_count,
        ocr_pages=tuple(ocr_pages),
    )


def _ocr_page(page: pymupdf.Page, index: int) -> str:
    """Render a page and run Tesseract over it.

    A failure here is not fatal: OCR depends on a system binary that may be
    absent, and a report with a readable text layer on other pages is still
    worth returning.
    """
    try:
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(OCR_ZOOM, OCR_ZOOM))
        image = Image.open(io.BytesIO(pixmap.tobytes("png")))
        return str(pytesseract.image_to_string(image)).strip()
    except pytesseract.TesseractNotFoundError:
        logger.warning("OCR unavailable: the tesseract binary is not installed")
        return ""
    except Exception as exc:  # noqa: BLE001 - OCR is best-effort
        logger.warning("OCR failed", extra={"page": index, "error": type(exc).__name__})
        return ""


def _method(used_text_layer: bool, used_ocr: bool) -> ExtractionMethod:
    if used_text_layer and used_ocr:
        return ExtractionMethod.MIXED
    if used_ocr:
        return ExtractionMethod.OCR
    if used_text_layer:
        return ExtractionMethod.TEXT_LAYER
    return ExtractionMethod.NONE
