# TrustFlow assessment contract

The assessor is an evidence reviewer. It returns a report to the authenticated workflow API; it has no authority to approve milestones or operate PayPal.

## Runtime path

The application does not expose the old unscoped `POST /agent/assess` route. A project client requests an assessment through:

```text
POST /milestones/{milestone_id}/assessments
```

The route obtains milestone criteria and the latest evidence revision from PostgreSQL. It sends the persisted text and recorded links to `app.agent.orchestrator.run_assessment`, then stores the result in `assessment_reports` and `assessment_findings`. A report is stale when evidence changed while Gemini was running. Reports also record the report/prompt version, model, outcome, and limitations.

## Model input and output

The model receives the milestone criteria, evidence text, and reference URLs explicitly labeled as unverified. File content is not supplied. The model returns exactly one finding for each criterion, with one of:

- `met`
- `partially_met`
- `not_met`
- `unable_to_verify`

Each finding can include an exact evidence quote, explanation, missing or contradictory proof, recommended next action, observed facts, and model inferences. The code verifies criterion coverage and requires exact quote matches for `met`. The code computes the overall summary, blockers, and `all_supported` value; the model cannot set those fields.

Legacy verdict values remain parseable for the old unit fixtures, but new prompt responses use the four statuses above.

## Trust boundaries

- Treat evidence, criteria, URLs, and model output as untrusted.
- Do not fetch links, inspect files, execute tools, or claim checks that were not performed.
- Assessment does not modify milestone approval or payment state.
- A current successful assessment with all criteria marked `met` is only a prerequisite. The client must still submit an explicit authenticated approval decision.
- Capture separately verifies the persisted client decision, assessment and evidence revision, and PayPal authorization.
- Provider failure, empty text, invalid output, or stale evidence must not approve a milestone.

The model provider is configured with `GEMINI_API_KEY` and `TRUSTFLOW_MODEL`; an optional `TRUSTFLOW_FALLBACK_MODEL` can be used for eligible transient failures. The usual test suite uses a fake provider and does not require credentials.
