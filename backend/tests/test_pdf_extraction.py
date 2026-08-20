"""PDF text extraction and the OCR fallback.

PDFs are generated in-test with PyMuPDF rather than committed as fixtures, so
the inputs are visible in the test itself and no binaries live in the repo.
"""

from __future__ import annotations

import io

import pymupdf
import pytest
from PIL import Image, ImageDraw

from app.services.reports.pdf_extractor import (
    ExtractionMethod,
    PdfExtractionError,
    extract_document,
)

REPORT_TEXT = """CITY DIAGNOSTICS
COMPLETE BLOOD COUNT
Collected on: 2026-03-14

Hemoglobin            10.8 g/dL        13.0 - 17.0
WBC                   13,500 /uL       4000 - 11000
Platelets             180,000 /uL      150000 - 410000
"""


def make_text_pdf(text: str = REPORT_TEXT, pages: int = 1) -> bytes:
    """A PDF with a real text layer."""
    document = pymupdf.open()
    for _ in range(pages):
        page = document.new_page()
        page.insert_text((50, 60), text, fontsize=11)
    content: bytes = document.tobytes()
    document.close()
    return content


def make_scanned_pdf(text: str = "Hemoglobin 10.8 g/dL") -> bytes:
    """A PDF whose only content is a rendered image — no text layer."""
    image = Image.new("RGB", (1200, 300), "white")
    draw = ImageDraw.Draw(image)
    # Large and well spaced so OCR is reliable without a bundled font.
    draw.text((40, 110), text, fill="black", font_size=48)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    document = pymupdf.open()
    page = document.new_page(width=1200, height=300)
    page.insert_image(pymupdf.Rect(0, 0, 1200, 300), stream=buffer.getvalue())
    content: bytes = document.tobytes()
    document.close()
    return content


# ----------------------------------------------------------------- text layer


def test_text_layer_is_used_when_present() -> None:
    result = extract_document(make_text_pdf())

    assert result.method is ExtractionMethod.TEXT_LAYER
    assert result.page_count == 1
    assert result.ocr_pages == ()
    assert "Hemoglobin" in result.text


def test_all_pages_are_read() -> None:
    result = extract_document(make_text_pdf(pages=3))

    assert result.page_count == 3
    assert result.text.count("Hemoglobin") == 3


# ------------------------------------------------------------------- failures


def test_a_non_pdf_is_rejected() -> None:
    with pytest.raises(PdfExtractionError, match="could not be read"):
        extract_document(b"this is plainly not a pdf")


def test_an_empty_payload_is_rejected() -> None:
    with pytest.raises(PdfExtractionError):
        extract_document(b"")


def test_a_password_protected_pdf_is_reported_clearly() -> None:
    document = pymupdf.open()
    document.new_page().insert_text((50, 60), "secret")
    protected = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="x", user_pw="y")
    document.close()

    with pytest.raises(PdfExtractionError, match="password protected"):
        extract_document(protected)


def test_an_oversized_document_is_refused() -> None:
    """A page count large enough to be a denial of service, not a report."""
    document = pymupdf.open()
    for _ in range(31):
        document.new_page()
    many_pages = document.tobytes()
    document.close()

    with pytest.raises(PdfExtractionError, match="limit is 30"):
        extract_document(many_pages)


def test_a_pdf_with_no_content_yields_no_text() -> None:
    document = pymupdf.open()
    document.new_page()
    blank = document.tobytes()
    document.close()

    result = extract_document(blank, allow_ocr=False)

    assert result.is_empty
    assert result.method is ExtractionMethod.NONE


# ------------------------------------------------------------------------ OCR


def test_ocr_is_not_run_when_disabled() -> None:
    result = extract_document(make_scanned_pdf(), allow_ocr=False)

    assert result.method is ExtractionMethod.NONE
    assert result.ocr_pages == ()


def test_ocr_reads_a_scanned_page() -> None:
    """Requires the tesseract binary; skipped where it is unavailable."""
    import pytesseract

    try:
        pytesseract.get_tesseract_version()
    except Exception:  # noqa: BLE001
        pytest.skip("tesseract is not installed")

    result = extract_document(make_scanned_pdf("Hemoglobin 10.8"))

    assert result.method is ExtractionMethod.OCR
    assert result.ocr_pages == (1,)
    assert "emoglobin" in result.text  # OCR may miss the leading capital


def test_the_extraction_method_is_recorded() -> None:
    """OCR output is materially less reliable, so which path ran is surfaced."""
    assert extract_document(make_text_pdf()).method is ExtractionMethod.TEXT_LAYER
