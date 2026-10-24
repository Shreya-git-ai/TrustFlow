# Backend architecture

The backend runs as one FastAPI application. PayPal HTTP calls live in `backend/app/payments/paypal.py`, HTTP routes in `backend/app/routers/payments.py`, assessment routes in `backend/app/routers/assessments.py`, and assessment logic in `backend/app/agent/`. Database access lives in `backend/app/db/connection.py`, with the PostgreSQL schema in `backend/app/db/schema.sql`. `backend/app/main.py` registers the routes and handles request trace IDs. No Node service is required for the API.

## Existing PayPal contract

| Route | Request | Success response | Behavior |
| --- | --- | --- | --- |
| `GET /paypal/test-auth` | — | `{"success": true, "message": "Authenticated with PayPal"}` | Requests and discards an OAuth client-credentials token. |
| `POST /paypal/create-order` | Optional `amount` and `currency` (defaults `10`, `USD`) | `201` with `message`, `orderId`, `status`, and `approvalUrl` | Creates a PayPal v2 Checkout order with `intent: AUTHORIZE`. |
| `POST /paypal/authorize-order` | `orderId` | `message`, `orderId`, `orderStatus`, `authorizationId`, `authorizationStatus`, `amount` | Calls the PayPal authorize endpoint for the supplied order. |
| `POST /paypal/capture-authorization` | `authorizationId`, `milestoneApproved: true`; optional `amount` and `currency` | `message`, `captureId`, `status`, `amount` | Calls PayPal capture. If no amount is given, PayPal captures the remaining authorized amount; with an amount, it sends `final_capture: true`. |

The implementation obtains a new OAuth token for each operation and sends a unique `PayPal-Request-Id` for order creation, authorization, and capture. PayPal requests have a 15-second timeout. It returns sanitized API errors and does not return or log access tokens. Traces accept a valid incoming W3C `traceparent`, return a new response `traceparent`, and emit JSON request and span logs.

The imported TypeScript source did not include a webhook endpoint, signature verification, order-status verification, or application-user authentication. The capture approval check is only the caller-provided boolean from the existing contract. Payment operations are not written to PostgreSQL, and audit tables are not currently populated. Those behaviors have not been implied or added in the Python port.

## Gemini assessment

`POST /assessments` accepts `milestone_id`, `evidence_revision`, one or more criteria (`id` and `text`), `evidence_text`, and optional `evidence_links`. It returns a verdict and reasoning per criterion, exact quoted evidence for supported criteria, blockers for other verdicts, and a run trace. Verification checks criterion coverage and rejects supported verdicts whose quote is not present in the supplied evidence text. Evidence is limited to 20,000 characters by the orchestrator. Submitted links are included in the prompt but are not fetched or opened.

Assessment does not persist results, approve milestones, or trigger payments. Missing Gemini configuration returns `503`; provider errors return `502`. Empty evidence produces an `empty_evidence` trace without calling the model. Invalid model output is retried once by the orchestrator. The Gemini provider makes one call to the configured primary model and, for transient provider errors, one call to the optional fallback model. The trace reports the model that produced the response.

Set `GEMINI_API_KEY` and `TRUSTFLOW_MODEL`; `TRUSTFLOW_FALLBACK_MODEL` is optional. The README example uses `gemini-3.8-flash` with `gemini-3.6-flash` as fallback. The endpoint emits a best-effort `assessment.completed` Zapier event when a Catch Hook URL is configured; the event omits submitted evidence.

## Database

`backend/app/db/schema.sql` preserves the seven original tables: `users`, `projects`, `milestones`, `evidence`, `payments`, `audit_events`, and `webhook_events`, along with their constraints and indexes. The schema is applied only when `POST /db/setup-schema` is explicitly called. Its statements use `IF NOT EXISTS`; the application does not apply migrations at startup. `GET /db/test` runs a read-only connectivity query.

Configure `DATABASE_URL` with the PostgreSQL URL and SSL mode required by the database host. Connections are opened only for database routes.

## Configuration

Create `backend/.env` from `backend/.env.example` if it does not already exist. Set `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, and `DATABASE_URL` for those integrations. Set `GEMINI_API_KEY` and `TRUSTFLOW_MODEL` to use assessment, and optionally set `TRUSTFLOW_FALLBACK_MODEL`. `ELASTIC_APM_SERVER_URL` and `ZAPIER_WEBHOOK_URL` enable their respective optional integrations; leave them empty to disable them. The default PayPal endpoint is `https://api-m.sandbox.paypal.com`; `PAYPAL_BASE_URL` can override it. `PAYPAL_RETURN_URL` and `PAYPAL_CANCEL_URL` default to local port 3000. `PORT` defaults to 3000. Never copy local credentials into the example file or Git.

## Integration boundaries

- The React/Vite frontend remains a starter and is not connected to these routes.
- No existing Python payment, database, or router implementation was present to merge with.
- The source Postman environment and globals contain empty `values` lists; they add no API contract or credentials.
- The Node package scripts, lockfile, and TypeScript config were specific to the Express service and are not used by the Python backend.
