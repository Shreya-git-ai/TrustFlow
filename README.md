# TrustFlow

**AI-assisted milestone payment coordination**

TrustFlow is an early-stage project exploring how agents can help clients and freelancers coordinate milestone progress, evidence review, approval, and payments. PayPal is the payment provider for the current backend prototype.

## Project structure

- `backend/` — FastAPI application and PostgreSQL schema.
- `frontend/` — React and TypeScript app scaffold.
- `docs/` — architecture and demo notes.

The current frontend is still the Vite starter. It does not call the backend yet.

## Run the backend

Use Python 3.10 or newer. From the repository root, create the root-level `venv` once (skip the first command if it already exists), activate it, and install backend requirements:

```bash
python3 -m venv venv       # skip if the root venv already exists
source venv/bin/activate        # Windows: venv\Scripts\activate
python -m pip install -r backend/requirements.txt
cd backend
```

Create `backend/.env` from `.env.example` only if it does not already exist. Otherwise, edit the existing file so you do not overwrite your local settings. For Gemini assessment, set:

```dotenv
GEMINI_API_KEY=your-Google-AI-Studio-key
TRUSTFLOW_MODEL=gemini-3.8-flash
TRUSTFLOW_FALLBACK_MODEL=gemini-3.6-flash
```

`gemini-3.8-flash` is the recommended primary model for this assessment agent. The fallback is optional; it is tried only after transient provider errors. You can leave `TRUSTFLOW_FALLBACK_MODEL` empty to start. Use model IDs available to your Gemini API key; see Google's [Gemini API model list](https://ai.google.dev/gemini-api/docs/models). Keep the API key in `backend/.env` and do not commit it.

Start the API from `backend/`:

```bash
python -m app.main
```

It listens on port 3000 by default, or the value of `PORT` in `.env`. Check it at `http://localhost:3000/health`. The assessment endpoint is `POST http://localhost:3000/assessments`; it needs the Gemini settings above, but does not require the database or PayPal credentials. `PAYPAL_BASE_URL` defaults to PayPal sandbox; use live credentials and PayPal's live API URL only when deliberately configuring a production deployment.

## Run the frontend

Use Node.js 20.19+ or 22.12+. In a separate terminal from the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (usually `http://localhost:5173`). The frontend is currently the Vite starter and does not call the backend yet; run the API separately when working on backend endpoints.

Run the backend tests from `backend/` with `python -m unittest discover -s tests -v`. Route tests use a stub PayPal client and do not contact PayPal.

The database schema is in `backend/app/db/schema.sql`. After reviewing the target database and setting `DATABASE_URL`, the compatibility endpoint `POST /db/setup-schema` applies its idempotent `CREATE TABLE/INDEX IF NOT EXISTS` statements. This integration does not run it automatically. `GET /db/test` checks connectivity.

## Current API

- `GET /health`
- `GET /paypal/test-auth`
- `POST /paypal/create-order` — body: `{"amount": 10, "currency": "USD"}`; both fields are optional and default to 10 USD.
- `POST /paypal/authorize-order` — body: `{"orderId": "..."}`.
- `POST /paypal/capture-authorization` — body: `{"authorizationId": "...", "milestoneApproved": true}`. `amount` and `currency` may also be supplied for a final capture amount.
- `POST /assessments` — assesses evidence against milestone criteria with Gemini. Configure `GEMINI_API_KEY` and `TRUSTFLOW_MODEL`; body includes `milestone_id`, `evidence_revision`, `criteria` (`id` and `text`), and `evidence_text`, with optional `evidence_links`.
- `GET /db/test`
- `POST /db/setup-schema`

The assessment endpoint returns per-criterion verdicts, quoted evidence, blockers, and a run trace. It does not approve milestones or trigger payments; the current PayPal capture route remains a separate flow.

## Optional integrations

- **Elastic APM:** Set `ELASTIC_APM_SERVER_URL` and, when required by the APM Server, `ELASTIC_APM_SECRET_TOKEN`. The backend reports request performance and captured errors. Request bodies are not captured. Existing structured logs continue to go to standard output.
- **Zapier:** Set `ZAPIER_WEBHOOK_URL` to a Zapier Catch Hook URL to receive `assessment.completed`, `payment.order_created`, `payment.authorized`, and `payment.captured` events. Delivery is best-effort and happens after the API response. Event payloads omit submitted evidence and credentials.

Leave these settings empty to disable the corresponding integration. Zapier events are not yet persisted for retry after a process restart.

The PayPal flow creates an AUTHORIZE order, then the caller submits the order ID for authorization after buyer approval, and later captures the authorization. The capture route currently trusts the caller-provided `milestoneApproved: true` flag. These endpoints do not authenticate application users or persist the PayPal order, authorization, or capture to the database. No PayPal webhook receiver, webhook signature verification, or separate payment verification endpoint exists in the imported implementation.

See [the architecture notes](docs/ARCHITECTURE.md) for endpoint behavior, configuration, schema contents, and known integration boundaries.

## Project goals

Use Python 3.10 or newer.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Add sandbox credentials and a PostgreSQL URL to backend/.env.
python -m app.main
```

The API listens on port 3000 by default, or the value of `PORT` in `.env`. `PAYPAL_BASE_URL` defaults to PayPal sandbox; the checked-in example also sets the sandbox URL explicitly. Use live credentials and PayPal's live API URL only when deliberately configuring a production deployment.

Run the backend tests from `backend/` with `python -m unittest discover -s tests -v`. Route tests use a stub PayPal client and do not contact PayPal.

The database schema is in `backend/app/db/schema.sql`. After reviewing the target database and setting `DATABASE_URL`, the compatibility endpoint `POST /db/setup-schema` applies its idempotent `CREATE TABLE/INDEX IF NOT EXISTS` statements. This integration does not run it automatically. `GET /db/test` checks connectivity.

## Current API

- `GET /health`
- `GET /paypal/test-auth`
- `POST /paypal/create-order` — body: `{"amount": 10, "currency": "USD"}`; both fields are optional and default to 10 USD.
- `POST /paypal/authorize-order` — body: `{"orderId": "..."}`.
- `POST /paypal/capture-authorization` — body: `{"authorizationId": "...", "milestoneApproved": true}`. `amount` and `currency` may also be supplied for a final capture amount.
- `GET /db/test`
- `POST /db/setup-schema`

The PayPal flow creates an AUTHORIZE order, then the caller submits the order ID for authorization after buyer approval, and later captures the authorization. The capture route currently trusts the caller-provided `milestoneApproved: true` flag. These endpoints do not authenticate application users or persist the PayPal order, authorization, or capture to the database. No PayPal webhook receiver, webhook signature verification, or separate payment verification endpoint exists in the imported implementation.

See [the architecture notes](docs/ARCHITECTURE.md) for endpoint behavior, configuration, schema contents, and known integration boundaries.

## Project goals

- Explore practical uses of agents in milestone workflows.
- Improve visibility into milestone progress and payment status.
- Build a focused prototype for coordinating approvals and PayPal payments.

## Contributing

The project is an early prototype. Contributions should preserve the existing Python backend and React frontend structure.

## License

To be decided.
