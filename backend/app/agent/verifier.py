from app.agent.models import ModelOutput
import re

from app.agent.models import ModelOutput
from app.schemas.assessment import AssessmentInput, Verdict

def _norm(s: str) -> str:
    return " ".join(s.split()).lower()


_URL_RE = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_FILENAME_RE = re.compile(
    r"\b[\w-]+\.(?:zip|pdf|png|jpe?g|gif|svg|webp|docx?|xlsx?|pptx?|csv|txt|json|py|js|ts|html|css|mp4|mov)\b",
    re.IGNORECASE,
)
_ATTACHMENT_WORD_RE = re.compile(r"\b(?:attached|attachment|enclosed|uploaded)\b", re.IGNORECASE)
_ARTIFACT_CONTENT_CLAIM_RE = re.compile(
    r"\b(?:file|screenshot|image|document|report|link|url|attachment)\b.{0,80}"
    r"\b(?:shows?|proves?|contains?|demonstrates?|confirms?|depicts?|indicates?|says?|lists?)\b"
    r"|\b(?:shows?|proves?|contains?|demonstrates?|confirms?|depicts?|indicates?|says?|lists?)\b.{0,80}"
    r"\b(?:file|screenshot|image|document|report|link|url|attachment)\b",
    re.IGNORECASE,
)
_ARTIFACT_POINTER_RE = re.compile(
    r"\b(?:see|refer to|check|open|view)\s+(?:the\s+)?(?:file|screenshot|image|document|report|link|url|attachment)\b",
    re.IGNORECASE,
)


def _quote_is_artifact_reference(quote: str) -> bool:
    """Whether a quote only points to an artifact or asserts what it contains."""
    quote = quote.strip()
    if not quote:
        return False
    if _URL_RE.search(quote) or _FILENAME_RE.search(quote):
        return True
    # The evidence is plain text; a statement about an uninspected artifact is
    # not proof of the artifact's contents, even when the statement sounds sure.
    return bool(
        _ATTACHMENT_WORD_RE.search(quote)
        or _ARTIFACT_CONTENT_CLAIM_RE.search(quote)
        or _ARTIFACT_POINTER_RE.search(quote)
    )


def downgrade_artifact_only_verdicts(inp: AssessmentInput, out: ModelOutput) -> ModelOutput:
    """Downgrade passes supported only by a quoted attachment/link reference."""
    revised = []
    for verdict in out.verdicts:
        if (
            verdict.verdict in {Verdict.MET, Verdict.SUPPORTED}
            and verdict.quote
            and _quote_is_artifact_reference(verdict.quote)
        ):
            revised.append(verdict.model_copy(update={
                "verdict": Verdict.UNABLE_TO_VERIFY,
                "reasoning": "The evidence only references an attachment or link; its contents were not inspected.",
                "requested_revision": "Provide substantive evidence in the text or an independently verifiable description of the relevant contents.",
                "missing_or_contradictory": [*verdict.missing_or_contradictory, "The cited text refers to an uninspected attachment or link."],
                "recommended_next_action": "Provide the relevant facts directly in the evidence text or have the attachment reviewed.",
            }))
        else:
            revised.append(verdict)
    return out.model_copy(update={"verdicts": revised})

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
