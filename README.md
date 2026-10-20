# TrustFlow

**AI-assisted milestone payment coordination**

TrustFlow is an early-stage project exploring how agents can help clients and freelancers coordinate milestone progress, evidence review, approval, and payments. PayPal is the payment provider for the current backend prototype.

## Project structure

- `backend/` — FastAPI application and PostgreSQL schema.
- `frontend/` — React and TypeScript app scaffold.
- `docs/` — architecture and demo notes.

The current frontend is still the Vite starter. It does not call the backend yet.

## Run the backend

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
