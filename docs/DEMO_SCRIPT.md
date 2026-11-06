# TrustFlow MVP demo

## Before the demo

1. Configure PostgreSQL, run `python scripts/setup_db.py` from `backend/`, and start the API. Follow the root README for exact commands.
2. Set the Gemini environment variables if you will show assessment. PayPal direct settlement additionally needs an approved marketplace partner account, seller onboarding credentials, webhook ID, and frontend return/cancel URLs.
3. Open the frontend and create a client account. Invite a freelancer email; use its invitation link to create and verify a freelancer account if needed. No demo accounts are built in.

## Product walkthrough

1. Sign in as the client, create a project using the freelancer's email, and propose a milestone with explicit criteria, amount, currency, and deadline.
2. Sign in as the freelancer, accept the invitation, connect an eligible PayPal receiving account, review the milestone terms, and accept them. Submit evidence text; add a reference link or supported attachment to show how those limitations are disclosed.
3. Return as the client and request an assessment. Review each agreed criterion, quote, missing proof, inference, report version, and evidence revision.
4. If proof is incomplete, request a revision. Sign in as the freelancer and submit a new evidence revision, then rerun the assessment.
5. When all current criteria are marked met, explicitly approve as the client. The assessment itself does not approve anything.
6. Create a PayPal Sandbox order routed to the freelancer, complete the buyer approval page, confirm authorization, and capture. Show the persisted payment state and audit timeline.
7. If PayPal's capture result is uncertain, show `capture_pending` and use the reconcile action. Do not claim a successful capture until TrustFlow confirms the provider result.

The suite does not use fake payment success or a payout stub. PayPal partner approval is required for seller onboarding and direct settlement. If partner credentials or an approved buyer account are unavailable, demonstrate the persisted state up to the point available and describe the rest as untested.

## Optional Zapier event demo

Configure the Catch Hook URL in the backend and turn on event-filtered Zaps before the walkthrough. Use a dedicated test project and non-sensitive evidence. Submit evidence, assess it, request a revision, approve the new passing revision, and confirm payment capture; each successful operation should produce its matching event. Confirm that the payload includes a stable `event_id`, UTC `occurred_at`, IDs, and an authenticated `review_url`, and contains no evidence text or credentials.

For refund automation, follow [the refund and Zapier guide](REFUNDS_AND_ZAPIER.md): use a captured PayPal Sandbox payment, submit a refund proposal with the agent token, approve it as the client, and wait for PayPal's real signed refund-completion webhook. Do not send a fabricated webhook to simulate a completed capture or refund.
