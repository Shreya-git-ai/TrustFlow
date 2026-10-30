# Agent refund review and Zapier automation

## Refund review flow

The existing `client` account is the merchant/payer for this workflow. A trusted refund agent creates a proposal through `POST /agent/refund-proposals`; it cannot send a refund. The project client reviews proposals in **Payments → Agent-proposed refunds** and must approve one before TrustFlow calls PayPal.

Set a long random `TRUSTFLOW_AGENT_TOKEN` on the backend. The proposal endpoint requires it as a bearer token. The `proposal_key` is an agent-generated idempotency key and must be reused for retries of the same proposal.

Example request:

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
  "reason": "The post-delivery review found that the agreed acceptance requirement was not met.",
  "zendesk_ticket_id": 12345,
  "slack_channel_id": "C0123456789",
  "slack_thread_ts": "1729876543.123456"
}
```

Zendesk and Slack identifiers are optional. Include only the destination(s) for the support case related to this payment. The merchant review API is `GET /refund-proposals`; decisions use `POST /refund-proposals/{proposal_id}/decision` with `{"decision":"approve"}` or `{"decision":"reject"}` and the existing CSRF-protected session.

Approved refunds use [PayPal's captured-payment refund endpoint](https://developer.paypal.com/api/payments/v2/captures-refund) with a stable `PayPal-Request-Id` and the proposal UUID as `custom_id`. TrustFlow reserves pending proposals and active refunds against the payment's remaining refundable balance. A timeout is left in `processing`; retrying approval uses the same PayPal request ID. Payment totals and support automation update only after the refund is confirmed.

## Configure PayPal

In the PayPal app's webhook settings, subscribe the backend URL (`https://<your-api-host>/webhooks/paypal`) to:

- `PAYMENT.CAPTURE.COMPLETED`
- `PAYMENT.CAPTURE.REFUNDED`

Save that webhook's ID as `PAYPAL_WEBHOOK_ID` and use credentials from the same Sandbox or Live app. TrustFlow verifies PayPal's signature before processing the event. Its handler records the provider refund idempotently and places a `PAYMENT.CAPTURE.REFUNDED` message in the Zapier outbox. PayPal's [webhook guide](https://developer.paypal.com/api/rest/webhooks/) explains event subscriptions; the refund event must be subscribed for ticket automation to run.

## Configure Zapier

1. Create a **Webhooks by Zapier → Catch Hook** trigger and copy its URL into backend `ZAPIER_WEBHOOK_URL`. Zapier's [Catch Hook setup guide](https://help.zapier.com/hc/en-us/articles/8496288690317-Trigger-Zap-workflows-from-webhooks) covers the trigger setup.
2. Turn on the Zap before sending a test refund event. The hook receives the TrustFlow envelope with `event` and nested `data` fields.
3. Add a Filter step where `event` exactly matches `PAYMENT.CAPTURE.REFUNDED`.
4. Add a Path for Zendesk and another for Slack. Each path should also require its corresponding ticket fields to be present.

For the Zendesk path, use **Zendesk → Update Ticket**, set Ticket ID to `data.zendesk_ticket_id`, add an internal note with the refund id/amount, and set status to **Solved**. Zendesk supports ticket updates through its [Tickets API](https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/). Zendesk describes solved tickets as the state before its later closed state; closed tickets cannot be reopened, so Solved is the safer automated resolution state.

For the Slack path, a Slack thread has no native ticket status. Use a Slack message action to reply to `data.slack_thread_ts` in `data.slack_channel_id` with a short refund-confirmed resolution, and add the `white_check_mark` reaction to the original thread message. Slack's [`chat.postMessage`](https://api.slack.com/methods/chat.postMessage) supports `thread_ts`; [`reactions.add`](https://api.slack.com/methods/reactions.add) needs the channel and message timestamp. Use a Slack bot connection authorized for the channel and reaction scopes.

If no ticket id was attached to the proposal, use `data.ticket_lookup_key` (the PayPal capture id) to find a Zendesk ticket with a matching capture-id custom field. For Slack, store the thread metadata on the proposal so the event can target the right conversation. Do not close a ticket on a pending refund event; the outbox only emits this automation event after the verified refund event is recorded.

`ZAPIER_WEBHOOK_URL` is optional. If it is unset when a refund webhook is processed, no Zapier outbox item is created. Configure it before enabling the refund workflow.
