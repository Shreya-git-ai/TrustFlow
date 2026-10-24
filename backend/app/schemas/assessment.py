from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Verdict(str, Enum):
    MET = "met"
    PARTIALLY_MET = "partially_met"
    NOT_MET = "not_met"
    UNABLE_TO_VERIFY = "unable_to_verify"
    # Kept for the original demo API contract. New reports use the four values above.
    SUPPORTED = "supported"
    NOT_SUPPORTED = "not_supported"
    UNCLEAR = "unclear"


class CriterionInput(BaseModel):
    id: int = Field(gt=0)
    text: str = Field(min_length=1, max_length=1000)


class AssessmentInput(BaseModel):
    milestone_id: str = Field(min_length=1, max_length=100, coerce_numbers_to_str=True)
    evidence_revision: int = Field(ge=1)
    criteria: list[CriterionInput] = Field(min_length=1, max_length=50)
    evidence_text: str = Field(max_length=20_000)
    evidence_links: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def unique_criteria(self):
        ids = [criterion.id for criterion in self.criteria]
        if len(ids) != len(set(ids)):
            raise ValueError("criterion IDs must be unique")
        return self


class CriterionVerdict(BaseModel):
    criterion_id: int
    verdict: Verdict
    quote: str | None = None  # exact text from the evidence
    reasoning: str
    requested_revision: str | None = None
    missing_or_contradictory: list[str] = Field(default_factory=list)
    recommended_next_action: str | None = None
    observed_facts: list[str] = Field(default_factory=list)
    model_inferences: list[str] = Field(default_factory=list)


class Assessment(BaseModel):
    milestone_id: str
    evidence_revision: int
    verdicts: list[CriterionVerdict]
    all_supported: bool  # computed by code, never by the model
    blockers: list[str]  # computed by code from non-supported verdicts
    overall_summary: str = ""
    limitations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_consistency(self):
        passing = {Verdict.MET, Verdict.SUPPORTED}
        expected = bool(self.verdicts) and all(v.verdict in passing for v in self.verdicts)
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
