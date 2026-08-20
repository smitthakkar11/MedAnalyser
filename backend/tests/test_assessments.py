"""Assessment API: the full path from free text to a stored prediction.

    text → extraction → follow-up questions → model → PostgreSQL

Predictions come from a small model trained in-fixture, so these tests are
hermetic and do not require anyone to have run training.
"""

from __future__ import annotations

import uuid
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
from app.models.assessment import Assessment, AssessmentMessage
from app.services.ml.condition_prediction.features import SymptomVectoriser
from app.services.ml.condition_prediction.inference import ConditionPredictionService
from app.services.ml.condition_prediction.model_loader import LoadedModel

SIGNUP = "/api/auth/signup"
ASSESSMENTS = "/api/assessments"
PASSWORD = "a-strong-passphrase"

TRAINING_CASES: list[tuple[str, list[str]]] = [
    ("Migraine", ["headache", "nausea", "visual_disturbances"]),
    ("Migraine", ["headache", "nausea"]),
    ("Migraine", ["headache", "visual_disturbances"]),
    ("Gastroenteritis", ["vomiting", "diarrhoea", "abdominal_pain"]),
    ("Gastroenteritis", ["vomiting", "diarrhoea"]),
    ("Gastroenteritis", ["vomiting", "abdominal_pain"]),
    ("Common Cold", ["cough", "runny_nose", "throat_irritation"]),
    ("Common Cold", ["cough", "runny_nose"]),
    ("Common Cold", ["cough", "throat_irritation"]),
]


@pytest.fixture
def predictor() -> ConditionPredictionService:
    labels = [label for label, _ in TRAINING_CASES]
    symptom_sets = [symptoms for _, symptoms in TRAINING_CASES]
    vectoriser = SymptomVectoriser.fit(symptom_sets)
    encoder = LabelEncoder().fit(labels)
    estimator = RandomForestClassifier(n_estimators=50, random_state=42).fit(
        vectoriser.transform(symptom_sets), encoder.transform(labels)
    )
    return ConditionPredictionService(
        LoadedModel(
            estimator=estimator,
            vectoriser=vectoriser,
            label_encoder=encoder,
            metadata={
                "model_name": "test_condition_model",
                "model_version": "v0",
                "condition_symptoms": {
                    label: sorted({s for lbl, ss in TRAINING_CASES if lbl == label for s in ss})
                    for label in set(labels)
                },
            },
        )
    )


@pytest.fixture
def api_app(
    settings: Settings, db_session: AsyncSession, predictor: ConditionPredictionService
) -> Any:
    """App wired to the test database and the in-fixture model."""
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
    signup = await client.post(
        SIGNUP, json={"name": "Ada Lovelace", "email": email, "password": PASSWORD}
    )
    assert signup.status_code == 201
    token = signup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    await client.post("/api/auth/onboarding", json={"date_of_birth": "1990-05-04"}, headers=headers)
    return headers


async def _answer_everything(
    client: AsyncClient, headers: dict[str, str], assessment_id: str
) -> dict[str, Any]:
    """Reply to follow-up questions until the intake is finished."""
    answers: dict[str, Any] = {
        "duration": 3,
        "severity": "moderate",
        "previous_consultation": False,
        "additional_symptoms": [],
    }
    for _ in range(15):
        detail = (await client.get(f"{ASSESSMENTS}/{assessment_id}", headers=headers)).json()
        question = detail["next_question"]
        if question is None:
            return detail
        await client.post(
            f"{ASSESSMENTS}/{assessment_id}/messages",
            headers=headers,
            json={"question_key": question["key"], "value": answers.get(question["key"])},
        )
    raise AssertionError("the intake never finished")


# ------------------------------------------------------------------ creation


async def test_creating_an_assessment_extracts_symptoms(client: AsyncClient) -> None:
    headers = await _onboarded(client)

    response = await client.post(
        ASSESSMENTS,
        headers=headers,
        json={"symptom_text": "I have had a headache and nausea for 3 days"},
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body["recognised_symptoms"]) == {"headache", "nausea"}
    assert body["duration_days"] == 3
    assert body["status"] == "in_progress"
    # Nothing is predicted before the intake has gathered enough.
    assert body["predictions"] == []


async def test_everyday_phrasing_reaches_the_model_vocabulary(
    client: AsyncClient,
) -> None:
    """The user writes English; the model needs canonical features."""
    headers = await _onboarded(client)

    response = await client.post(
        ASSESSMENTS,
        headers=headers,
        json={"symptom_text": "stomach ache and been throwing up since yesterday"},
    )

    assert set(response.json()["recognised_symptoms"]) == {"abdominal_pain", "vomiting"}


async def test_negated_symptoms_are_stored_separately(client: AsyncClient) -> None:
    headers = await _onboarded(client)

    response = await client.post(
        ASSESSMENTS,
        headers=headers,
        json={"symptom_text": "I have a cough but no fever"},
    )

    body = response.json()
    assert "cough" in body["recognised_symptoms"]
    assert "high_fever" in body["rejected_symptoms"]
    assert "high_fever" not in body["recognised_symptoms"]


async def test_the_first_question_is_returned_immediately(client: AsyncClient) -> None:
    headers = await _onboarded(client)

    response = await client.post(
        ASSESSMENTS, headers=headers, json={"symptom_text": "I have a headache"}
    )

    question = response.json()["next_question"]
    assert question is not None
    assert question["key"] == "duration"


async def test_a_duration_in_the_text_is_not_asked_for_again(
    client: AsyncClient,
) -> None:
    headers = await _onboarded(client)

    response = await client.post(
        ASSESSMENTS, headers=headers, json={"symptom_text": "headache for 3 days"}
    )

    assert response.json()["next_question"]["key"] != "duration"


async def test_the_original_text_is_preserved_verbatim(client: AsyncClient) -> None:
    headers = await _onboarded(client)
    text = "I've had a really bad headache and nausea for 3 days."

    response = await client.post(ASSESSMENTS, headers=headers, json={"symptom_text": text})

    assert response.json()["input_text"] == text


@pytest.mark.parametrize("text", ["", "  ", "ab"])
async def test_too_short_input_is_rejected(client: AsyncClient, text: str) -> None:
    headers = await _onboarded(client)

    response = await client.post(ASSESSMENTS, headers=headers, json={"symptom_text": text})

    assert response.status_code == 422


# -------------------------------------------------------------- conversation


async def test_answering_advances_the_intake(client: AsyncClient) -> None:
    headers = await _onboarded(client)
    created = (
        await client.post(ASSESSMENTS, headers=headers, json={"symptom_text": "I have a headache"})
    ).json()

    response = await client.post(
        f"{ASSESSMENTS}/{created['id']}/messages",
        headers=headers,
        json={"question_key": "duration", "value": 3},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["duration_days"] == 3
    assert body["next_question"]["key"] != "duration"


async def test_answers_out_of_order_are_refused(client: AsyncClient) -> None:
    """The rule state machine would be corrupted by an unexpected answer."""
    headers = await _onboarded(client)
    created = (
        await client.post(ASSESSMENTS, headers=headers, json={"symptom_text": "I have a headache"})
    ).json()

    response = await client.post(
        f"{ASSESSMENTS}/{created['id']}/messages",
        headers=headers,
        json={"question_key": "treatment_response", "value": "improved"},
    )

    assert response.status_code == 409


async def test_selected_symptoms_are_added_and_unselected_ones_rejected(
    client: AsyncClient,
) -> None:
    """Not ticking an offered symptom is an answer, and stops it being re-asked."""
    headers = await _onboarded(client)
    created = (
        await client.post(
            ASSESSMENTS, headers=headers, json={"symptom_text": "headache for 2 days, mild"}
        )
    ).json()

    detail = created
    while detail["next_question"] and detail["next_question"]["key"] != "additional_symptoms":
        detail = (
            await client.post(
                f"{ASSESSMENTS}/{detail['id']}/messages",
                headers=headers,
                json={"question_key": detail["next_question"]["key"], "value": False},
            )
        ).json()

    question = detail["next_question"]
    assert question is not None and question["symptom_options"]
    offered = [option["value"] for option in question["symptom_options"]]

    updated = (
        await client.post(
            f"{ASSESSMENTS}/{detail['id']}/messages",
            headers=headers,
            json={"question_key": "additional_symptoms", "value": [offered[0]]},
        )
    ).json()

    assert offered[0] in updated["recognised_symptoms"]
    for not_selected in offered[1:]:
        assert not_selected in updated["rejected_symptoms"]


async def test_the_conversation_is_recorded(client: AsyncClient) -> None:
    headers = await _onboarded(client)
    created = (
        await client.post(ASSESSMENTS, headers=headers, json={"symptom_text": "I have a headache"})
    ).json()
    await client.post(
        f"{ASSESSMENTS}/{created['id']}/messages",
        headers=headers,
        json={"question_key": "duration", "value": 3},
    )

    messages = (await client.get(f"{ASSESSMENTS}/{created['id']}/messages", headers=headers)).json()

    roles = [message["role"] for message in messages]
    assert roles[0] == "user"  # the opening free text
    assert "assistant" in roles  # the question that was put
    assert any(message["question_key"] == "duration" for message in messages)


# ----------------------------------------------------------------- analysis


async def test_analysis_predicts_stores_and_completes(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """The end-to-end path this phase exists to deliver."""
    headers = await _onboarded(client)
    created = (
        await client.post(
            ASSESSMENTS,
            headers=headers,
            json={"symptom_text": "throwing up, loose motions and stomach ache for 2 days"},
        )
    ).json()
    await _answer_everything(client, headers, created["id"])

    response = await client.post(f"{ASSESSMENTS}/{created['id']}/analyze", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["completed_at"] is not None
    assert body["predictions"], "expected at least one candidate condition"
    assert body["predictions"][0]["condition"] == "Gastroenteritis"
    # Attribution: a stored result must say which model produced it.
    assert body["model_name"] == "test_condition_model"
    assert body["model_version"] == "v0"

    stored = (
        await db_session.execute(
            select(Assessment).where(Assessment.id == uuid.UUID(created["id"]))
        )
    ).scalar_one()
    assert stored.predictions
    assert stored.model_version == "v0"
    assert set(stored.recognised_symptoms) >= {"vomiting", "diarrhoea", "abdominal_pain"}


async def test_predictions_are_ranked_and_explained(client: AsyncClient) -> None:
    headers = await _onboarded(client)
    created = (
        await client.post(
            ASSESSMENTS, headers=headers, json={"symptom_text": "headache and nausea"}
        )
    ).json()
    await _answer_everything(client, headers, created["id"])

    body = (await client.post(f"{ASSESSMENTS}/{created['id']}/analyze", headers=headers)).json()

    scores = [prediction["score"] for prediction in body["predictions"]]
    assert scores == sorted(scores, reverse=True)
    top = body["predictions"][0]
    # An explanation may only cite symptoms the user actually reported.
    assert set(top["contributing_symptoms"]) <= set(body["recognised_symptoms"])


async def test_analysing_twice_is_refused(client: AsyncClient) -> None:
    """A completed assessment is an immutable record."""
    headers = await _onboarded(client)
    created = (
        await client.post(
            ASSESSMENTS, headers=headers, json={"symptom_text": "cough and runny nose"}
        )
    ).json()
    await _answer_everything(client, headers, created["id"])
    await client.post(f"{ASSESSMENTS}/{created['id']}/analyze", headers=headers)

    again = await client.post(f"{ASSESSMENTS}/{created['id']}/analyze", headers=headers)

    assert again.status_code == 409


async def test_a_completed_assessment_accepts_no_more_answers(
    client: AsyncClient,
) -> None:
    headers = await _onboarded(client)
    created = (
        await client.post(
            ASSESSMENTS, headers=headers, json={"symptom_text": "cough and runny nose"}
        )
    ).json()
    await _answer_everything(client, headers, created["id"])
    await client.post(f"{ASSESSMENTS}/{created['id']}/analyze", headers=headers)

    response = await client.post(
        f"{ASSESSMENTS}/{created['id']}/messages",
        headers=headers,
        json={"question_key": "duration", "value": 5},
    )

    assert response.status_code == 409


async def test_thin_input_is_flagged_as_low_information(client: AsyncClient) -> None:
    """One recognised symptom is not enough for a ranking to mean much."""
    headers = await _onboarded(client)

    created = (
        await client.post(ASSESSMENTS, headers=headers, json={"symptom_text": "just a cough"})
    ).json()

    assert created["low_information"] is True


# ---------------------------------------------------------------- ownership


async def test_listing_returns_only_your_own_assessments(client: AsyncClient) -> None:
    ada = await _onboarded(client, "ada@example.com")
    grace = await _onboarded(client, "grace@example.com")
    await client.post(ASSESSMENTS, headers=ada, json={"symptom_text": "headache and nausea"})

    listed = (await client.get(ASSESSMENTS, headers=grace)).json()

    assert listed == []


async def test_one_user_cannot_read_anothers_assessment(client: AsyncClient) -> None:
    """The guarantee that matters most: no token reaches another user's data."""
    ada = await _onboarded(client, "ada@example.com")
    grace = await _onboarded(client, "grace@example.com")
    created = (
        await client.post(ASSESSMENTS, headers=ada, json={"symptom_text": "headache and nausea"})
    ).json()

    response = await client.get(f"{ASSESSMENTS}/{created['id']}", headers=grace)

    # 404, not 403: the response must not confirm the id exists.
    assert response.status_code == 404


async def test_one_user_cannot_answer_or_analyse_anothers_assessment(
    client: AsyncClient,
) -> None:
    ada = await _onboarded(client, "ada@example.com")
    grace = await _onboarded(client, "grace@example.com")
    created = (
        await client.post(ASSESSMENTS, headers=ada, json={"symptom_text": "headache"})
    ).json()

    answered = await client.post(
        f"{ASSESSMENTS}/{created['id']}/messages",
        headers=grace,
        json={"question_key": "duration", "value": 3},
    )
    analysed = await client.post(f"{ASSESSMENTS}/{created['id']}/analyze", headers=grace)

    assert answered.status_code == 404
    assert analysed.status_code == 404


async def test_one_user_cannot_delete_anothers_assessment(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    ada = await _onboarded(client, "ada@example.com")
    grace = await _onboarded(client, "grace@example.com")
    created = (
        await client.post(ASSESSMENTS, headers=ada, json={"symptom_text": "headache"})
    ).json()

    response = await client.delete(f"{ASSESSMENTS}/{created['id']}", headers=grace)

    assert response.status_code == 404
    assert await db_session.scalar(select(func.count()).select_from(Assessment)) == 1


async def test_deleting_your_own_assessment_removes_its_messages(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    headers = await _onboarded(client)
    created = (
        await client.post(ASSESSMENTS, headers=headers, json={"symptom_text": "headache"})
    ).json()

    response = await client.delete(f"{ASSESSMENTS}/{created['id']}", headers=headers)

    assert response.status_code == 204
    assert await db_session.scalar(select(func.count()).select_from(Assessment)) == 0
    assert await db_session.scalar(select(func.count()).select_from(AssessmentMessage)) == 0


async def test_assessments_require_authentication(client: AsyncClient) -> None:
    assert (await client.get(ASSESSMENTS)).status_code == 401
    assert (await client.post(ASSESSMENTS, json={"symptom_text": "headache"})).status_code == 401


async def test_assessments_require_completed_onboarding(client: AsyncClient) -> None:
    """An account that has not passed the age check cannot hold medical data."""
    signup = await client.post(
        SIGNUP, json={"name": "Ada", "email": "ada@example.com", "password": PASSWORD}
    )
    headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

    response = await client.get(ASSESSMENTS, headers=headers)

    assert response.status_code == 403


async def test_unknown_assessment_id_is_not_found(client: AsyncClient) -> None:
    headers = await _onboarded(client)

    response = await client.get(f"{ASSESSMENTS}/{uuid.uuid4()}", headers=headers)

    assert response.status_code == 404
