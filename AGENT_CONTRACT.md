# TrustFlow Agent <-> Backend Contract (v1)

## Call
POST /agent/assess
Body:     AssessmentInput
Response: AssessmentResult  (HTTP 200 whenever the agent ran; read `trace.outcome`)

Python equivalent: assess(AssessmentInput) -> AssessmentResult
Models live in schemas/assessment.py (single source of truth).

## Agent guarantees
- Never moves money. It only returns verdicts.
- all_supported and blockers are computed by code, never by the model.
- Exactly one verdict per input criterion (no missing or duplicate criterion_id).
- Every non-null quote is an exact substring of evidence_text; a "supported" verdict must carry a quote.
- trace.outcome != "ok"  =>  assessment is null.
- Same (milestone_id, evidence_revision) returns the cached result (idempotent).

## Backend responsibilities
- Send evidence_revision with every call. Ignore a result whose revision is older than the latest submitted one.
- assessment == null  =>  keep milestone in SUBMITTED, store trace, show "could not assess, retry".
- all_supported == true  =>  only ENABLES the client's Approve button.
- Payment happens only after the client approves; the backend then calls PayPal Sandbox.
- Client timeout >= 70s (agent aborts its own call at 60s).
- Store the full AssessmentResult JSON (assessment + trace) per call for demo/audit.

## Outcomes
ok | empty_evidence | invalid_output | provider_error