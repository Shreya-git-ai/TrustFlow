# TrustFlow MVP demo

## Before the demo

1. Configure PostgreSQL, run `python scripts/setup_db.py` from `backend/`, and start the API. Follow the root README for exact commands.
2. Set the Gemini environment variables if you will show assessment. Set PayPal Sandbox credentials, webhook ID, and frontend return/cancel URLs if you will show payment.
3. Open the frontend and create separate client and freelancer accounts. No demo accounts are built in.

## Product walkthrough

1. Sign in as the client, create a project using the freelancer account's email, and define a milestone with explicit criteria, amount, currency, and deadline.
2. Sign in as the freelancer, accept the invitation, open the project, and submit evidence text. Add a reference link or supported attachment to show how those limitations are disclosed.
3. Return as the client and request an assessment. Review each criterion, quote, missing proof, inference, report version, and evidence revision.
4. If proof is incomplete, request a revision. Sign in as the freelancer and submit a new evidence revision, then rerun the assessment.
5. When all current criteria are marked met, explicitly approve as the client. The assessment itself does not approve anything.
6. Create a PayPal Sandbox order and complete the buyer approval page. Return to TrustFlow, confirm authorization, and capture. Show the persisted payment state and audit timeline.
7. If PayPal's capture result is uncertain, show `capture_pending` and use the reconcile action. Do not claim a successful capture until TrustFlow confirms the provider result.

The suite does not use fake payment success or a payout stub. If PayPal credentials or an approved buyer account are unavailable, demonstrate the persisted state up to the point available and describe the rest as untested.
