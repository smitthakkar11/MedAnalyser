"""Rule-driven follow-up questioning.

A state machine over a declarative rule file, not a language model. The
questions a clinical intake needs to ask are a small, well-understood set with
clear dependencies ("only ask what the doctor said if they saw a doctor"), and
a rule table expresses that exactly, runs instantly, and can be audited.
"""

from app.services.ml.followup.question_engine import (
    AssessmentState,
    FollowUpQuestion,
    FollowUpQuestionEngine,
    get_question_engine,
)

__all__ = [
    "AssessmentState",
    "FollowUpQuestion",
    "FollowUpQuestionEngine",
    "get_question_engine",
]
