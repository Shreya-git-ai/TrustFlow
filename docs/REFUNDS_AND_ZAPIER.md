# TrustFlow workflow events and Zapier

TrustFlow writes business events to its PostgreSQL outbox in the same transaction as the associated evidence, assessment, decision, payment, or refund update. The worker sends user-facing notification emails through TrustFlow's SMTP service and can send non-email automation events to Zapier. TrustFlow remains the source of truth; Zapier cannot approve milestones or change payment state.

## Event envelope

Every delivered event uses this envelope:

```json
{
  "event": "evidence.submitted",
  "event_type": "evidence.submitted",
  "event_id": "stable-event-uuid",
  "occurred_at": "2026-10-30T12:34:56Z",
  "project_id": "<project UUID>",
  "milestone_id": "<milestone UUID>",
  "data": {
    "project_id": "<project UUID>",
    "milestone_id": "<milestone UUID>"
  }
}
```

Event-specific fields are available both at the top level (for easier Zapier field mapping) and under `data` for compatibility with existing consumers. For events that generate email, recipient addresses are removed from the Zapier copy; TrustFlow sends the email itself over SMTP.

`event_id` is stable when the same logical event is retried. The outbox records the event creation timestamp and reuses it for delivery retries. Delivery is at least once: if Zapier receives a request but its response is lost, the outbox may send it again. Use `event_id` as a downstream deduplication key when the Zap writes to a system that supports idempotency.

Milestone links use the configured `TRUSTFLOW_FRONTEND_URL` and open the project/milestone in TrustFlow. They require a signed-in user who is a member of that project; the URL itself grants no access. Configure the public frontend origin in deployed environments. Locally, links default to `http://localhost:5173` outside production.

## Supported business events

| Event | Recipient IDs | Event data |
|---|---|---|
| `project.invited` | Freelancer | `project_title` / `project_name`, `project_id`, `client_id`, `workspace_url` |
| `milestone.created` | Freelancer | `project_title` / `project_name`, `project_id`, `milestone_id`, `milestone_title`, `amount`, `currency`, `review_url` |
| `milestone.updated` | Freelancer | `project_title` / `project_name`, `project_id`, `milestone_id`, `milestone_title`, `amount`, `currency`, `review_url` |
| `evidence.submitted` | `client_id` | `freelancer_id`, `project_id`, `milestone_id`, `evidence_revision`, `file_attached`, `review_url` |
| `assessment.completed` | `client_id` | `project_id`, `milestone_id`, `assessment_id`, `evidence_revision`, `overall_result`, `all_met`, `criterion_summary` (criterion IDs and result only), `blocker_count`, `stale`, `advisory`, `client_approval_required`, `review_url` |
| `revision.requested` | `freelancer_id` | `client_id`, `project_id`, `milestone_id`, `evidence_revision`, `assessment_id`, `review_url` |
| `milestone.approved` | `freelancer_id` | `client_id`, `project_id`, `milestone_id`, `evidence_revision`, `assessment_id`, `review_url` |
| `payment.captured` | Client and freelancer | `client_id`, `freelancer_id`, `payment_id`, `project_id`, `milestone_id`, `capture_id`, `amount`, `currency`, confirmed `status`, `review_url` |
| `PAYMENT.CAPTURE.REFUNDED` | Client | `refund_id`, `capture_id`, `payment_id`, `proposal_id`, `refund_amount`, `cumulative_refunded_amount`, `currency`, and optional Zendesk/Slack references |

For email-triggering events, the Zapier copy omits email addresses and invitation URLs that contain an email address. It also contains no evidence text, uploaded file contents, Gemini prompts or quotes, or PayPal access tokens. Some event display names remain available for non-email automations. Assessment summaries include only criterion IDs and verdicts, not criterion wording or the model's private reasoning. SMTP recipient addresses stay in the backend delivery path.

`assessment.completed` means that an assessment report was successfully persisted. Its `advisory` field is `true`; `client_approval_required` is also `true`. Neither `all_met: true` nor any other assessment field means the milestone was approved. The client must still explicitly approve it in TrustFlow.

`payment.captured` is queued only after a confirmed PayPal capture response, verified PayPal completion webhook, or successful reconciliation. A request being sent, a user returning from PayPal, or an uncertain `capture_pending` result does not produce this event.

The existing operational events (`project.created`, `milestone.updated`, `assessment.failed`, `milestone.revoked`, `payment.order_created`, and `payment.authorized`) continue to use the same envelope/outbox. `milestone.revision_requested` remains an audit event; the Zapier business event for that action is `revision.requested`.

## Configure the worker and Catch Hooks

1. Set `ZAPIER_WEBHOOK_URL` on the backend API and its outbox worker using the same secret Catch Hook URL. It accepts one Catch Hook URL or Zapier's combined Catch Hook URL format. On Render these are separate services and both need the variable.
2. Each Zapier Catch Hook trigger gets its own URL. Create a separate Zap for each event you want to handle. If all those hooks are owned by the same Zapier user, combine the final token portions into the Catch Hook URL format described in Zapier's [webhook setup guide](https://help.zapier.com/hc/en-us/articles/8496288690317-Trigger-Zap-workflows-from-webhooks), then set that combined URL as `ZAPIER_WEBHOOK_URL`. Hooks owned by different users cannot be combined this way.
3. Every Zap should filter on its exact `event` value before running an action. This is important because a combined Catch Hook address sends every TrustFlow event to each configured Zap.
4. Keep Catch Hook URLs secret. They are stored only in backend environment settings; never put them in frontend code, browser-visible settings, or public documentation.
5. The worker leaves failed events pending, stores attempts, a sanitized `last_error`, and the next retry time, and uses a capped exponential delay (up to one hour). `backend/scripts/deliver_events.py` drains up to 50 pending rows. The Render blueprint runs it every 15 minutes. If deploying on Vercel or another platform without that Render cron, configure a scheduled worker to run this script against the same database.

The checked-in outbox schema already provides a unique dedupe key, creation timestamp, attempts, delivery status, lock expiry, retry time, error field, and delivered timestamp. No additional event table or migration is needed.

Zapier currently documents Webhooks by Zapier Catch Hook as unavailable on its Free plan and available on Professional, Team, and Enterprise plans. Plans and connector capabilities can change; verify Catch Hook, Filters, connected-app actions, task limits, and account ownership in your own Zapier workspace before building the flows. If your plan cannot filter each event from the shared hook, do not enable action steps that could run on the wrong event; use a plan or routing design that supports safe event filtering.

## Recommended Zaps

For each Zap, choose **Webhooks by Zapier → Catch Hook**, use the combined hook URL above, and add a Filter step for the exact event name. Zapier's [Catch Hook guide](https://help.zapier.com/hc/en-us/articles/8496288690317-Trigger-Zap-workflows-from-webhooks) describes trigger setup and testing.

Do not add email actions to these Zaps. TrustFlow creates event-specific messages and sends them through the configured SMTP server. Use Zapier for support-system, chat, or other non-email actions.

### 1. Evidence submitted → notify the client

- **Filter:** `event` exactly equals `evidence.submitted`.
- **Map:** `data.project_id`, `data.milestone_id`, `data.evidence_revision`, and `data.review_url`.
- **Action:** Use a non-email action if needed. TrustFlow emails the client that a new evidence revision is ready; the evidence itself is never sent by email.
- **Safe test:** Submit sample evidence in a test project and verify the SMTP message and authenticated milestone link.

### Project invitation → notify the freelancer

- **Filter:** `event` exactly equals `project.invited`.
- **Map:** `data.project_title`, `data.project_id`, and `data.workspace_url`.
- **Action:** TrustFlow sends the invitation email through SMTP. The freelancer signs in and accepts the invite in their workspace.
- **Safe test:** Create a synthetic project for a test freelancer and verify the TrustFlow invitation message.

### Milestone created → notify the freelancer

- **Filter:** `event` exactly equals `milestone.created`.
- **Map:** `data.milestone_title`, `data.project_id`, and `data.review_url`.
- **Action:** TrustFlow emails the freelancer the milestone title, amount, and authenticated milestone link.
- **Safe test:** Add a synthetic milestone and verify the TrustFlow message reaches the freelancer's test inbox.

### Milestone terms updated → notify the freelancer

- **Filter:** `event` exactly equals `milestone.updated`.
- **Map:** `data.milestone_title` and `data.review_url`.
- **Action:** Summarize that the client changed milestone terms and link to the current terms in TrustFlow.
- **Safe test:** Edit a synthetic milestone before evidence has been submitted.

### 2. Assessment completed → notify the client

- **Filter:** `event` exactly equals `assessment.completed`. Optionally branch on `data.stale` so stale results are clearly labeled or suppressed.
- **Map:** `data.overall_result`, `data.criterion_summary`, `data.blocker_count`, `data.stale`, `data.advisory`, `data.client_approval_required`, and `data.review_url`.
- **Action:** Send the summary and link. State that the report is advisory and the client must make the decision in TrustFlow. Do not present the result as an approval.
- **Safe test:** Submit test evidence, run an assessment, and verify the test inbox receives an advisory message. No evidence text or model prompt is sent to Zapier.

### 3. Revision requested → notify the freelancer

- **Filter:** `event` exactly equals `revision.requested`.
- **Map:** `data.project_id`, `data.milestone_id`, `data.evidence_revision`, and `data.review_url`.
- **Action:** TrustFlow emails the freelancer about the requested revision and links to TrustFlow to read feedback. The feedback note itself is not sent to Zapier.
- **Safe test:** Request a revision on a test project and confirm the SMTP email links to the correct milestone.

### 4. Milestone approved → notify the freelancer

- **Filter:** `event` exactly equals `milestone.approved`.
- **Map:** `data.project_id`, `data.milestone_id`, `data.evidence_revision`, and `data.review_url`.
- **Action:** TrustFlow emails the freelancer that the client approved this revision. Do not use the Zap to initiate capture or change TrustFlow approval/payment state.
- **Safe test:** Approve a passing test milestone and confirm the TrustFlow email arrives only after approval is persisted.

### 5. Payment captured → notify parties or update a tracker

- **Filter:** `event` exactly equals `payment.captured` and `data.status` equals `captured`.
- **Map:** `data.payment_id`, `data.project_id`, `data.milestone_id`, `data.amount`, `data.currency`, `data.capture_id`, and `data.review_url`.
- **Action:** TrustFlow emails both project members after a confirmed capture. Treat this as a capture notice, not a payout confirmation; TrustFlow does not split or pay funds out to freelancers.
- **Safe test:** Use a PayPal Sandbox buyer account and confirm neither member receives a message while capture is uncertain.

### 6. Refund completed → retain the current support workflow

- **Filter:** `event` exactly equals `PAYMENT.CAPTURE.REFUNDED`.
- TrustFlow emails the client after the verified refund completion webhook. Keep the Zap focused on ticket or Slack actions.
- **Zendesk mapping:** If `data.zendesk_ticket_id` is present, add an internal note with the refund ID and amount and set the ticket to **Solved**. Solved tickets can later be closed by Zendesk's configured process; a closed ticket cannot be reopened.
- **Slack mapping:** If `data.slack_channel_id` and `data.slack_thread_ts` are present, reply to that thread with the refund confirmation and add the `white_check_mark` reaction. Slack threads do not have a ticket status to close.
- **Safe test:** Refund a PayPal Sandbox capture and wait for the signature-verified `PAYMENT.CAPTURE.REFUNDED` webhook. Do not test by posting a forged payload to the public PayPal webhook route.

Zendesk ticket updates use its [Tickets API](https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/). Slack thread replies use [`chat.postMessage`](https://api.slack.com/methods/chat.postMessage); reactions use [`reactions.add`](https://api.slack.com/methods/reactions.add).

## Agent-proposed refund review

The existing `client` account is the merchant/payer. A trusted agent can create a proposal through `POST /agent/refund-proposals`; it cannot send a refund. Only the authenticated project client can approve or reject proposals in **Payments → Agent-proposed refunds**.

Set a long random `TRUSTFLOW_AGENT_TOKEN` on the backend. The agent endpoint requires it as a bearer token. `proposal_key` is an idempotency key and must be reused when retrying the same proposal.

```http
POST /agent/refund-proposals
Authorization: Bearer <TRUSTFLOW_AGENT_TOKEN>
Content-Type: application/json
```

```json
{
  "payment_id": "<payment UUID from GET /payments>",
  "proposal_key": "refund-review-<stable-agent-key>",
  "amount": "12.50",
  "reason": "The post-delivery review found that an agreed acceptance requirement was not met.",
  "zendesk_ticket_id": 12345,
  "slack_channel_id": "C0123456789",
  "slack_thread_ts": "1729876543.123456"
}
```

Approved refunds use [PayPal's captured-payment refund endpoint](https://developer.paypal.com/api/payments/v2/captures-refund) with a stable `PayPal-Request-Id` and proposal UUID as `custom_id`. Pending proposals and provider refunds reserve the remaining refundable balance. A timeout stays in `processing`; the same PayPal request ID is reused for retry. Payment totals and the support event update only after PayPal confirms the refund through its verified webhook.

Subscribe the PayPal app to `PAYMENT.CAPTURE.COMPLETED` and `PAYMENT.CAPTURE.REFUNDED`, set its registered webhook ID as `PAYPAL_WEBHOOK_ID`, and use credentials from the same Sandbox or Live app. The backend verifies the PayPal signature before processing either event.

If no Zendesk ticket ID is attached, `data.ticket_lookup_key` is the PayPal capture ID; a Zap may use it to find a ticket only if the connected tracker has a matching custom field. Slack thread metadata must be supplied when creating the proposal.

## Manual end-to-end test

1. Create or choose a test client account and test freelancer account with inboxes you control. Create a test project and milestone between them.
2. In Zapier, turn on one non-email Zap at a time. Use **Catch Hook → Filter by exact `event` → support or chat action**. No email action is needed; TrustFlow sends those messages directly through SMTP.
3. Use the TrustFlow frontend to trigger the event: create a project, submit evidence, run an assessment, request a revision, approve an eligible assessment, or complete a PayPal Sandbox capture. Refund testing requires a Sandbox refund and the verified PayPal webhook. Do not send forged webhook requests.
4. If delivery is queued, run `../venv/bin/python scripts/deliver_events.py` from `backend/` to drain due events. Check the Zap's run history and the controlled inboxes.
5. Confirm the TrustFlow emails have the expected recipient and event, use the authenticated `review_url`, and contain no evidence text or private feedback. Test pending/uncertain capture and confirm it sends no payment-captured email.

Signup verification and password-reset links are also sent directly through SMTP. Zapier does not receive authentication links or notification recipient addresses.
