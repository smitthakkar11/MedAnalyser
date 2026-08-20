"""Symptom assessment endpoints.

The flow a client follows:

    POST   /api/assessments                  free text in, first question out
    POST   /api/assessments/{id}/messages    answer, get the next question
    POST   /api/assessments/{id}/analyze     run the model, finalise
    GET    /api/assessments/{id}             read it back

Every endpoint requires an authenticated, age-verified user, and every query is
scoped to that user's id in the repository — the identity always comes from the
verified token, never from the path or body.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.api.deps import ConditionPredictor, DbSession, OnboardedUser
from app.schemas.assessment import (
    AnswerSubmission,
    AssessmentCreate,
    AssessmentDetail,
    AssessmentSummary,
    MessageResponse,
)
from app.services.assessment import AssessmentService

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.post(
    "",
    response_model=AssessmentDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Start an assessment from free-text symptoms",
)
async def create_assessment(
    payload: AssessmentCreate,
    current_user: OnboardedUser,
    session: DbSession,
    predictor: ConditionPredictor,
) -> AssessmentDetail:
    """Extract symptoms from what the user wrote and return the first question.

    Nothing is predicted yet: the model needs several symptoms before a ranking
    is worth showing, so the intake gathers more first.
    """
    return await AssessmentService(session, predictor=predictor).create(
        current_user, payload.symptom_text
    )


@router.get("", response_model=list[AssessmentSummary], summary="List your assessments")
async def list_assessments(
    current_user: OnboardedUser,
    session: DbSession,
    predictor: ConditionPredictor,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[AssessmentSummary]:
    return await AssessmentService(session, predictor=predictor).list_assessments(
        current_user, limit=limit, offset=offset
    )


@router.get(
    "/{assessment_id}",
    response_model=AssessmentDetail,
    summary="Read one assessment",
    responses={404: {"description": "No such assessment for this user."}},
)
async def get_assessment(
    assessment_id: uuid.UUID,
    current_user: OnboardedUser,
    session: DbSession,
    predictor: ConditionPredictor,
) -> AssessmentDetail:
    return await AssessmentService(session, predictor=predictor).get(current_user, assessment_id)


@router.delete(
    "/{assessment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an assessment",
)
async def delete_assessment(
    assessment_id: uuid.UUID,
    current_user: OnboardedUser,
    session: DbSession,
    predictor: ConditionPredictor,
) -> None:
    await AssessmentService(session, predictor=predictor).delete(current_user, assessment_id)


@router.post(
    "/{assessment_id}/messages",
    response_model=AssessmentDetail,
    summary="Answer the outstanding follow-up question",
    responses={409: {"description": "No outstanding question, or answered out of order."}},
)
async def answer_question(
    assessment_id: uuid.UUID,
    payload: AnswerSubmission,
    current_user: OnboardedUser,
    session: DbSession,
    predictor: ConditionPredictor,
) -> AssessmentDetail:
    """Record an answer and return the next question, if any."""
    return await AssessmentService(session, predictor=predictor).answer(
        current_user, assessment_id, payload.question_key, payload.value
    )


@router.get(
    "/{assessment_id}/messages",
    response_model=list[MessageResponse],
    summary="The intake conversation",
)
async def list_messages(
    assessment_id: uuid.UUID,
    current_user: OnboardedUser,
    session: DbSession,
    predictor: ConditionPredictor,
) -> list[MessageResponse]:
    detail = await AssessmentService(session, predictor=predictor).get(current_user, assessment_id)
    return detail.messages


@router.post(
    "/{assessment_id}/analyze",
    response_model=AssessmentDetail,
    summary="Run the model and finalise the assessment",
    responses={
        409: {"description": "The assessment has already been analysed."},
        503: {"description": "The trained model is not available on this server."},
    },
)
async def analyse_assessment(
    assessment_id: uuid.UUID,
    current_user: OnboardedUser,
    session: DbSession,
    predictor: ConditionPredictor,
) -> AssessmentDetail:
    """Predict candidate conditions and store the result with its model version.

    Output is a ranked set of **possible** conditions requiring professional
    evaluation, never a diagnosis.
    """
    return await AssessmentService(session, predictor=predictor).analyse(
        current_user, assessment_id
    )
