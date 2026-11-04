# TrustFlow

TrustFlow helps clients and freelancers coordinate milestone terms, evidence, AI assisted review, human approval, and PayPal payments. It is a prototype: AI reports findings, while only the authenticated project client can approve a milestone. TrustFlow does not provide legal escrow.

## How the workflow works

1. A client creates a project and invites a freelancer who already has a TrustFlow account.
2. The freelancer accepts the invitation. The client defines milestone criteria, amount, currency, and deadline.
3. The freelancer submits a revision with text, HTTP(S) reference links, and optionally a private file (up to 3 MB).
4. The client asks Gemini to assess the current revision against the saved criteria. The report is stored with criterion-level findings and an audit record.
5. The client requests changes or explicitly approves the current revision.
6. PayPal Sandbox order, buyer approval, authorization, capture, and reconciliation are handled separately from the AI report.

Assessment considers only the submitted text. Reference links are not opened. PDF, image, and text attachments are stored as private PostgreSQL binary data and can be downloaded by project members, but file contents are not extracted or assessed. Reports disclose this limitation.

## Repository map

- `backend/app/main.py` — FastAPI app, CORS, request tracing, health checks, and router registration.
- `backend/app/routers/` — authenticated HTTP endpoints for accounts, projects, evidence, reviews, decisions, payments, and PayPal webhooks.
- `backend/app/services/` — account, workflow, payment, evidence validation, and integration-outbox logic.
- `backend/app/agent/` — Gemini prompt, provider, orchestration, output checks, and offline evaluation cases.
- `backend/app/db/` — shared PostgreSQL connection boundary, base schema, and additive migrations.
- `backend/app/payments/paypal.py` — PayPal Sandbox HTTP client.
- `backend/tests/` — unit and mocked API/provider tests.
- `e2e/tests/` — Playwright browser tests for authentication, workspace navigation, collaboration, and payments.
- `frontend/` — responsive React/TypeScript workspace.
- `postman/TrustFlow.postman_collection.json` — API requests and starter assertions.
- `render.yaml` — Render service blueprint; it describes deployment and does not deploy anything by itself.
- `docs/` — current architecture, safety limits, and demo steps.

## Local setup

Use Python 3.10 or newer and Node.js 20.19+ or 22.12+.

Create the root virtual environment and install backend dependencies:

```bash
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
python -m pip install -r backend/requirements.txt
```

Create `backend/.env` from `backend/.env.example` only if it does not already exist. Add your PostgreSQL URL. To use assessments, set `GEMINI_API_KEY` and `TRUSTFLOW_MODEL`. For PayPal, set Sandbox `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET`. Never commit `.env` or copy its values into the example file.

Apply the base schema and all additive migrations explicitly:

```bash
cd backend
../venv/bin/python scripts/setup_db.py
```

Start the API from `backend/`:

```bash
../venv/bin/python -m app.main
```

It listens on port 3000 by default. `GET http://localhost:3000/health` is public; readiness and product data require a session. The database schema and migrations are not applied automatically at app startup.

In a second terminal, start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

Vite serves the app at `http://localhost:5173` and proxies `/api` to the local backend. Create one client account and one freelancer account. The client enters the freelancer’s registered email to create the invitation; the freelancer signs in separately and accepts it.

## Environment variables

`backend/.env.example` lists every setting. Main settings:

- `DATABASE_URL` — PostgreSQL connection string.
- `GEMINI_API_KEY`, `TRUSTFLOW_MODEL`, optional `TRUSTFLOW_FALLBACK_MODEL` — AI assessment provider.
- `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, optional `PAYPAL_BASE_URL` — PayPal; Sandbox is the default.
- `PAYPAL_WEBHOOK_ID` — registered webhook ID required for signature verification.
- `PAYPAL_RETURN_URL`, `PAYPAL_CANCEL_URL` — frontend callback pages.
- `CORS_ORIGINS` — exact frontend origins, comma separated.
- `TRUSTFLOW_ENV` — set to `production` when deployed; this enables Secure session cookies.
- `SESSION_HASH_SALT` — generate a unique random value for production.
- `TRUSTFLOW_FRONTEND_URL` — public frontend origin used for verification, invitation emails, and authenticated milestone links in Zapier events. Set this in deployed environments.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`, `SMTP_USE_SSL`, `SMTP_USE_STARTTLS` — SMTP delivery for verification, password reset, and project invitations when Zapier is not configured. `ZAPIER_AUTH_WEBHOOK_URL` can handle verification and reset instead. Signup requires email confirmation when either auth email channel is configured. Set provider credentials on the backend only; never commit them.
- `ZAPIER_WEBHOOK_URL` — server-only Zapier Catch Hook URL (or same-owner combined Catch Hook URL). Workflow and verified refund events are transactionally placed in the PostgreSQL outbox and retried; events remain queued if this setting is absent. Notification events include only their target email address so Zapier can send email actions; see [the Zapier guide](docs/REFUNDS_AND_ZAPIER.md) for setup and manual testing.
- `ZAPIER_AUTH_WEBHOOK_URL` — optional dedicated Catch Hook for email verification and password reset when SMTP is unavailable. Keep it separate from workflow hooks because it carries short-lived account links.
- `TRUSTFLOW_AGENT_TOKEN` — bearer token required for the agent refund-proposal intake endpoint.
- `ELASTIC_APM_SERVER_URL`, optional `ELASTIC_APM_SECRET_TOKEN` — optional monitoring.

## Vercel services deployment

The root `vercel.json` defines a FastAPI backend service and a Vite frontend service. In Vercel, set the project framework to **Services** and configure the backend environment variables in Project Settings. At minimum, set `DATABASE_URL`, `TRUSTFLOW_ENV=production`, a unique `SESSION_HASH_SALT`, and `TRUSTFLOW_FRONTEND_URL` to the public frontend origin; add Gemini, PayPal, SMTP, `ZAPIER_WEBHOOK_URL`, optional `ZAPIER_AUTH_WEBHOOK_URL`, and `TRUSTFLOW_AGENT_TOKEN` values as needed. Set `PAYPAL_RETURN_URL` and `PAYPAL_CANCEL_URL` to the Vercel production domain. Vercel deployment hostnames are included in backend origin checks automatically.

Apply the database schema and migrations to the Vercel database before using the app. Evidence files up to 3 MB are stored in PostgreSQL so they remain available across serverless function instances. This increases database storage use; larger files should use an external object store.

The app prefers Argon2id through `argon2-cffi`. The existing offline development environment can fall back to Python’s scrypt implementation if that package cannot be installed. Deployed installs should install `backend/requirements.txt` so account passwords use Argon2id.

## API overview

- `POST /auth/signup`, `POST /auth/login`, `GET /auth/me`, `PATCH /auth/me`, `POST /auth/logout`
- `POST /auth/verify-email`, `POST /auth/resend-verification`, `POST /auth/password-reset/request`, `POST /auth/password-reset/confirm`
- `GET /projects`, `POST /projects`, `GET /projects/{id}`, `POST /projects/{id}/accept`, `GET /projects/{id}/audit`
- `POST /projects/{id}/milestones`, `PUT /projects/{id}/milestones/{milestone_id}`
- `GET /milestones/{id}`, `POST /milestones/{id}/evidence`, `GET /milestones/{id}/evidence/{evidence_id}/file`
- `POST /milestones/{id}/assessments`, `POST /milestones/{id}/decision`
- `POST /milestones/{id}/payment/order`, `POST /milestones/{id}/payment/authorize`, `POST /milestones/{id}/payment/capture`, `POST /milestones/{id}/payment/reconcile`
- `GET /refund-proposals`, `POST /refund-proposals/{id}/decision`, trusted-agent `POST /agent/refund-proposals`
- `POST /webhooks/paypal`
- `GET /health`, `GET /agent/health`, authenticated `GET /ready`

The same backend routes are also mounted under `/api` for the Vercel public API rewrite. Unprefixed paths remain available for local development and the existing Render deployment.

Cookie-authenticated mutations require the `X-CSRF-Token` returned by login or `/auth/me`. The browser stores the session in an HttpOnly cookie. A client can request approval only with a current successful assessment where every criterion is met. Capture verifies the persisted client decision, evidence revision, assessment report, payment state, and PayPal authorization. A caller-supplied approval flag is not used.

Agent refund proposals appear in the client payment dashboard and require an explicit client decision before PayPal receives a refund request. Configure PayPal's `PAYMENT.CAPTURE.REFUNDED` event and a Zapier Catch Hook to automate ticket resolution. Setup steps and the agent proposal payload are in [the refund and Zapier guide](docs/REFUNDS_AND_ZAPIER.md).

Zapier also receives evidence-submitted, assessment-completed, revision-requested, milestone-approved, and confirmed-payment-captured notifications. Event creation is server-side and transactional; delivery uses the existing retryable outbox. Configure a scheduled outbox worker in deployments without the Render cron service.

The old unscoped `/assessments`, `/agent/assess`, and `/paypal/*` payment routes are not registered by the application. Use the milestone-scoped authenticated endpoints above.

## Tests and checks

Run backend tests from `backend/`:

```bash
../venv/bin/python -m unittest discover -s tests -v
```

Run frontend checks from `frontend/`:

```bash
npm run lint
npm run build
```

Backend tests mock Gemini and PayPal calls. They do not apply database migrations or contact PostgreSQL, Gemini, PayPal, or Zapier. Browser automation lives in `e2e/`; follow its README to configure dedicated test accounts and run the suite against a local or approved non-production environment. Browser workflows create application data, and optional tests contact Gemini and PayPal Sandbox.

## Known MVP limits

- Email verification and password recovery use one-time links sent through backend SMTP. Local development signup remains immediate when SMTP is not configured; production signup is blocked until email delivery is configured. Zapier can send project and milestone workflow notifications; project invitations use Zapier when its Catch Hook is configured and SMTP otherwise.
- Rows already present in the legacy `users` table have no password hashes. They cannot sign in through the new auth flow until a secure account-claim process is added.
- Uploaded files (up to 3 MB) are stored privately in PostgreSQL and downloadable by project members, but are not extracted, scanned for malware, OCRed, or included in the Gemini prompt. Do not treat file-only evidence as verified.
- Evidence links are recorded and checked for valid HTTP(S) shape, but never fetched.
- An uncertain capture remains `capture_pending`; the backend will not issue another capture. Reconcile through the verified webhook or the authenticated PayPal order check. A mismatch requires operator review.
- An expired PayPal authorization is blocked from capture. Replacing an expired authorization currently requires operator intervention.
- Webhook verification needs a registered PayPal webhook and `PAYPAL_WEBHOOK_ID`. No live PayPal request has been made by the automated suite.
- The Render blueprint uses a persistent disk for evidence and describes Sandbox settings. Configure environment secrets, run the schema script, and review costs before creating services. No deployment is performed automatically.
- User and payment operations require a reachable PostgreSQL database. This workspace’s configured Neon host could not be resolved during the earlier migration audit, so live database behavior remains unverified.

See [the current architecture](docs/ARCHITECTURE.md), [the safety model](docs/AGENT_SAFETY.md), [the demo script](docs/DEMO_SCRIPT.md), and [the Postman collection](postman/TrustFlow.postman_collection.json).
