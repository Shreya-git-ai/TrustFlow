import json
import re
import time

from pydantic import ValidationError

from app.agent.models import ModelOutput
from app.agent.prompts.assessor import PROMPT_VERSION, SYSTEM_PROMPT, build_user_prompt
from app.agent.providers.base import ModelProvider
from app.agent.verifier import downgrade_artifact_only_verdicts, verify
from app.schemas.assessment import (
    Assessment, AssessmentInput, AssessmentResult, RunTrace, Verdict,
)

MAX_EVIDENCE_CHARS = 20_000
MAX_ATTEMPTS = 2   # first try + one retry on invalid output

def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", raw, re.DOTALL)
    return m.group(1) if m else raw

def _result(provider, started, attempts, outcome, assessment=None, error=None):
    return AssessmentResult(
        assessment=assessment,
        trace=RunTrace(
            model=provider.name,
            prompt_version=PROMPT_VERSION,
            attempts=attempts,
            duration_ms=int((time.monotonic() - started) * 1000),
            outcome=outcome,
            error=error,
        ),
    )

def run_assessment(inp: AssessmentInput, provider: ModelProvider) -> AssessmentResult:
    started = time.monotonic()

    if not inp.evidence_text.strip():
        return _result(provider, started, 0, "empty_evidence", error="no evidence text")
    if len(inp.evidence_text) > MAX_EVIDENCE_CHARS:
        inp = inp.model_copy(update={"evidence_text": inp.evidence_text[:MAX_EVIDENCE_CHARS]})

    user_prompt = build_user_prompt(inp)
    last_error = "unknown"

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            raw = provider.complete_json(SYSTEM_PROMPT, user_prompt)
        except Exception as e:                      # timeout, network, auth, ...
            return _result(provider, started, attempt, "provider_error", error=f"{type(e).__name__}: assessment provider failed")

        try:
            out = ModelOutput.model_validate(json.loads(_strip_fences(raw)))
            problems = verify(inp, out)
            if problems:
                raise ValueError("; ".join(problems))
            out = downgrade_artifact_only_verdicts(inp, out)
        except (json.JSONDecodeError, ValidationError, ValueError) as e:
            last_error = str(e)[:300]
            user_prompt = build_user_prompt(inp) + f"\n\nYour previous reply was rejected: {last_error}\nFix it and reply with JSON only."
            continue

        # Code, not the model, computes the summary fields.
        passing = {Verdict.MET, Verdict.SUPPORTED}
        not_ok = [v for v in out.verdicts if v.verdict not in passing]
        limitations = []
        if inp.evidence_links:
            limitations.append("Reference links were supplied as text and were not opened or verified.")
        all_met = not not_ok
        assessment = Assessment(
            milestone_id=inp.milestone_id,
            evidence_revision=inp.evidence_revision,
            verdicts=out.verdicts,
            all_supported=all_met,
            blockers=[f"Criterion {v.criterion_id}: {v.requested_revision or v.reasoning}" for v in not_ok],
            overall_summary=f"{len(out.verdicts) - len(not_ok)} of {len(out.verdicts)} criteria are marked met based on the supplied text.",
            limitations=limitations,
        )
        return _result(provider, started, attempt, "ok", assessment=assessment)

    return _result(provider, started, MAX_ATTEMPTS, "invalid_output", error=last_error)
