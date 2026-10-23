from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Verdict(str, Enum):
    SUPPORTED = "supported"
    NOT_SUPPORTED = "not_supported"
    UNCLEAR = "unclear"


class CriterionInput(BaseModel):
    id: int
    text: str


class AssessmentInput(BaseModel):
    milestone_id: str
    evidence_revision: int
    criteria: list[CriterionInput] = Field(min_length=1)
    evidence_text: str
    evidence_links: list[str] = []


class CriterionVerdict(BaseModel):
    criterion_id: int
    verdict: Verdict
    quote: str | None = None  # exact text from the evidence
    reasoning: str
    requested_revision: str | None = None


class Assessment(BaseModel):
    milestone_id: str
    evidence_revision: int
    verdicts: list[CriterionVerdict]
    all_supported: bool  # computed by code, never by the model
    blockers: list[str]  # computed by code from non-supported verdicts

    @model_validator(mode="after")
    def check_consistency(self):
        expected = all(v.verdict == Verdict.SUPPORTED for v in self.verdicts)
        if self.all_supported != expected:
            raise ValueError("all_supported does not match the verdicts")
        return self


class RunTrace(BaseModel):
    model: str
    prompt_version: str
    attempts: int
    duration_ms: int
    outcome: Literal["ok", "empty_evidence", "invalid_output", "provider_error"]
    error: str | None = None


class AssessmentResult(BaseModel):
    assessment: Assessment | None  # None means: keep milestone in SUBMITTED, log it
    trace: RunTrace