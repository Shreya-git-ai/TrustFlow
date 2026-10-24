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
## What the backend should do with the result

- Call `POST /agent/assess` after saving the evidence. `milestone_id` is the UUID string; `evidence_revision` is the number of evidence rows for that milestone.
- Store the response in `evidence.assessment` (JSONB) on the matching evidence row.
- Write an `audit_events` row: `event_type` = `assessment_completed` or `assessment_failed`, `actor_type` = `ai`, `details` = model, prompt_version, duration_ms, outcome.
- If `assessment` is null (failed run), keep the milestone as `submitted` and show a retry.
- If `all_supported` is true, the client's Approve button can be enabled. The agent never approves or pays.
- Evidence text over 20,000 characters is rejected with 422; show a limit message in the form.
- Decision: add `assessed` to `milestones.status` (agreed with the backend owner). Transitions: `submitted` -> `assessed` only when `all_supported` is true; failed or unsupported runs stay `submitted`; approve is allowed only from `assessed`; new evidence after `assessed` returns the milestone to `submitted`. The existing database needs an ALTER on the status CHECK constraint, not just a schema.sql edit.

