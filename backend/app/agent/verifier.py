from app.agent.models import ModelOutput
from app.schemas.assessment import AssessmentInput, Verdict

def _norm(s: str) -> str:
    return " ".join(s.split()).lower()

def verify(inp: AssessmentInput, out: ModelOutput) -> list[str]:
    """Return a list of problems; empty means the output is acceptable."""
    problems = []
    expected = sorted(c.id for c in inp.criteria)
    got = sorted(v.criterion_id for v in out.verdicts)
    if got != expected:
        problems.append(f"verdicts must cover exactly criterion ids {expected}, got {got}")
    for v in out.verdicts:
        if v.verdict in {Verdict.MET, Verdict.SUPPORTED}:
            if not v.quote:
                problems.append(f"criterion {v.criterion_id}: supported but no quote")
            elif v.quote not in inp.evidence_text:
                problems.append(f"criterion {v.criterion_id}: quote not found in evidence")
    return problems
