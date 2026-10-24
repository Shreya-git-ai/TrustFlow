# TrustFlow architecture

TrustFlow is a React/Vite frontend backed by one FastAPI application and PostgreSQL. The frontend sends cookie-authenticated requests to the API. The API is the source of truth for membership, milestone revisions, assessments, client decisions, PayPal state, and the audit timeline.

## Request and data flow

1. `frontend/src/App.tsx` renders the role-specific workspace and calls `frontend/src/api/assessment.ts`. In development Vite proxies `/api` to port 3000; `VITE_API_BASE_URL` configures a deployed API origin.
2. `backend/app/main.py` loads environment settings, configures exact-origin credentialed CORS, tracing, error handling, health routes, and registers the auth, workflow, and payment routers.
3. `backend/app/routers/auth.py` and `backend/app/security.py` establish cookie sessions. `backend/app/services/auth.py` hashes passwords and session tokens, enforces the login-attempt window, and rotates sessions when account credentials change. Mutations use the CSRF token returned by `/auth/me`, login, or signup.
4. `backend/app/routers/workflow.py` validates HTTP inputs and delegates business logic to `backend/app/services/workflow.py`. Services query PostgreSQL through the shared connection contexts in `backend/app/db/repository.py`.
5. The freelancer's evidence submission creates a numbered revision. File bytes are validated and stored privately by `backend/app/services/storage.py`; only text is sent to the assessor. The assessment route snapshots current criteria and text, invokes the Gemini provider through `backend/app/agent/orchestrator.py`, validates exact quotes and criterion coverage, then persists the report, findings, and audit event.
6. The client decision route checks the latest successful report and current evidence revision before recording approval or a revision request. The assessment route itself never changes approval or payment state.
7. `backend/app/routers/payments.py` calls the PayPal client in `backend/app/payments/paypal.py`; `backend/app/services/payments.py` persists each state transition and checks the current client decision, assessment, and evidence before capture. Verified webhook events and reconciliation resolve uncertain capture outcomes without blindly repeating capture.
8. Workflow and payment services enqueue optional Zapier notifications in `integration_outbox`. `backend/app/services/events.py` leases and retries delivery; `backend/scripts/deliver_events.py` is also run by the optional Render cron service.

## Backend file map

| Area | Main files | Responsibility |
| --- | --- | --- |
| App composition | `backend/app/main.py`, `backend/app/observability.py` | FastAPI setup, CORS, traces, health, sanitized errors, optional APM. |
| Authentication | `backend/app/routers/auth.py`, `backend/app/security.py`, `backend/app/services/auth.py` | Signup, login, session lookup and revocation, CSRF, role and session security. |
| Product API | `backend/app/routers/workflow.py`, `backend/app/services/workflow.py` | Projects, invitations, milestones, evidence, assessment persistence, decisions, audit. |
| Assessment | `backend/app/agent/`, `backend/app/schemas/assessment.py` | Gemini provider, guarded prompt/output, validation, report data model. |
| Payments | `backend/app/routers/payments.py`, `backend/app/services/payments.py`, `backend/app/payments/paypal.py` | Durable payment state, PayPal order/authorization/capture, webhook verification and reconciliation. |
| Persistence | `backend/app/db/connection.py`, `backend/app/db/repository.py`, `backend/app/db/schema.sql`, `backend/app/db/migrations/` | PostgreSQL connections, shared transaction boundary, base schema and additive migration. |
| Uploads and integrations | `backend/app/services/storage.py`, `backend/app/services/events.py`, `backend/app/integrations/zapier.py` | Private upload handling and retryable optional event delivery. |
| Scripts and checks | `backend/scripts/`, `backend/tests/`, `postman/` | Explicit database setup, outbox delivery, offline/mocked tests, API collection. |

## State and safety boundaries

- User roles are `client` and `freelancer`; project membership starts `invited` and must be accepted by the assigned freelancer.
- Evidence revisions are numbered per milestone. New evidence clears any earlier approval reference. Assessments record the revision and are marked stale if evidence changed during model execution.
- The assessor sees the text supplied by the freelancer. Reference URLs are stored but not fetched. Attachments are private and downloadable by project members, but their contents are not extracted, OCRed, or inspected. A report discloses these limitations.
- Only the authenticated project client can decide. Approval requires a current successful report with every criterion marked met. Capture independently checks the persisted approval, latest decision, evidence revision, report and PayPal authorization.
- The client creates a PayPal order and authorizes it after the buyer approves it. An uncertain capture is kept `capture_pending`; the same operation is not sent again. A verified webhook or authenticated order reconciliation confirms the result.
- TrustFlow coordinates PayPal payments; it is not a legal escrow provider.

## Database setup

`backend/app/db/schema.sql` creates or preserves the original core tables. `backend/app/db/migrations/001_mvp.sql` adds authentication/session, membership, revision, assessment, decision, payment, webhook, and outbox state. Run `python scripts/setup_db.py` from `backend/` after configuring `DATABASE_URL`. App startup does not apply schema changes. The setup command is idempotent for the checked-in schema and migration.

The automated suite uses mocks and does not connect to PostgreSQL, Gemini, PayPal, or Zapier. A database URL and provider credentials are required to exercise those integrations locally. The prior migration audit's live Neon probe was blocked by DNS, so live database application remains unverified.
