# TrustFlow workflow events and Zapier

TrustFlow writes business events to its PostgreSQL outbox in the same transaction as the associated evidence, assessment, decision, payment, or refund update. A separate worker sends those events to Zapier. Zapier is a notification/automation destination; TrustFlow remains the source of truth and Zapier cannot approve milestones or change payment state.

## Event envelope

Every delivered event uses this envelope:

```json
{
  "event": "evidence.submitted",
  "event_type": "evidence.submitted",
  "event_id": "stable-event-uuid",
  "occurred_at": "2026-10-30T12:34:56Z",
  "data": {
    "project_id": "<project UUID>",
    "milestone_id": "<milestone UUID>"
  }
}
```

`event_id` is stable when the same logical event is retried. The outbox records the event creation timestamp and reuses it for delivery retries. Delivery is at least once: if Zapier receives a request but its response is lost, the outbox may send it again. Use `event_id` as a downstream deduplication key when the Zap writes to a system that supports idempotency.

Milestone links use the configured `TRUSTFLOW_FRONTEND_URL` and open the project/milestone in TrustFlow. They require a signed-in user who is a member of that project; the URL itself grants no access. Configure the public frontend origin in deployed environments. Locally, links default to `http://localhost:5173` outside production.

## Supported business events

| Event | Recipient IDs | Event data |
|---|---|---|
| `evidence.submitted` | `client_id` | `recipient_email`, `freelancer_id`, `project_id`, `milestone_id`, `evidence_revision`, `file_attached`, `review_url` |
| `assessment.completed` | `client_id` | `recipient_email`, `project_id`, `milestone_id`, `assessment_id`, `evidence_revision`, `overall_result`, `all_met`, `criterion_summary` (criterion IDs and result only), `blocker_count`, `stale`, `advisory`, `client_approval_required`, `review_url` |
| `revision.requested` | `freelancer_id` | `recipient_email`, `client_id`, `project_id`, `milestone_id`, `evidence_revision`, `assessment_id`, `review_url` |
| `milestone.approved` | `freelancer_id` | `recipient_email`, `client_id`, `project_id`, `milestone_id`, `evidence_revision`, `assessment_id`, `review_url` |
| `payment.captured` | Client and freelancer | `client_email`, `freelancer_email`, `client_id`, `freelancer_id`, `payment_id`, `project_id`, `milestone_id`, `capture_id`, `amount`, `currency`, confirmed `status`, `review_url` |
| `PAYMENT.CAPTURE.REFUNDED` | `recipient_email` is the client | `refund_id`, `capture_id`, `payment_id`, `proposal_id`, `refund_amount`, `cumulative_refunded_amount`, `currency`, and optional Zendesk/Slack references |

The outbox contains no evidence text, uploaded file contents, Gemini prompts or quotes, PayPal access tokens, or user names. For email notifications, each event includes only the address of its intended recipient; `payment.captured` includes both project members' addresses. These addresses are delivered to the Zapier account configured by the project operator, so restrict access to that Zapier workspace and use test accounts during setup. Assessment summaries intentionally include only criterion IDs and verdicts, not criterion wording or the model's private reasoning.

`assessment.completed` means that an assessment report was successfully persisted. Its `advisory` field is `true`; `client_approval_required` is also `true`. Neither `all_met: true` nor any other assessment field means the milestone was approved. The client must still explicitly approve it in TrustFlow.

`payment.captured` is queued only after a confirmed PayPal capture response, verified PayPal completion webhook, or successful reconciliation. A request being sent, a user returning from PayPal, or an uncertain `capture_pending` result does not produce this event.

The existing operational events (`project.created`, `milestone.updated`, `assessment.failed`, `milestone.revoked`, `payment.order_created`, and `payment.authorized`) continue to use the same envelope/outbox. `milestone.revision_requested` remains an audit event; the Zapier business event for that action is `revision.requested`.

## Configure the worker and Catch Hooks

1. Set `ZAPIER_WEBHOOK_URL` on the **backend only**. It accepts one Catch Hook URL or Zapier's combined Catch Hook URL format.
2. Each Zapier Catch Hook trigger gets its own URL. Create a separate Zap for each event you want to handle. If all those hooks are owned by the same Zapier user, combine the final token portions into the Catch Hook URL format described in Zapier's [webhook setup guide](https://help.zapier.com/hc/en-us/articles/8496288690317-Trigger-Zap-workflows-from-webhooks), then set that combined URL as `ZAPIER_WEBHOOK_URL`. Hooks owned by different users cannot be combined this way.
3. Every Zap should filter on its exact `event` value before running an action. This is important because a combined Catch Hook address sends every TrustFlow event to each configured Zap.
4. Keep Catch Hook URLs secret. They are stored only in backend environment settings; never put them in frontend code, browser-visible settings, or public documentation.
5. The worker leaves failed events pending, stores attempts, a sanitized `last_error`, and the next retry time, and uses a capped exponential delay (up to one hour). `backend/scripts/deliver_events.py` drains up to 50 pending rows. The Render blueprint runs it every 15 minutes. If deploying on Vercel or another platform without that Render cron, configure a scheduled worker to run this script against the same database.

The checked-in outbox schema already provides a unique dedupe key, creation timestamp, attempts, delivery status, lock expiry, retry time, error field, and delivered timestamp. No additional event table or migration is needed.

Zapier currently documents Webhooks by Zapier Catch Hook as unavailable on its Free plan and available on Professional, Team, and Enterprise plans. Plans and connector capabilities can change; verify Catch Hook, Filters, connected-app actions, task limits, and account ownership in your own Zapier workspace before building the flows. If your plan cannot filter each event from the shared hook, do not enable action steps that could run on the wrong event; use a plan or routing design that supports safe event filtering.

## Recommended Zaps

For each Zap, choose **Webhooks by Zapier → Catch Hook**, use the combined hook URL above, and add a Filter step for the exact event name. Zapier's [Catch Hook guide](https://help.zapier.com/hc/en-us/articles/8496288690317-Trigger-Zap-workflows-from-webhooks) describes trigger setup and testing.

To send email, add **Email by Zapier → Send Outbound Email**, or use an account you control through Gmail, Outlook, or SMTP. Map the event's recipient field into **To**. During testing, use project accounts whose email addresses lead to test inboxes. Email actions send real messages when tested. Zapier currently documents Email by Zapier limits of 5 emails per account per day on Free/Trial and 10 per account per hour on paid plans; for Free/Trial action tests, delivery is directed to the Zapier account email. Check the current [Email by Zapier setup and limits](https://help.zapier.com/hc/en-us/articles/8496305915917-Send-emails-in-Zaps) before using it for live notifications.

### 1. Evidence submitted → notify the client

- **Filter:** `event` exactly equals `evidence.submitted`.
- **Map:** `data.recipient_email`, `data.project_id`, `data.milestone_id`, `data.evidence_revision`, and `data.review_url`.
- **Action:** Send an email saying a new evidence revision is ready for review, with the milestone link. Do not include the evidence itself.
- **Safe test:** Submit non-sensitive sample evidence in a test project whose client account uses a test inbox; verify the email and authenticated milestone link.

### 2. Assessment completed → notify the client

- **Filter:** `event` exactly equals `assessment.completed`. Optionally branch on `data.stale` so stale results are clearly labeled or suppressed.
- **Map:** `data.recipient_email`, `data.overall_result`, `data.criterion_summary`, `data.blocker_count`, `data.stale`, `data.advisory`, `data.client_approval_required`, and `data.review_url`.
- **Action:** Send the summary and link. State that the report is advisory and the client must make the decision in TrustFlow. Do not present the result as an approval.
- **Safe test:** Submit test evidence, run an assessment, and verify the test inbox receives an advisory message. No evidence text or model prompt is sent to Zapier.

### 3. Revision requested → notify the freelancer

- **Filter:** `event` exactly equals `revision.requested`.
- **Map:** `data.recipient_email`, `data.project_id`, `data.milestone_id`, `data.evidence_revision`, and `data.review_url`.
- **Action:** Email the freelancer that a revision was requested and link to TrustFlow to read the feedback. The feedback note itself is intentionally not sent to Zapier.
- **Safe test:** Request a revision on a test project whose freelancer account uses a test inbox; confirm the email link opens for that freelancer and not an unrelated account.

### 4. Milestone approved → notify the freelancer

- **Filter:** `event` exactly equals `milestone.approved`.
- **Map:** `data.recipient_email`, `data.project_id`, `data.milestone_id`, `data.evidence_revision`, and `data.review_url`.
- **Action:** Email the freelancer that the client approved this revision. Do not use the Zap to initiate capture or change TrustFlow approval/payment state.
- **Safe test:** Approve a passing test milestone as its client and confirm the test inbox receives the email only after approval is persisted.

### 5. Payment captured → notify parties or update a tracker

- **Filter:** `event` exactly equals `payment.captured` and `data.status` equals `captured`.
- **Map:** `data.client_email`, `data.freelancer_email`, `data.payment_id`, `data.project_id`, `data.milestone_id`, `data.amount`, `data.currency`, `data.capture_id`, and `data.review_url`.
- **Action:** Add two email actions: one to `client_email`, one to `freelancer_email`. Treat this as a confirmed capture notice, not a payout confirmation; TrustFlow does not split or pay funds out to freelancers.
- **Safe test:** Use a PayPal Sandbox buyer account and test project with controlled test inboxes. Confirm no email arrives while capture is uncertain and both inboxes receive one only after PayPal confirms capture.

### 6. Refund completed → retain the current support workflow

- **Filter:** `event` exactly equals `PAYMENT.CAPTURE.REFUNDED`.
- **Optional email action:** Map `data.recipient_email` to an Email by Zapier, Gmail, Outlook, or SMTP action to notify the client that the refund was confirmed.
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
2. In Zapier, turn on one Zap at a time. Use **Catch Hook → Filter by exact `event` → Email action**. For evidence, assessment, revision, approval, and refund events, map `data.recipient_email` to **To**. For captured payments, use two email actions mapped to `data.client_email` and `data.freelancer_email`.
3. Use the TrustFlow frontend to trigger that event: submit evidence, run assessment, request revision, approve an eligible assessment, or complete a PayPal Sandbox capture. Refund testing requires a Sandbox refund and the verified PayPal webhook. Do not send forged webhook requests.
4. If delivery is queued, run `../venv/bin/python scripts/deliver_events.py` from `backend/` to drain due events. Check the Zap's run history and the controlled inboxes.
5. Verify each email has the expected recipient and event, uses the authenticated `review_url`, and contains no evidence text or private feedback. Test pending/uncertain capture and confirm it sends no payment-captured email.

Zapier's action test can send a real email. During early setup, map **To** to your own test inbox; only switch to the dynamic recipient field after confirming the event data and test accounts are correct.
