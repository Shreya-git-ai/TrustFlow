# Backend architecture

The backend runs as one FastAPI application. PayPal HTTP calls live in `backend/app/payments/paypal.py`, HTTP routes in `backend/app/routers/payments.py`, request parsing in `backend/app/schemas/payments.py`, database access in `backend/app/db/connection.py`, and the PostgreSQL schema in `backend/app/db/schema.sql`. `backend/app/main.py` registers the routes and handles request trace IDs. No Node service is required.

## Existing PayPal contract

| Route | Request | Success response | Behavior |
| --- | --- | --- | --- |
| `GET /paypal/test-auth` | — | `{"success": true, "message": "Authenticated with PayPal"}` | Requests and discards an OAuth client-credentials token. |
| `POST /paypal/create-order` | Optional `amount` and `currency` (defaults `10`, `USD`) | `201` with `message`, `orderId`, `status`, and `approvalUrl` | Creates a PayPal v2 Checkout order with `intent: AUTHORIZE`. |
| `POST /paypal/authorize-order` | `orderId` | `message`, `orderId`, `orderStatus`, `authorizationId`, `authorizationStatus`, `amount` | Calls the PayPal authorize endpoint for the supplied order. |
| `POST /paypal/capture-authorization` | `authorizationId`, `milestoneApproved: true`; optional `amount` and `currency` | `message`, `captureId`, `status`, `amount` | Calls PayPal capture. If no amount is given, PayPal captures the remaining authorized amount; with an amount, it sends `final_capture: true`. |

The implementation obtains a new OAuth token for each operation and sends a unique `PayPal-Request-Id` for order creation, authorization, and capture. PayPal requests have a 15-second timeout. It returns sanitized API errors and does not return or log access tokens. Traces accept a valid incoming W3C `traceparent`, return a new response `traceparent`, and emit JSON request and span logs.

The imported TypeScript source did not include a webhook endpoint, signature verification, order-status verification, or application-user authentication. The capture approval check is only the caller-provided boolean from the existing contract. Payment operations are not written to PostgreSQL, and audit tables are not currently populated. Those behaviors have not been implied or added in the Python port.

## Database

`backend/app/db/schema.sql` preserves the seven original tables: `users`, `projects`, `milestones`, `evidence`, `payments`, `audit_events`, and `webhook_events`, along with their constraints and indexes. The schema is applied only when `POST /db/setup-schema` is explicitly called. Its statements use `IF NOT EXISTS`; the application does not apply migrations at startup. `GET /db/test` runs a read-only connectivity query.

Configure `DATABASE_URL` with the PostgreSQL URL and SSL mode required by the database host. Connections are opened only for database routes.

## Configuration

Copy `backend/.env.example` to `backend/.env`. Set `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, and `DATABASE_URL`. The default PayPal endpoint is `https://api-m.sandbox.paypal.com`; `PAYPAL_BASE_URL` can override it. `PAYPAL_RETURN_URL` and `PAYPAL_CANCEL_URL` default to local port 3000. `PORT` defaults to 3000. Never copy local credentials into the example file or Git.

## Integration boundaries

- The React/Vite frontend remains unchanged and is not connected to these routes.
- No existing Python payment, database, or router implementation was present to merge with.
- The source Postman environment and globals contain empty `values` lists; they add no API contract or credentials.
- The Node package scripts, lockfile, and TypeScript config were specific to the Express service and are not used by the Python backend.
