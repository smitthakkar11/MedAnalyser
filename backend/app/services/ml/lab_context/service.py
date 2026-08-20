"""Turn a user's report values into evidence an assessment can carry."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.models.report import ReportValue, ValueFlag

PROMPTS_FILE = Path(__file__).parent / "data" / "lab_symptom_prompts.json"

#: How many lab-prompted symptoms to offer in one question.
MAX_PROMPTED_SYMPTOMS = 6


@dataclass(frozen=True)
class LabFinding:
    """One laboratory value considered by an assessment.

    ``source`` is fixed to ``"report"`` and exists so that anything rendering an
    assessment can distinguish, without guessing, between a number read off a
    document and an output produced by a model.
    """

    analyte: str
    display_name: str
    value: float
    unit: str | None
    flag: ValueFlag
    reference_text: str | None
    report_id: str
    report_filename: str
    source: str = "report"

    @property
    def is_abnormal(self) -> bool:
        return self.flag in (ValueFlag.LOW, ValueFlag.HIGH)


@dataclass
class LabContext:
    """Everything the attached reports contribute to an assessment."""

    findings: list[LabFinding] = field(default_factory=list)
    #: Symptoms worth asking about given the abnormal results.
    prompted_symptoms: list[str] = field(default_factory=list)

    @property
    def abnormal(self) -> list[LabFinding]:
        return [finding for finding in self.findings if finding.is_abnormal]

    @property
    def is_empty(self) -> bool:
        return not self.findings


class LabContextService:
    """Builds lab evidence and the questions it makes worth asking."""

    def __init__(self, prompts: dict[str, list[str]] | None = None) -> None:
        self._prompts = prompts if prompts is not None else _load_prompts()

    def build(
        self,
        values: list[ReportValue],
        report_names: dict[str, str],
        *,
        already_known: set[str] | None = None,
    ) -> LabContext:
        """Assemble findings and prompted symptoms from *values*.

        Only the most recent value per analyte is carried: an assessment is
        about the user's current state, and showing three historical
        haemoglobins as separate findings would imply they are separate results
        to weigh. Trends are the medical timeline's job.
        """
        latest: dict[str, ReportValue] = {}
        for value in sorted(values, key=lambda item: item.created_at):
            latest[value.analyte] = value

        findings = [
            LabFinding(
                analyte=value.analyte,
                display_name=value.display_name,
                value=value.value,
                unit=value.unit,
                flag=value.flag,
                reference_text=value.reference_text,
                report_id=str(value.report_id),
                report_filename=report_names.get(str(value.report_id), "report"),
            )
            for value in latest.values()
        ]
        findings.sort(key=lambda finding: (not finding.is_abnormal, finding.display_name))

        return LabContext(
            findings=findings,
            prompted_symptoms=self.prompted_symptoms(findings, already_known or set()),
        )

    def prompted_symptoms(self, findings: list[LabFinding], already_known: set[str]) -> list[str]:
        """Symptoms worth asking about, given the abnormal results.

        Ranked by how many abnormal findings point at the same symptom: one
        mentioned by three out of range values is a better question than one
        mentioned by a single borderline result.
        """
        mentions: Counter[str] = Counter()
        for finding in findings:
            if not finding.is_abnormal:
                continue
            direction = "low" if finding.flag is ValueFlag.LOW else "high"
            for symptom in self._prompts.get(f"{finding.analyte}_{direction}", []):
                if symptom not in already_known:
                    mentions[symptom] += 1

        return [symptom for symptom, _ in mentions.most_common(MAX_PROMPTED_SYMPTOMS)]


def _load_prompts() -> dict[str, list[str]]:
    payload = json.loads(PROMPTS_FILE.read_text())
    return {key: list(value) for key, value in payload["prompts"].items()}


@lru_cache(maxsize=1)
def get_lab_context_service() -> LabContextService:
    return LabContextService()
