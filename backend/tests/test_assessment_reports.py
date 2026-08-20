"""Reports attached to assessments.

The line these tests hold: an attached report changes what is *shown* and what
is *asked*, and never what the model is *given*. The condition model is trained
on symptoms only.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import get_db_session
from app.main import create_app
from app.models.assessment_report import AssessmentReport
from app.services.ml.condition_prediction.features import SymptomVectoriser
from app.services.ml.condition_prediction.inference import ConditionPredictionService
from app.services.ml.condition_prediction.model_loader import LoadedModel
from app.services.storage.local import LocalStorageProvider
from tests.test_pdf_extraction import make_text_pdf

SIGNUP = "/api/auth/signup"
ASSESSMENTS = "/api/assessments"
REPORTS = "/api/reports"
PASSWORD = "a-strong-passphrase"

TRAINING_CASES: list[tuple[str, list[str]]] = [
    ("Migraine", ["headache", "nausea"]),
    ("Migraine", ["headache", "visual_disturbances"]),
    ("Gastroenteritis", ["vomiting", "diarrhoea"]),
    ("Gastroenteritis", ["vomiting", "abdominal_pain"]),
    ("Anaemia", ["fatigue", "breathlessness"]),
    ("Anaemia", ["fatigue", "dizziness"]),
]

#: A report whose haemoglobin is below its own printed range.
ANAEMIC_REPORT = """CITY DIAGNOSTICS
COMPLETE BLOOD COUNT
Collected on: 2026-03-14

Hemoglobin            8.2 g/dL         13.0 - 17.0
Platelets             200,000 /uL      150000 - 410000
"""


@pytest.fixture
def predictor() -> ConditionPredictionService:
    labels = [label for label, _ in TRAINING_CASES]
    symptom_sets = [symptoms for _, symptoms in TRAINING_CASES]
    vectoriser = SymptomVectoriser.fit(symptom_sets)
    encoder = LabelEncoder().fit(labels)
    estimator = RandomForestClassifier(n_estimators=40, random_state=42).fit(
        vectoriser.transform(symptom_sets), encoder.transform(labels)
    )
    return ConditionPredictionService(
        LoadedModel(
            estimator=estimator,
            vectoriser=vectoriser,
            label_encoder=encoder,
            metadata={"model_name": "test_condition_model", "model_version": "v0"},
        )
    )


@pytest.fixture
def api_app(
    settings: Settings,
    db_session: AsyncSession,
    predictor: ConditionPredictionService,
    tmp_path: Path,
) -> Any:
    application = create_app(settings)
    application.state.condition_predictor = predictor
    application.state.storage_service = LocalStorageProvider(tmp_path / "storage")

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
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    await client.post("/api/auth/onboarding", json={"date_of_birth": "1990-05-04"}, headers=headers)
    return headers


async def _upload(client: AsyncClient, headers: dict[str, str], text: str = ANAEMIC_REPORT) -> dict:
    files = {"file": ("cbc.pdf", make_text_pdf(text), "application/pdf")}
    response = await client.post(REPORTS, headers=headers, files=files)
    assert response.status_code == 201
    return response.json()


async def _start(
    client: AsyncClient, headers: dict[str, str], text: str = "I have a headache"
) -> dict:
    response = await client.post(ASSESSMENTS, headers=headers, json={"symptom_text": text})
    assert response.status_code == 201
    return response.json()


# ------------------------------------------------------------------ attaching


async def test_attaching_a_report_surfaces_its_values(client: AsyncClient) -> None:
    headers = await _onboarded(client)
    report = await _upload(client, headers)
    assessment = await _start(client, headers)

    response = await client.post(
        f"{ASSESSMENTS}/{assessment['id']}/reports/{report['id']}", headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert [r["id"] for r in body["linked_reports"]] == [report["id"]]
    findings = {f["analyte"]: f for f in body["lab_findings"]}
    assert findings["hemoglobin"]["value"] == 8.2
    assert findings["hemoglobin"]["flag"] == "low"


async def test_findings_declare_they_came_from_a_report(client: AsyncClient) -> None:
    """Provenance is explicit so nothing can be mistaken for a model output."""
    headers = await _onboarded(client)
    report = await _upload(client, headers)
    assessment = await _start(client, headers)

    body = (
        await client.post(
            f"{ASSESSMENTS}/{assessment['id']}/reports/{report['id']}", headers=headers
        )
    ).json()

    assert all(finding["source"] == "report" for finding in body["lab_findings"])
    assert all(finding["report_filename"] == "cbc.pdf" for finding in body["lab_findings"])


async def test_attaching_twice_is_idempotent(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _onboarded(client)
    report = await _upload(client, headers)
    assessment = await _start(client, headers)
    url = f"{ASSESSMENTS}/{assessment['id']}/reports/{report['id']}"

    await client.post(url, headers=headers)
    second = await client.post(url, headers=headers)

    assert second.status_code == 200
    assert len(second.json()["linked_reports"]) == 1
    assert await db_session.scalar(select(func.count()).select_from(AssessmentReport)) == 1


async def test_a_report_can_be_detached(client: AsyncClient) -> None:
    headers = await _onboarded(client)
    report = await _upload(client, headers)
    assessment = await _start(client, headers)
    url = f"{ASSESSMENTS}/{assessment['id']}/reports/{report['id']}"
    await client.post(url, headers=headers)

    body = (await client.delete(url, headers=headers)).json()

    assert body["linked_reports"] == []
    assert body["lab_findings"] == []


async def test_deleting_a_report_removes_it_from_the_assessment(
    client: AsyncClient,
) -> None:
    """The link cascades; an assessment must not reference a deleted document."""
    headers = await _onboarded(client)
    report = await _upload(client, headers)
    assessment = await _start(client, headers)
    await client.post(f"{ASSESSMENTS}/{assessment['id']}/reports/{report['id']}", headers=headers)

    await client.delete(f"{REPORTS}/{report['id']}", headers=headers)

    body = (await client.get(f"{ASSESSMENTS}/{assessment['id']}", headers=headers)).json()
    assert body["linked_reports"] == []
    assert body["lab_findings"] == []


# -------------------------------------------------------- lab-driven questions


async def test_an_out_of_range_value_prompts_related_symptoms(
    client: AsyncClient,
) -> None:
    """Low haemoglobin makes fatigue and breathlessness worth asking about."""
    headers = await _onboarded(client)
    report = await _upload(client, headers)
    assessment = await _start(client, headers, "I have a headache for 2 days, mild")

    body = (
        await client.post(
            f"{ASSESSMENTS}/{assessment['id']}/reports/{report['id']}", headers=headers
        )
    ).json()

    question = body["next_question"]
    assert question is not None
    assert question["key"] == "lab_prompted_symptoms"
    offered = {option["value"] for option in question["symptom_options"]}
    assert {"fatigue", "breathlessness"} & offered


async def test_answering_a_lab_prompt_records_the_symptoms(
    client: AsyncClient,
) -> None:
    headers = await _onboarded(client)
    report = await _upload(client, headers)
    assessment = await _start(client, headers, "I have a headache for 2 days, mild")
    body = (
        await client.post(
            f"{ASSESSMENTS}/{assessment['id']}/reports/{report['id']}", headers=headers
        )
    ).json()
    offered = [option["value"] for option in body["next_question"]["symptom_options"]]

    updated = (
        await client.post(
            f"{ASSESSMENTS}/{assessment['id']}/messages",
            headers=headers,
            json={"question_key": "lab_prompted_symptoms", "value": [offered[0]]},
        )
    ).json()

    assert offered[0] in updated["recognised_symptoms"]
    # Offered but not selected means "no", so it is not asked again.
    for skipped in offered[1:]:
        assert skipped in updated["rejected_symptoms"]


async def test_a_normal_report_prompts_nothing(client: AsyncClient) -> None:
    headers = await _onboarded(client)
    normal = "Hemoglobin 14.5 g/dL 13.0 - 17.0\nPlatelets 250,000 /uL 150000 - 410000\n" * 3
    report = await _upload(client, headers, normal)
    assessment = await _start(client, headers, "I have a headache for 2 days, mild")

    body = (
        await client.post(
            f"{ASSESSMENTS}/{assessment['id']}/reports/{report['id']}", headers=headers
        )
    ).json()

    assert body["lab_findings"], "values should still be shown"
    assert body["next_question"] is None or body["next_question"]["key"] != "lab_prompted_symptoms"


# ------------------------------------------------- separation from the model


async def test_lab_values_never_enter_the_model(client: AsyncClient) -> None:
    """The core guarantee of this phase.

    The model is trained on symptoms only. Attaching a report must not change
    the feature vector, so an analysis with and without it predicts identically
    when no lab-prompted symptom is answered.
    """
    headers = await _onboarded(client, "ada@example.com")
    other = await _onboarded(client, "grace@example.com")

    plain = await _start(client, other, "vomiting and diarrhoea for 2 days, mild")
    with_report = await _start(client, headers, "vomiting and diarrhoea for 2 days, mild")
    report = await _upload(client, headers)
    await client.post(f"{ASSESSMENTS}/{with_report['id']}/reports/{report['id']}", headers=headers)

    async def analyse(hdrs: dict[str, str], assessment_id: str) -> dict:
        for _ in range(12):
            detail = (await client.get(f"{ASSESSMENTS}/{assessment_id}", headers=hdrs)).json()
            question = detail["next_question"]
            if question is None:
                break
            # Decline every optional symptom so only the typed ones count.
            declined = [] if question["answer_type"] == "symptom_check" else False
            await client.post(
                f"{ASSESSMENTS}/{assessment_id}/messages",
                headers=hdrs,
                json={"question_key": question["key"], "value": declined},
            )
        return (await client.post(f"{ASSESSMENTS}/{assessment_id}/analyze", headers=hdrs)).json()

    without = await analyse(other, plain["id"])
    withlab = await analyse(headers, with_report["id"])

    assert [p["condition"] for p in without["predictions"]] == [
        p["condition"] for p in withlab["predictions"]
    ]
    assert without["predictions"][0]["score"] == withlab["predictions"][0]["score"]
    # ...but the lab evidence is still carried on the completed assessment.
    assert withlab["lab_findings"]
    assert not without["lab_findings"]


async def test_predictions_and_findings_stay_distinguishable(
    client: AsyncClient,
) -> None:
    """A completed assessment keeps the two kinds of evidence separate."""
    headers = await _onboarded(client)
    report = await _upload(client, headers)
    assessment = await _start(client, headers, "vomiting and diarrhoea for 2 days, mild")
    await client.post(f"{ASSESSMENTS}/{assessment['id']}/reports/{report['id']}", headers=headers)
    for _ in range(12):
        detail = (await client.get(f"{ASSESSMENTS}/{assessment['id']}", headers=headers)).json()
        if detail["next_question"] is None:
            break
        await client.post(
            f"{ASSESSMENTS}/{assessment['id']}/messages",
            headers=headers,
            json={"question_key": detail["next_question"]["key"], "value": []},
        )
    body = (await client.post(f"{ASSESSMENTS}/{assessment['id']}/analyze", headers=headers)).json()

    assert body["model_name"] and body["model_version"]  # predictions are attributed
    assert all(finding["source"] == "report" for finding in body["lab_findings"])
    # No lab analyte leaked into the symptoms the model was given.
    assert "hemoglobin" not in body["recognised_symptoms"]


# ----------------------------------------------------------------- ownership


async def test_you_cannot_attach_someone_elses_report(client: AsyncClient) -> None:
    ada = await _onboarded(client, "ada@example.com")
    grace = await _onboarded(client, "grace@example.com")
    adas_report = await _upload(client, ada)
    graces_assessment = await _start(client, grace)

    response = await client.post(
        f"{ASSESSMENTS}/{graces_assessment['id']}/reports/{adas_report['id']}", headers=grace
    )

    assert response.status_code == 404


async def test_you_cannot_attach_to_someone_elses_assessment(
    client: AsyncClient,
) -> None:
    ada = await _onboarded(client, "ada@example.com")
    grace = await _onboarded(client, "grace@example.com")
    adas_assessment = await _start(client, ada)
    graces_report = await _upload(client, grace)

    response = await client.post(
        f"{ASSESSMENTS}/{adas_assessment['id']}/reports/{graces_report['id']}", headers=grace
    )

    assert response.status_code == 404


async def test_a_completed_assessment_cannot_gain_reports(client: AsyncClient) -> None:
    """A completed assessment is an immutable record of what was considered."""
    headers = await _onboarded(client)
    report = await _upload(client, headers)
    assessment = await _start(client, headers, "vomiting and diarrhoea for 2 days, mild")
    for _ in range(12):
        detail = (await client.get(f"{ASSESSMENTS}/{assessment['id']}", headers=headers)).json()
        if detail["next_question"] is None:
            break
        await client.post(
            f"{ASSESSMENTS}/{assessment['id']}/messages",
            headers=headers,
            json={"question_key": detail["next_question"]["key"], "value": []},
        )
    await client.post(f"{ASSESSMENTS}/{assessment['id']}/analyze", headers=headers)

    response = await client.post(
        f"{ASSESSMENTS}/{assessment['id']}/reports/{report['id']}", headers=headers
    )

    assert response.status_code == 409


async def test_attaching_an_unknown_report_is_not_found(client: AsyncClient) -> None:
    headers = await _onboarded(client)
    assessment = await _start(client, headers)

    response = await client.post(
        f"{ASSESSMENTS}/{assessment['id']}/reports/{uuid.uuid4()}", headers=headers
    )

    assert response.status_code == 404
