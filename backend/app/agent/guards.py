"""Code-level safety net applied to every AssessmentResult before it leaves the agent."""
from app.schemas.assessment import AssessmentInput, AssessmentResult, Verdict


def _invalid(result: AssessmentResult, reason: str) -> AssessmentResult:
    trace = result.trace.model_copy(update={"outcome": "invalid_output", "error": reason})
    return AssessmentResult(assessment=None, trace=trace)


def enforce_guards(inp: AssessmentInput, result: AssessmentResult) -> AssessmentResult:
    """Return the result untouched if it is sound, else downgrade it to invalid_output."""
    a = result.assessment
    if a is None:
        return result

    if (a.milestone_id, a.evidence_revision) != (inp.milestone_id, inp.evidence_revision):
        return _invalid(result, "milestone_id/evidence_revision mismatch with input")

    expected = sorted(c.id for c in inp.criteria)
    got = sorted(v.criterion_id for v in a.verdicts)
    if expected != got:
        return _invalid(result, f"criteria coverage mismatch: expected {expected}, got {got}")

    for v in a.verdicts:
        if v.verdict in {Verdict.MET, Verdict.SUPPORTED} and not v.quote:
            return _invalid(result, f"criterion {v.criterion_id} supported without a quote")
        if v.quote and v.quote not in inp.evidence_text:
            return _invalid(result, f"criterion {v.criterion_id} quote not found in evidence")

    return result
