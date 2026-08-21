"""Red flags in the assessment flow.

The contract: safety is evaluated independently of the model, is re-evaluated
whenever the inputs change, is stored on the assessment, and takes priority
over any prediction.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.session import get_db_session
from app.main import create_app
from app.models.assessment import Assessment
from app.services.ml.condition_prediction.features import SymptomVectoriser
from app.services.ml.condition_prediction.inference import ConditionPredictionService
from app.services.ml.condition_prediction.model_loader import LoadedModel

SIGNUP = "/api/auth/signup"
ASSESSMENTS = "/api/assessments"
PASSWORD = "a-strong-passphrase"

TRAINING_CASES: list[tuple[str, list[str]]] = [
    ("Common Cold", ["cough", "runny_nose"]),
    ("Common Cold", ["cough", "throat_irritation"]),
    ("Migraine", ["headache", "nausea"]),
    ("Migraine", ["headache", "visual_disturbances"]),
    ("Angina", ["chest_pain", "breathlessness"]),
    ("Angina", ["chest_pain", "sweating"]),
]


@pytest.fixture
def predictor() -> ConditionPredictionService:
    labels = [label for label, _ in TRAINING_CASES]
    sets = [symptoms for _, symptoms in TRAINING_CASES]
    vectoriser = SymptomVectoriser.fit(sets)
    encoder = LabelEncoder().fit(labels)
    estimator = RandomForestClassifier(n_estimators=40, random_state=42).fit(
        vectoriser.transform(sets), encoder.transform(labels)
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
    settings: Settings, db_session: AsyncSession, predictor: ConditionPredictionService
) -> Any:
    application = create_app(settings)
    application.state.condition_predictor = predictor

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
    signup = await client.post(SIGNUP, json={"name": "Ada", "email": email, "password": PASSWORD})
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    await client.post("/api/auth/onboarding", json={"date_of_birth": "1990-05-04"}, headers=headers)
    return headers


async def _start(client: AsyncClient, headers: dict[str, str], text: str) -> dict:
    response = await client.post(ASSESSMENTS, headers=headers, json={"symptom_text": text})
    assert response.status_code == 201
    return response.json()


# ------------------------------------------------------- flagged at intake


async def test_an_emergency_is_flagged_the_moment_it_is_described(
    client: AsyncClient,
) -> None:
    """The warning must not wait until the user finishes the questionnaire."""
    headers = await _onboarded(client)

    body = await _start(client, headers, "I have crushing chest pain spreading to my arm")

    assert body["safety"]["level"] == "emergency"
    assert "emergency medical care now" in body["safety"]["headline"]
    assert body["safety"]["flags"]


async def test_every_flag_cites_public_guidance(client: AsyncClient) -> None:
    headers = await _onboarded(client)

    body = await _start(client, headers, "I passed out this morning")

    for flag in body["safety"]["flags"]:
        assert flag["source"]
        assert flag["source_url"].startswith("https://")


async def test_an_ordinary_complaint_is_not_flagged(client: AsyncClient) -> None:
    headers = await _onboarded(client)

    body = await _start(client, headers, "I have a mild runny nose and I keep sneezing")

    assert body["safety"]["level"] == "none"
    assert body["safety"]["headline"] == ""
    assert body["safety"]["flags"] == []


async def test_the_outcome_is_persisted(client: AsyncClient, db_session: AsyncSession) -> None:
    headers = await _onboarded(client)

    await _start(client, headers, "I have crushing chest pain")

    stored = (await db_session.execute(select(Assessment))).scalar_one()
    assert stored.safety_level == "emergency"
    assert stored.safety_flags


# --------------------------------------------------- re-evaluated on change


async def test_a_later_answer_can_raise_a_flag(client: AsyncClient) -> None:
    """A red flag that only becomes apparent from a follow-up must still fire."""
    headers = await _onboarded(client)
    created = await _start(client, headers, "I have chest pain for 2 days")
    assert created["safety"]["level"] == "none"

    # Answering "severe" turns an unremarkable chest pain into an emergency.
    detail = created
    while detail["next_question"] and detail["next_question"]["key"] != "severity":
        detail = (
            await client.post(
                f"{ASSESSMENTS}/{detail['id']}/messages",
                headers=headers,
                json={"question_key": detail["next_question"]["key"], "value": False},
            )
        ).json()

    updated = (
        await client.post(
            f"{ASSESSMENTS}/{detail['id']}/messages",
            headers=headers,
            json={"question_key": "severity", "value": "severe"},
        )
    ).json()

    assert updated["safety"]["level"] == "emergency"


# --------------------------------------------- priority over the prediction


async def test_safety_is_independent_of_the_prediction(client: AsyncClient) -> None:
    """The engine reaches its verdict without consulting the model.

    The stub model here has no idea chest pain is dangerous — it only knows
    three benign-sounding labels — yet the emergency is still raised.
    """
    headers = await _onboarded(client)
    created = await _start(client, headers, "crushing chest pain and I cant breathe")

    assert created["safety"]["level"] == "emergency"
    # No prediction has even been run yet.
    assert created["predictions"] == []


async def test_the_warning_survives_analysis(client: AsyncClient) -> None:
    """A completed assessment keeps its warning alongside the predictions —
    a model output must never be able to soften it."""
    headers = await _onboarded(client)
    created = await _start(
        client, headers, "severe crushing chest pain and breathlessness for 1 day"
    )
    detail = created
    for _ in range(12):
        if detail["next_question"] is None:
            break
        detail = (
            await client.post(
                f"{ASSESSMENTS}/{detail['id']}/messages",
                headers=headers,
                json={
                    "question_key": detail["next_question"]["key"],
                    "value": []
                    if detail["next_question"]["answer_type"] == "symptom_check"
                    else False,
                },
            )
        ).json()

    completed = (
        await client.post(f"{ASSESSMENTS}/{created['id']}/analyze", headers=headers)
    ).json()

    assert completed["status"] == "completed"
    assert completed["safety"]["level"] == "emergency"
    assert completed["predictions"], "predictions are still produced"
    # Both are present, and the warning is not diluted by the prediction.
    assert "emergency medical care now" in completed["safety"]["headline"]


async def test_the_summary_carries_the_level(client: AsyncClient) -> None:
    """A history list must be able to mark a dangerous entry without loading it."""
    headers = await _onboarded(client)
    await _start(client, headers, "I have crushing chest pain")

    listed = (await client.get(ASSESSMENTS, headers=headers)).json()

    assert listed[0]["safety_level"] == "emergency"


async def test_a_denied_symptom_does_not_raise_a_flag(client: AsyncClient) -> None:
    """ "no chest pain" must not be read as chest pain."""
    headers = await _onboarded(client)

    body = await _start(client, headers, "I have a headache but no chest pain")

    assert body["safety"]["level"] == "none"
