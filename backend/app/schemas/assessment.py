"""Request and response schemas for symptom assessments."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.assessment import AssessmentStatus

MAX_INPUT_LENGTH = 2000


class AssessmentCreate(BaseModel):
    """Start an assessment from what the user typed."""

    symptom_text: str = Field(
        min_length=3,
        max_length=MAX_INPUT_LENGTH,
        description="Symptoms in the user's own words.",
    )

    @field_validator("symptom_text")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("Please describe your symptoms in a little more detail.")
        return stripped


class AnswerSubmission(BaseModel):
    """Answer the outstanding follow-up question."""

    question_key: str = Field(min_length=1, max_length=60)
    #: Shape depends on the question's `answer_type`: a string, a boolean, a
    #: number, or a list of symptom names for `symptom_check`.
    value: str | bool | float | list[str] | None = None

    @field_validator("value")
    @classmethod
    def _bound_text(cls, value: Any) -> Any:
        if isinstance(value, str) and len(value) > 300:
            raise ValueError("Answer is too long.")
        if isinstance(value, list) and len(value) > 40:
            raise ValueError("Too many symptoms selected.")
        return value


class SymptomOption(BaseModel):
    """A symptom offered in a `symptom_check` question."""

    value: str
    label: str


class QuestionResponse(BaseModel):
    """A follow-up question for the user."""

    key: str
    text: str
    answer_type: Literal["text", "choice", "boolean", "number", "duration", "symptom_check"]
    help_text: str | None = None
    choices: list[str] = Field(default_factory=list)
    #: For `symptom_check`: canonical symptom names, with display labels.
    symptom_options: list[SymptomOption] = Field(default_factory=list)


class MessageResponse(BaseModel):
    """One turn of the intake conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    question_key: str | None
    content: str
    created_at: datetime


class PredictionResponse(BaseModel):
    """One candidate condition.

    `score` is a relative model output, **not** a calibrated probability and not
    a statement of clinical likelihood.
    """

    condition: str
    score: float
    contributing_symptoms: list[str] = Field(default_factory=list)


class LabFindingResponse(BaseModel):
    """A laboratory value an assessment considered.

    `source` is always `"report"`. It exists so a client can tell, without
    inferring, that this number was read off a document — as opposed to a
    prediction, which is produced by the model and labelled as such.
    """

    analyte: str
    display_name: str
    value: float
    unit: str | None
    flag: str
    reference_text: str | None
    report_id: uuid.UUID
    report_filename: str
    source: Literal["report"] = "report"


class LinkedReportResponse(BaseModel):
    """A report attached to an assessment."""

    id: uuid.UUID
    original_filename: str
    report_date: date | None
    value_count: int
    abnormal_count: int


class AssessmentSummary(BaseModel):
    """An assessment as it appears in a list."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: AssessmentStatus
    input_text: str
    top_condition: str | None
    symptom_count: int
    created_at: datetime
    completed_at: datetime | None


class AssessmentDetail(BaseModel):
    """A full assessment, including how its result was produced."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: uuid.UUID
    status: AssessmentStatus
    input_text: str

    recognised_symptoms: list[str]
    rejected_symptoms: list[str]
    unrecognised_terms: list[str]
    duration_days: float | None
    severity: str | None

    previous_consultation: bool | None
    previous_diagnosis: str | None
    previous_medication: str | None
    treatment_response: str | None
    still_taking_medication: bool | None

    predictions: list[PredictionResponse] = Field(default_factory=list)
    model_name: str | None
    model_version: str | None

    #: Reports attached to this assessment.
    linked_reports: list[LinkedReportResponse] = Field(default_factory=list)
    #: Laboratory values from those reports. Carried **alongside** the model's
    #: predictions, never merged into them: the condition model is trained on
    #: symptoms only and has never seen a laboratory value.
    lab_findings: list[LabFindingResponse] = Field(default_factory=list)

    messages: list[MessageResponse] = Field(default_factory=list)
    #: The outstanding question, or null when the intake is ready to analyse.
    next_question: QuestionResponse | None = None
    #: True when too few symptoms were recognised for a ranking to mean much.
    low_information: bool = False

    created_at: datetime
    completed_at: datetime | None
