"""Assessment orchestration.

Ties together the pieces that turn free text into a stored, explainable result:

    text → SymptomExtractor → AssessmentState → FollowUpQuestionEngine
                                    ↓
                       ConditionPredictionService → persisted Assessment

The route handlers stay thin; every decision about what to ask next, what the
model is given, and what gets stored lives here.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ServiceUnavailableError
from app.models.assessment import (
    Assessment,
    AssessmentMessage,
    AssessmentStatus,
    MessageRole,
)
from app.models.user import User
from app.repositories.assessment import AssessmentRepository
from app.schemas.assessment import (
    AssessmentDetail,
    AssessmentSummary,
    MessageResponse,
    PredictionResponse,
    QuestionResponse,
    SymptomOption,
)
from app.services.ml.condition_prediction.inference import (
    MIN_INFORMATIVE_SYMPTOMS,
    ConditionPredictionService,
)
from app.services.ml.feature_extraction import SymptomExtractor, get_symptom_extractor
from app.services.ml.followup import (
    AssessmentState,
    FollowUpQuestionEngine,
    get_question_engine,
)

logger = logging.getLogger(__name__)

#: How many candidates a completed assessment stores.
STORED_PREDICTION_COUNT = 5


def humanise_symptom(symptom: str) -> str:
    """`abdominal_pain` -> `Abdominal pain`, for display."""
    return symptom.replace("_", " ").capitalize()


class AssessmentService:
    """Creates, advances and analyses symptom assessments."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        extractor: SymptomExtractor | None = None,
        question_engine: FollowUpQuestionEngine | None = None,
        predictor: ConditionPredictionService | None = None,
    ) -> None:
        self._session = session
        self._repository = AssessmentRepository(session)
        # Injectable for tests; defaults are the process-wide singletons.
        self._extractor = extractor or get_symptom_extractor()
        self._questions = question_engine or get_question_engine()
        self._predictor_instance = predictor

    # ------------------------------------------------------------- lifecycle

    async def create(self, user: User, symptom_text: str) -> AssessmentDetail:
        """Start an assessment from free text.

        The extractor runs immediately so the first follow-up question can
        already account for what the user said — nobody should be asked for a
        duration they just gave.
        """
        extraction = self._extractor.extract(symptom_text)

        assessment = Assessment(
            user_id=user.id,
            status=AssessmentStatus.IN_PROGRESS,
            input_text=symptom_text,
            recognised_symptoms=extraction.symptoms,
            rejected_symptoms=extraction.negated_symptoms,
            unrecognised_terms=_unrecognised_terms(extraction.unmatched_text),
            duration_days=extraction.duration_days,
            severity=extraction.severity,
        )
        self._repository.add(assessment)
        self._repository.add_message(
            AssessmentMessage(
                assessment=assessment,
                role=MessageRole.USER,
                content=symptom_text,
            )
        )
        await self._session.commit()
        await self._session.refresh(assessment)

        logger.info(
            "Assessment created",
            extra={
                "assessment_id": str(assessment.id),
                "n_symptoms": len(extraction.symptoms),
                "n_unrecognised": len(assessment.unrecognised_terms),
            },
        )
        return await self._detail(assessment)

    async def get(self, user: User, assessment_id: uuid.UUID) -> AssessmentDetail:
        return await self._detail(await self._require(user, assessment_id))

    async def list_assessments(
        self, user: User, *, limit: int = 50, offset: int = 0
    ) -> list[AssessmentSummary]:
        rows = await self._repository.list_for_user(user.id, limit=limit, offset=offset)
        return [
            AssessmentSummary(
                id=row.id,
                status=row.status,
                input_text=row.input_text,
                top_condition=row.top_condition,
                symptom_count=len(row.recognised_symptoms or []),
                created_at=row.created_at,
                completed_at=row.completed_at,
            )
            for row in rows
        ]

    async def delete(self, user: User, assessment_id: uuid.UUID) -> None:
        assessment = await self._require(user, assessment_id)
        await self._repository.delete(assessment)
        await self._session.commit()
        logger.info("Assessment deleted", extra={"assessment_id": str(assessment_id)})

    # ---------------------------------------------------------- conversation

    async def answer(
        self, user: User, assessment_id: uuid.UUID, question_key: str, value: object
    ) -> AssessmentDetail:
        """Record an answer to a follow-up question and advance the intake."""
        assessment = await self._require(user, assessment_id)
        if assessment.is_completed:
            raise ConflictError("This assessment has already been analysed.")

        expected = self._questions.next_question(self._state(assessment))
        if expected is None:
            raise ConflictError("There are no outstanding questions for this assessment.")
        if expected.key != question_key:
            # Answering out of order would corrupt the rule state machine.
            raise ConflictError(
                f"The outstanding question is '{expected.key}', not '{question_key}'."
            )

        self._apply_answer(assessment, expected.key, value, expected.symptom_options)

        self._repository.add_message(
            AssessmentMessage(
                assessment_id=assessment.id,
                role=MessageRole.ASSISTANT,
                question_key=expected.key,
                content=expected.text,
            )
        )
        self._repository.add_message(
            AssessmentMessage(
                assessment_id=assessment.id,
                role=MessageRole.USER,
                question_key=expected.key,
                content=_render_answer(value),
            )
        )
        await self._session.commit()
        await self._session.refresh(assessment)
        return await self._detail(assessment)

    def _apply_answer(
        self,
        assessment: Assessment,
        key: str,
        value: object,
        offered: tuple[str, ...],
    ) -> None:
        """Write one answer onto the assessment."""
        match key:
            case "duration":
                assessment.duration_days = _as_float(value)
            case "severity":
                assessment.severity = str(value) if value else None
            case "previous_consultation":
                assessment.previous_consultation = bool(value)
            case "previous_diagnosis":
                assessment.previous_diagnosis = _as_text(value)
            case "previous_medication":
                assessment.previous_medication = _as_text(value)
            case "treatment_response":
                assessment.treatment_response = _as_text(value)
            case "still_taking_medication":
                assessment.still_taking_medication = bool(value)
            case "additional_symptoms":
                selected = {str(item) for item in value} if isinstance(value, list) else set()
                # Symptoms offered but not selected are a real answer — "no, I
                # don't have those" — so they are recorded as rejected. Without
                # this the engine would offer the same list again forever.
                assessment.recognised_symptoms = sorted(
                    set(assessment.recognised_symptoms) | selected
                )
                assessment.rejected_symptoms = sorted(
                    set(assessment.rejected_symptoms) | (set(offered) - selected)
                )

    # -------------------------------------------------------------- analysis

    async def analyse(self, user: User, assessment_id: uuid.UUID) -> AssessmentDetail:
        """Run the model and finalise the assessment."""
        assessment = await self._require(user, assessment_id)
        if assessment.is_completed:
            raise ConflictError("This assessment has already been analysed.")

        predictor = self._predictor()
        result = predictor.predict(assessment.recognised_symptoms, top_k=STORED_PREDICTION_COUNT)

        assessment.predictions = [prediction.model_dump() for prediction in result.predictions]
        assessment.model_name = result.model_name
        assessment.model_version = result.model_version
        assessment.status = AssessmentStatus.COMPLETED
        assessment.completed_at = datetime.now(UTC)

        await self._session.commit()
        await self._session.refresh(assessment)

        logger.info(
            "Assessment analysed",
            extra={
                "assessment_id": str(assessment.id),
                "model_version": result.model_version,
                "n_predictions": len(result.predictions),
                "low_information": result.low_information,
            },
        )
        return await self._detail(assessment)

    def _predictor(self) -> ConditionPredictionService:
        """The model, or a 503 if this deployment has none."""
        if self._predictor_instance is None:
            raise ServiceUnavailableError("The assessment model is not available on this server.")
        return self._predictor_instance

    # ------------------------------------------------------------- internals

    async def _require(self, user: User, assessment_id: uuid.UUID) -> Assessment:
        assessment = await self._repository.get_for_user(assessment_id, user.id)
        if assessment is None:
            # Deliberately the same response whether the id does not exist or
            # belongs to someone else.
            raise NotFoundError("Assessment not found.")
        return assessment

    def _state(self, assessment: Assessment) -> AssessmentState:
        """Project the stored row into the state the rule engine reads."""
        state = AssessmentState(
            recognised_symptoms=list(assessment.recognised_symptoms or []),
            rejected_symptoms=list(assessment.rejected_symptoms or []),
            duration_days=assessment.duration_days,
            severity=assessment.severity,
            previous_consultation=assessment.previous_consultation,
            previous_diagnosis=assessment.previous_diagnosis,
            previous_medication=assessment.previous_medication,
            treatment_response=assessment.treatment_response,
            still_taking_medication=assessment.still_taking_medication,
            candidate_conditions=self._candidate_conditions(assessment),
        )
        # A field extracted from the free text counts as answered: asking for it
        # again would be the intake ignoring what the user already wrote.
        for name in (
            "duration_days",
            "severity",
            "previous_consultation",
            "previous_diagnosis",
            "previous_medication",
            "treatment_response",
            "still_taking_medication",
        ):
            if getattr(state, name) is not None:
                state.answered.add(name)
        if state.duration_days is not None:
            state.answered.add("duration")
        if state.severity is not None:
            state.answered.add("severity")

        # Replay which questions have already been put to the user.
        for message in assessment.messages:
            if message.role is MessageRole.ASSISTANT and message.question_key:
                state.asked[message.question_key] += 1
                state.answered.add(message.question_key)
        return state

    def _candidate_conditions(self, assessment: Assessment) -> list[str]:
        """Current best guesses, used only to choose informative questions."""
        if not assessment.recognised_symptoms:
            return []
        try:
            result = self._predictor().predict(assessment.recognised_symptoms, top_k=5)
        except ServiceUnavailableError:
            # Questions still work without a model; they just get less targeted.
            return []
        return [prediction.condition for prediction in result.predictions]

    async def _detail(self, assessment: Assessment) -> AssessmentDetail:
        question = (
            None
            if assessment.is_completed
            else self._questions.next_question(self._state(assessment))
        )
        return AssessmentDetail(
            id=assessment.id,
            status=assessment.status,
            input_text=assessment.input_text,
            recognised_symptoms=list(assessment.recognised_symptoms or []),
            rejected_symptoms=list(assessment.rejected_symptoms or []),
            unrecognised_terms=list(assessment.unrecognised_terms or []),
            duration_days=assessment.duration_days,
            severity=assessment.severity,
            previous_consultation=assessment.previous_consultation,
            previous_diagnosis=assessment.previous_diagnosis,
            previous_medication=assessment.previous_medication,
            treatment_response=assessment.treatment_response,
            still_taking_medication=assessment.still_taking_medication,
            predictions=[
                PredictionResponse(**prediction) for prediction in (assessment.predictions or [])
            ],
            model_name=assessment.model_name,
            model_version=assessment.model_version,
            messages=[
                MessageResponse(
                    id=message.id,
                    role=message.role.value,
                    question_key=message.question_key,
                    content=message.content,
                    created_at=message.created_at,
                )
                for message in assessment.messages
            ],
            next_question=(
                QuestionResponse(
                    key=question.key,
                    text=question.text,
                    answer_type=question.answer_type,
                    help_text=question.help_text,
                    choices=list(question.choices),
                    symptom_options=[
                        SymptomOption(value=symptom, label=humanise_symptom(symptom))
                        for symptom in question.symptom_options
                    ],
                )
                if question
                else None
            ),
            low_information=len(assessment.recognised_symptoms or []) < MIN_INFORMATIVE_SYMPTOMS,
            created_at=assessment.created_at,
            completed_at=assessment.completed_at,
        )


def _unrecognised_terms(unmatched: str, *, limit: int = 12) -> list[str]:
    """Content words the extractor could not map, for vocabulary improvement."""
    stopwords = {
        "i",
        "a",
        "an",
        "and",
        "the",
        "for",
        "of",
        "to",
        "have",
        "has",
        "had",
        "am",
        "is",
        "are",
        "was",
        "were",
        "been",
        "being",
        "my",
        "me",
        "it",
        "in",
        "on",
        "at",
        "with",
        "but",
        "since",
        "about",
        "some",
        "very",
        "really",
        "quite",
        "also",
        "get",
        "got",
        "feel",
        "feeling",
        "felt",
        "last",
        "few",
        "day",
        "days",
        "week",
        "weeks",
        "month",
        "months",
        "year",
        "years",
        "hour",
        "hours",
        "ago",
        "now",
        "then",
        "not",
        "no",
        "cannot",
        "will",
        "would",
        "there",
        "that",
        "this",
    }
    seen: list[str] = []
    for word in unmatched.split():
        token = word.strip("() ")
        if len(token) > 2 and not token.isdigit() and token not in stopwords and token not in seen:
            seen.append(token)
    return seen[:limit]


def _as_float(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _as_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:300] or None


def _render_answer(value: object) -> str:
    """A readable transcript line for the stored conversation."""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(humanise_symptom(str(item)) for item in value) or "None of these"
    if value is None or str(value).strip() == "":
        return "No answer given"
    return str(value)
