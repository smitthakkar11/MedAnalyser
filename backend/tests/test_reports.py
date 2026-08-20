"""Medical report API: upload, validation, extraction, ownership.

Uploads are pointed at a temporary storage root, so tests never touch the
developer's storage directory.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import get_db_session
from app.main import create_app
from app.models.report import MedicalReport, ReportValue
from app.services.storage.local import LocalStorageProvider
from tests.test_pdf_extraction import make_scanned_pdf, make_text_pdf

SIGNUP = "/api/auth/signup"
REPORTS = "/api/reports"
PASSWORD = "a-strong-passphrase"


@pytest.fixture
def storage_root(tmp_path: Path) -> Path:
    return tmp_path / "storage"


@pytest.fixture
def api_app(settings: Settings, db_session: AsyncSession, storage_root: Path) -> Any:
    application = create_app(settings)
    application.state.storage_service = LocalStorageProvider(storage_root)

    async def _override():
        yield db_session

    application.dependency_overrides[get_db_session] = _override
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
async def client(api_app: FastAPI) -> Any:
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def _onboarded(client: AsyncClient, email: str = "ada@example.com") -> dict[str, str]:
    signup = await client.post(
        SIGNUP, json={"name": "Ada Lovelace", "email": email, "password": PASSWORD}
    )
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/api/auth/onboarding", json={"date_of_birth": "1990-05-04"}, headers=headers)
    return headers


def _upload(content: bytes, name: str = "cbc.pdf", mime: str = "application/pdf") -> dict:
    return {"file": (name, content, mime)}


# ------------------------------------------------------------------ uploading


async def test_uploading_a_report_extracts_its_values(client: AsyncClient) -> None:
    """The path this phase exists to deliver."""
    headers = await _onboarded(client)

    response = await client.post(REPORTS, headers=headers, files=_upload(make_text_pdf()))

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "processed"
    assert body["extraction_method"] == "text_layer"
    assert body["page_count"] == 1

    values = {value["analyte"]: value for value in body["values"]}
    assert values["hemoglobin"]["value"] == 10.8
    assert values["wbc"]["value"] == 13500.0
    assert values["platelets"]["value"] == 180000.0


async def test_flags_come_from_the_reports_own_ranges(client: AsyncClient) -> None:
    headers = await _onboarded(client)

    body = (await client.post(REPORTS, headers=headers, files=_upload(make_text_pdf()))).json()

    values = {value["analyte"]: value for value in body["values"]}
    assert values["hemoglobin"]["flag"] == "low"  # 10.8 against 13.0–17.0
    assert values["wbc"]["flag"] == "high"  # 13,500 against 4000–11000
    assert values["platelets"]["flag"] == "normal"  # 180,000 against 150000–410000


async def test_the_report_date_is_read_from_the_page(client: AsyncClient) -> None:
    headers = await _onboarded(client)

    body = (await client.post(REPORTS, headers=headers, files=_upload(make_text_pdf()))).json()

    assert body["report_date"] == "2026-03-14"


async def test_values_are_persisted_with_the_owner(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await _onboarded(client)

    await client.post(REPORTS, headers=headers, files=_upload(make_text_pdf()))

    stored = (await db_session.execute(select(ReportValue))).scalars().all()
    assert len(stored) == 3
    report = (await db_session.execute(select(MedicalReport))).scalar_one()
    assert all(value.user_id == report.user_id for value in stored)


async def test_the_original_file_is_stored(client: AsyncClient, storage_root: Path) -> None:
    headers = await _onboarded(client)

    await client.post(REPORTS, headers=headers, files=_upload(make_text_pdf()))

    written = list(storage_root.rglob("*.pdf"))
    assert len(written) == 1
    assert written[0].read_bytes().startswith(b"%PDF-")


async def test_a_hostile_filename_never_reaches_the_filesystem(
    client: AsyncClient, storage_root: Path, db_session: AsyncSession
) -> None:
    """An uploaded filename is attacker-controlled; the stored name is generated."""
    headers = await _onboarded(client)

    await client.post(
        REPORTS,
        headers=headers,
        files=_upload(make_text_pdf(), name="../../../../etc/passwd.pdf"),
    )

    written = list(storage_root.rglob("*"))
    assert not any("etc" in part.name or ".." in part.name for part in written)
    report = (await db_session.execute(select(MedicalReport))).scalar_one()
    # The display label keeps only the basename.
    assert "/" not in report.original_filename
    assert report.original_filename == "passwd.pdf"


async def test_a_scanned_report_falls_back_to_ocr(client: AsyncClient) -> None:
    import pytesseract

    try:
        pytesseract.get_tesseract_version()
    except Exception:  # noqa: BLE001
        pytest.skip("tesseract is not installed")

    headers = await _onboarded(client)

    body = (
        await client.post(
            REPORTS, headers=headers, files=_upload(make_scanned_pdf("Hemoglobin 10.8"))
        )
    ).json()

    assert body["extraction_method"] == "ocr"


# ----------------------------------------------------------------- validation


@pytest.mark.parametrize(
    ("content", "name", "mime"),
    [
        (b"not a pdf at all", "notes.txt", "text/plain"),
        (b"not a pdf at all", "sneaky.pdf", "application/pdf"),
        (b"%PDF-1.4 fake", "sneaky.exe", "application/pdf"),
        (b"", "empty.pdf", "application/pdf"),
    ],
    ids=["wrong-mime", "wrong-magic-bytes", "wrong-extension", "empty"],
)
async def test_files_that_are_not_processable_pdfs_are_refused(
    client: AsyncClient, content: bytes, name: str, mime: str
) -> None:
    headers = await _onboarded(client)

    response = await client.post(REPORTS, headers=headers, files=_upload(content, name, mime))

    assert response.status_code == 422


async def test_a_declared_content_type_is_not_believed(client: AsyncClient) -> None:
    """The magic bytes decide, not the client's claim."""
    headers = await _onboarded(client)

    response = await client.post(
        REPORTS,
        headers=headers,
        files=_upload(b"MZ\x90\x00 an executable", "report.pdf", "application/pdf"),
    )

    assert response.status_code == 422
    assert "not a valid PDF" in response.json()["error"]["message"]


async def test_an_oversized_upload_is_refused(client: AsyncClient, api_app: FastAPI) -> None:
    api_app.state.settings.max_upload_size_mb = 1
    headers = await _onboarded(client)
    oversized = b"%PDF-" + b"0" * (2 * 1024 * 1024)

    response = await client.post(REPORTS, headers=headers, files=_upload(oversized))

    assert response.status_code == 413


async def test_a_pdf_with_no_readable_text_is_marked_failed(
    client: AsyncClient,
) -> None:
    """Marked failed with an actionable message, not silently empty."""
    import pymupdf

    document = pymupdf.open()
    document.new_page()
    blank = document.tobytes()
    document.close()
    headers = await _onboarded(client)

    body = (await client.post(REPORTS, headers=headers, files=_upload(blank))).json()

    assert body["status"] == "failed"
    assert body["error_message"]


async def test_a_pdf_with_no_known_analytes_is_processed_but_explains_itself(
    client: AsyncClient,
) -> None:
    headers = await _onboarded(client)
    text = "DISCHARGE SUMMARY\nThe patient was seen and discharged in good condition.\n" * 3

    body = (await client.post(REPORTS, headers=headers, files=_upload(make_text_pdf(text)))).json()

    assert body["status"] == "processed"
    assert body["values"] == []
    assert "no laboratory values" in body["error_message"].lower()


async def test_re_uploading_the_same_file_is_refused(client: AsyncClient) -> None:
    headers = await _onboarded(client)
    content = make_text_pdf()
    first = await client.post(REPORTS, headers=headers, files=_upload(content))

    second = await client.post(REPORTS, headers=headers, files=_upload(content))

    assert second.status_code == 409
    assert second.json()["error"]["details"]["existing_report_id"] == first.json()["id"]


async def test_a_refused_duplicate_leaves_no_orphan_file(
    client: AsyncClient, storage_root: Path
) -> None:
    headers = await _onboarded(client)
    content = make_text_pdf()
    await client.post(REPORTS, headers=headers, files=_upload(content))

    await client.post(REPORTS, headers=headers, files=_upload(content))

    assert len(list(storage_root.rglob("*.pdf"))) == 1


async def test_two_users_may_upload_the_same_file(client: AsyncClient) -> None:
    """Deduplication is per user, not global."""
    ada = await _onboarded(client, "ada@example.com")
    grace = await _onboarded(client, "grace@example.com")
    content = make_text_pdf()
    await client.post(REPORTS, headers=ada, files=_upload(content))

    response = await client.post(REPORTS, headers=grace, files=_upload(content))

    assert response.status_code == 201


# ------------------------------------------------------------------- reading


async def test_listing_summarises_each_report(client: AsyncClient) -> None:
    headers = await _onboarded(client)
    await client.post(REPORTS, headers=headers, files=_upload(make_text_pdf()))

    listed = (await client.get(REPORTS, headers=headers)).json()

    assert len(listed) == 1
    assert listed[0]["value_count"] == 3
    assert listed[0]["abnormal_count"] == 2  # low haemoglobin, high WBC


async def test_extracted_text_is_withheld_unless_requested(
    client: AsyncClient,
) -> None:
    """Report text is sensitive and long; it is opt-in."""
    headers = await _onboarded(client)
    created = (await client.post(REPORTS, headers=headers, files=_upload(make_text_pdf()))).json()

    without = (await client.get(f"{REPORTS}/{created['id']}", headers=headers)).json()
    with_text = (
        await client.get(f"{REPORTS}/{created['id']}?include_text=true", headers=headers)
    ).json()

    assert without["extracted_text"] is None
    assert "Hemoglobin" in with_text["extracted_text"]


async def test_the_original_file_can_be_downloaded(client: AsyncClient) -> None:
    headers = await _onboarded(client)
    created = (await client.post(REPORTS, headers=headers, files=_upload(make_text_pdf()))).json()

    response = await client.get(f"{REPORTS}/{created['id']}/file", headers=headers)

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")
    # Served as an attachment under a generated name, never the user's.
    assert response.headers["content-disposition"].startswith("attachment")
    assert created["id"] in response.headers["content-disposition"]


# ----------------------------------------------------------------- ownership


async def test_listing_returns_only_your_own_reports(client: AsyncClient) -> None:
    ada = await _onboarded(client, "ada@example.com")
    grace = await _onboarded(client, "grace@example.com")
    await client.post(REPORTS, headers=ada, files=_upload(make_text_pdf()))

    assert (await client.get(REPORTS, headers=grace)).json() == []


async def test_one_user_cannot_read_anothers_report(client: AsyncClient) -> None:
    ada = await _onboarded(client, "ada@example.com")
    grace = await _onboarded(client, "grace@example.com")
    created = (await client.post(REPORTS, headers=ada, files=_upload(make_text_pdf()))).json()

    detail = await client.get(f"{REPORTS}/{created['id']}", headers=grace)
    download = await client.get(f"{REPORTS}/{created['id']}/file", headers=grace)

    # 404, not 403: the response must not confirm the id exists.
    assert detail.status_code == 404
    assert download.status_code == 404


async def test_one_user_cannot_delete_anothers_report(
    client: AsyncClient, db_session: AsyncSession, storage_root: Path
) -> None:
    ada = await _onboarded(client, "ada@example.com")
    grace = await _onboarded(client, "grace@example.com")
    created = (await client.post(REPORTS, headers=ada, files=_upload(make_text_pdf()))).json()

    response = await client.delete(f"{REPORTS}/{created['id']}", headers=grace)

    assert response.status_code == 404
    assert await db_session.scalar(select(func.count()).select_from(MedicalReport)) == 1
    assert len(list(storage_root.rglob("*.pdf"))) == 1


async def test_deleting_removes_the_values_and_the_stored_file(
    client: AsyncClient, db_session: AsyncSession, storage_root: Path
) -> None:
    headers = await _onboarded(client)
    created = (await client.post(REPORTS, headers=headers, files=_upload(make_text_pdf()))).json()

    response = await client.delete(f"{REPORTS}/{created['id']}", headers=headers)

    assert response.status_code == 204
    assert await db_session.scalar(select(func.count()).select_from(MedicalReport)) == 0
    assert await db_session.scalar(select(func.count()).select_from(ReportValue)) == 0
    assert list(storage_root.rglob("*.pdf")) == []


async def test_reports_require_authentication(client: AsyncClient) -> None:
    assert (await client.get(REPORTS)).status_code == 401
    assert (await client.post(REPORTS, files=_upload(make_text_pdf()))).status_code == 401


async def test_reports_require_completed_onboarding(client: AsyncClient) -> None:
    signup = await client.post(
        SIGNUP, json={"name": "Ada", "email": "ada@example.com", "password": PASSWORD}
    )
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    assert (await client.get(REPORTS, headers=headers)).status_code == 403


async def test_an_unknown_report_id_is_not_found(client: AsyncClient) -> None:
    headers = await _onboarded(client)

    response = await client.get(f"{REPORTS}/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404
