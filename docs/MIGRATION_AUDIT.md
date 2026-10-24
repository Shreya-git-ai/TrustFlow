# TrustFlow Node.js to Python Migration Audit

> Historical snapshot dated 2026-10-20, written before the MVP work documented in the current README and architecture. Its endpoint, frontend, auth, and payment-gap findings describe the repository at that audit date and are not the current API contract. The live PostgreSQL connection limitation recorded below remains relevant until verified in a network-enabled environment.

**Audit date:** 2026-10-20

**Scope:** original `TrustFlow/` Express/TypeScript service and migrated `TrustFlow-team/` FastAPI backend and React/Vite frontend.

## A. Executive summary

**Overall status: PARTIAL — the Python service accounts for all seven original HTTP routes and its SQL schema is structurally identical, but the end-to-end migration is not complete.** The frontend is still the Vite starter and makes no backend calls. The app has no user authentication, trusts a caller-supplied milestone approval flag before capture, and does not persist payment state. A safe read-only Neon check was blocked by DNS resolution, and the sandbox prevented binding a local Uvicorn socket. PayPal requests were verified only with mocks; no sandbox or live provider request was made.

The source and migrated services expose the same seven method/path pairs. Normal request and response contracts are close. Two concrete input-parity defects were corrected during this audit: JavaScript `Number(...).toFixed(2)` cent rounding for values such as `1.005`, and treating an explicit `currency: null` as the existing USD default. Regression tests cover both.

The repositories were inspected before changes. The original repository remained clean on `main` at `ed5df12`; the target remained on `feature/backend-integration` at `6bc3551`. No branch, remote, or commit operations were performed. The target repository had a pre-existing uncommitted `frontend/package-lock.json` change; it was preserved as found. The original Node repository was not modified.

## B. Endpoint parity matrix

Requests may include the optional W3C `traceparent` header. Payment JSON requests accept `application/json` and `+json` media types in Python; neither service requires an application-user authorization header. The frontend currently depends on none of these routes.

| Method and path | Node handler → Python handler | Request and response contract | Effects, controls, and verification |
| --- | --- | --- | --- |
| `GET /health` | `app.get("/health")` → `health()` | No body. `200` with `{"status":"ok","service":"TrustFlow API"}`. | No DB or provider call; no authentication. TestClient PASS. No frontend caller. |
| `GET /paypal/test-auth` | `app.get("/paypal/test-auth")` → `test_paypal_auth()` | No body. `200` with `success` and `message`; provider/config failure returns `502` with `success:false` and a generic `error`. | Obtains and discards an OAuth token. No DB or authentication. Route and mocked OAuth failure tests PASS. No frontend caller. |
| `POST /paypal/create-order` | `app.post("/paypal/create-order")` → `create_order()` | JSON `amount` and `currency` are optional; defaults are `10` and `USD`. Amount must be positive and currency a three-letter uppercase code. Success is `201` with `message`, `orderId`, `status`, `approvalUrl`; invalid input is `400`; provider HTTP failure is `502` with `paypalStatus`; transport/config failure is `502` with a generic error. | Calls OAuth then PayPal Checkout Orders with `intent: AUTHORIZE`. No DB or authentication. Success, validation, provider status, timeout, and output mapping are covered by mocked tests. No frontend caller. |
| `POST /paypal/authorize-order` | `app.post("/paypal/authorize-order")` → `authorize_order()` | JSON requires an ASCII alphanumeric `orderId`. Success is `200` with `message`, `orderId`, `orderStatus`, `authorizationId`, `authorizationStatus`, `amount`; invalid input is `400`; provider and transport failures are `502`. | Calls OAuth and PayPal's order authorization endpoint. No DB or authentication. Route success, validation, and provider failure tests PASS; provider HTTP lifecycle is mocked. No frontend caller. |
| `POST /paypal/capture-authorization` | `app.post("/paypal/capture-authorization")` → `capture_authorization()` | JSON requires ASCII alphanumeric `authorizationId` and literal boolean `milestoneApproved:true`; false/missing approval returns `403`. Optional positive `amount` and uppercase `currency` produce an amount-bearing final capture; without amount, the remaining authorization is captured. Success is `200` with `message`, `captureId`, `status`, `amount`; invalid input is `400`; provider/transport failure is `502`. | Calls OAuth and PayPal authorization capture. No DB, user auth, or server-side milestone check. TestClient verifies rejection before provider call; mocked HTTP test verifies capture body. No frontend caller. |
| `GET /db/test` | `app.get("/db/test")` → `database_health()` | No body. Success is `200` with `success`, `message`, `database`, `databaseTime`; connection failure is `500` with a generic error. Python formats the timestamp as UTC ISO-8601; Node JSON serialization also emits an ISO timestamp. | Runs a fixed `SELECT NOW(), current_database()` query. No auth. Success and failure tested with a patched DB function only; no live route query. No frontend caller. |
| `POST /db/setup-schema` | `app.post("/db/setup-schema")` → `setup_database_schema()` | No body. Success is `200` with `success`, `message`, and the seven table names. Failure is `500`. The Python failure message says `Check DATABASE_URL`; Node says `Check server logs`, a small response-text difference. | Runs static `CREATE TABLE/INDEX IF NOT EXISTS` DDL. No auth. The route test replaces the schema function with a mock; no live DDL was run. No frontend caller. |

The seven Python route registrations were enumerated successfully and match the seven original routes. The source's configured PayPal return and cancel URLs point at `/paypal/return` and `/paypal/cancel`, but neither implementation defines those handlers. Python TestClient confirms both paths return `404`; this is an existing workflow gap, not a route omitted from the Python port. Unsupported `POST /health` returns `405` as expected.

### Contract differences found

- The original Express handlers use JavaScript coercion (`Number` and `String`). Python now matches the common numeric/string inputs, JavaScript's tested cent rounding, null defaults, and ordinary numeric string syntax. Exotic coercions remain narrower in Python: values such as arrays/objects that JavaScript can coerce to numbers or strings are rejected by the Python request schema. Amount formatting at extreme magnitudes also has not been proven byte-for-byte equivalent to JavaScript `toFixed`.
- Invalid JSON and bodies over 32 KiB produce `400 {"error":"Invalid request"}` in Python, matching the intended Express error contract. Python additionally accepts `application/*+json` media types.
- `POST /db/setup-schema` has the failure-message text difference noted above. No route names or normal success field names were found to be missing.
- Python returns generic typed error logs for database and PayPal exceptions; it does not expose provider payloads or credentials in route responses.

## C. Database parity report

### Schema

`TrustFlow/src/schema.sql` and `backend/app/db/schema.sql` each contain 12 SQL statements. A token-level comparison that ignores formatting whitespace matched all 591 tokens. Both define the same seven tables (`users`, `projects`, `milestones`, `evidence`, `payments`, `audit_events`, `webhook_events`) and five indexes. Column types, nullability, defaults, keys, foreign keys, uniqueness, check constraints, and index definitions match. The only source difference found was whitespace in the `webhook_events.processing_status` check-list formatting.

Neither application applies schema at startup. The Python setup route reads its static schema file and executes each semicolon-separated statement inside a psycopg connection context; successful context exit commits and exceptional exit rolls back. The statements are `IF NOT EXISTS` DDL, not versioned migrations. The original uses a `pg.Pool` and submits the schema text as a query. The Python port opens and closes a direct connection per database route rather than pooling, with a 10-second connect timeout; the Node pool has no explicit connection timeout configured.

Both implementations use fixed SQL with no request-supplied SQL fragments. Database query errors are returned generically. The Python logs only the exception type for database failures; the Node source logs the error object.

### Configuration and live check

Both local `.env` files contain the expected variable names `DATABASE_URL`, `PAYPAL_BASE_URL`, `PAYPAL_CLIENT_ID`, and `PAYPAL_CLIENT_SECRET`. Their database host and database path match; they classify as Neon with `sslmode=require`, and their PayPal base URL classifies as sandbox. Values, hostnames, database name, credentials, and connection strings are intentionally omitted here. The target `.env` is ignored by Git and is not tracked; `.env.example` is the checked-in template.

The original Node pool sets `ssl: { rejectUnauthorized: false }` whenever a URL is configured. Python psycopg uses libpq settings from the URL; the configured `sslmode=require` encrypts the connection but does not verify the server certificate identity. Both settings should be reviewed before production use. Python loads `backend/.env` from a path relative to `app/main.py`, which is correct; process environment variables take precedence because `load_dotenv` uses `override=False`.

A read-only probe was attempted against the migrated configuration using an 8-second connection timeout, `default_transaction_read_only=on`, an explicit `SET TRANSACTION READ ONLY`, and only a current database/user/time metadata query. **BLOCKED:** the client could not resolve the Neon hostname (`OperationalError`, DNS resolution failure) before a query ran. No database writes or business-row reads occurred. The `GET /db/test` and `POST /db/setup-schema` route tests use patched functions; live connection and schema application remain unverified.

## D. PayPal verification report

The Python client uses `httpx.AsyncClient` with a 15-second timeout, obtains an OAuth client-credentials token for each operation, and defaults to the sandbox API base URL. It checks for configured credentials, sends Basic auth for OAuth and Bearer auth for the order operations, and does not return or log access tokens. Each create, authorize, or capture request gets a fresh UUID `PayPal-Request-Id`.

The mocked transport test exercised this exact sequence without network access:

1. OAuth token request and `201` AUTHORIZE order creation for EUR 12.35; checked the JSON, return URL, approval link, and authorization intent.
2. A second OAuth request and order authorization for the mocked order ID.
3. A third OAuth request and USD 5.25 authorization capture with `final_capture:true`.
4. Verified three unique UUID request IDs and the 15-second timeout on requests.
5. Mocked an OAuth `401` and verified it surfaces as a sanitized failure without returning a token.

The backend route tests separately cover fake PayPal client success, invalid requests, provider HTTP errors, timeouts, and the capture approval gate. These are unit and mocked HTTP integration checks. **No PayPal sandbox or live provider request was made, and no financial operation was initiated.**

The implementation does not cache OAuth tokens, retry requests, persist orders/authorizations/captures, or reuse the same idempotency key across a caller retry. The request ID is fresh for every attempt, so it does not deduplicate duplicate client submissions. It does not validate that a successful provider response contains a particular order/authorization/capture state before returning mapped data. No webhook receiver or signature verification exists; the `webhook_events` table is not used by the payment routes. The capture check only trusts `milestoneApproved:true` from the request body.

## E. Frontend compatibility

The React app is the Vite starter screen, with its counter and framework links. Search found no API client, `fetch`, Axios, backend base URL, relevant `VITE_*` variable, or Vite proxy. The checked-in README also describes the frontend as not connected to the backend. The backend defaults to port 3000 and Vite defaults to port 5173.

There is no CORS middleware. An in-process browser-style preflight (`OPTIONS /paypal/create-order`, origin `http://localhost:5173`, requested method `POST`) returned `405` with no `Access-Control-Allow-Origin` or `Access-Control-Allow-Methods` headers. A browser frontend hosted on a separate origin cannot call the API until CORS is configured. No frontend payment flow exists to test.

The production build and lint checks pass. The build was directed to a temporary directory so the existing ignored `frontend/dist/` was not overwritten. There is no frontend test script or browser end-to-end suite. A successful build verifies compilation only; it does not verify browser/API compatibility.

## F. Test results

| Check | Status | Result |
| --- | --- | --- |
| Python syntax compilation | **PASS** | `PYTHONDONTWRITEBYTECODE=1 ../../TrustFlow/venv/bin/python -m compileall -q app tests` — exit 0. |
| Backend test suite | **PASS** | `PYTHONDONTWRITEBYTECODE=1 ../../TrustFlow/venv/bin/python -m unittest discover -s tests -v` — exit 0, 25 tests passed. Includes all seven route handlers, validation/errors, database stubs, mocked PayPal HTTP lifecycle, and amount schema regressions. |
| FastAPI import and route enumeration | **PASS** | Imported `app.main` and enumerated all seven routes — exit 0. |
| Backend Uvicorn local startup / real socket smoke test | **BLOCKED** | Started with blank `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, and `DATABASE_URL`; bind to `127.0.0.1:39127` failed with `[Errno 1] ... operation not permitted` — exit 3. The sandbox denied socket binding. In-process TestClient checks passed; no real local HTTP request could be made. |
| PayPal API lifecycle via mocked `httpx.MockTransport` | **PASS** | OAuth, create, authorize, capture, timeout, request IDs, and OAuth error behavior tested; no external request. Included in 25-test suite. |
| PayPal sandbox/live verification | **NOT TESTED** | No provider requests were made. |
| Database endpoint behavior | **PASS** | Success/error paths tested through patched functions; setup-schema was mocked and did not execute DDL. |
| Neon read-only connectivity | **BLOCKED** | Safe metadata-only probe was blocked by DNS resolution before query execution. Probe wrapper exit 0 after catching the connection error; no database query completed. |
| Schema parity | **PASS** | 12 statements in each schema; token-level comparison matched all 591 tokens — exit 0. |
| CORS preflight | **FAIL** | TestClient request returned `405` and no CORS headers. Probe command itself exited 0. |
| Frontend production build | **PASS** | From `frontend/`: `npm run build -- --outDir /private/tmp/trustflow-migration-audit-build-9c67` — exit 0 (`tsc -b && vite build`). |
| Frontend lint | **PASS** | From `frontend/`: `npm run lint` — exit 0. |
| Original TypeScript typecheck | **PASS** | From `TrustFlow/`: `npm run typecheck` — exit 0. |
| Node backend automated tests | **NOT TESTED** | `TrustFlow/package.json` has no test suite; its `test` script is a placeholder that prints an error and exits 1. |
| Frontend/browser integration tests | **NOT TESTED** | No browser test setup or API integration is present. |
| Git whitespace validation | **PASS** | `git diff --check` — exit 0. A separate scan of modified/new Python files found no trailing whitespace and a final newline in each. |

The FastAPI `TestClient` emitted a Starlette deprecation warning because the installed stack uses `httpx` with `starlette.testclient`; this did not fail tests. No package installation or upgrade was performed.

## G. Remaining issues

1. **High — authorize users and verify milestone state server-side before capture.** All routes are unauthenticated. A caller can set `milestoneApproved:true`; the backend does not check a trusted project/milestone record or caller ownership. This is present in the original service and remains unsafe for production payments.
2. **High — persist and reconcile payment state.** The schema has payment and audit tables, but routes do not write to them. There is no order-status verification endpoint, webhook receiver/signature check, duplicate-capture guard, or durable workflow state.
3. **High — add request-level idempotency.** Fresh PayPal request IDs per attempt do not deduplicate retries from a client. Duplicate order/capture requests are not tracked locally.
4. **High — complete the browser integration.** The frontend has no API client or payment workflow, and CORS preflight currently fails. Build success does not establish frontend compatibility.
5. **Medium — verify the configured Neon endpoint in an environment with DNS/network access.** Current evidence establishes schema parity and mocked route behavior only; live connection and deployed schema state are unknown.
6. **Medium — review public database operations.** `/db/test` exposes current database identity/time when reachable; `/db/setup-schema` can run DDL without authentication. Restrict these operations before exposing the service.
7. **Medium — review TLS identity validation and connection scaling.** The source disables Node certificate verification; the configured `sslmode=require` does not verify certificate identity. Python opens direct connections rather than using a pool.
8. **Low — align the schema setup error message.** Node returns “Check server logs”; Python returns “Check DATABASE_URL.”
9. **Low — document narrower exotic JavaScript coercions.** Python rejects array/object coercions JavaScript accepts and has not been verified against JavaScript `toFixed` formatting for extreme magnitudes. Common scalar inputs, null defaults, and tested rounding cases now match.

The security and workflow gaps in items 1–3 and 6 existed in the Node implementation as well; migration route parity carries them forward. They remain required work before production use.

## H. Reproduction commands

Commands below use the existing sibling virtual environment available in this workspace. On another machine, replace `../../TrustFlow/venv/bin/python` with the Python executable in an environment containing `backend/requirements.txt` dependencies. They do not print `.env` values.

Backend checks, from `TrustFlow-team/backend/`:

```bash
PYTHONDONTWRITEBYTECODE=1 ../../TrustFlow/venv/bin/python -m compileall -q app tests
PYTHONDONTWRITEBYTECODE=1 ../../TrustFlow/venv/bin/python -m unittest discover -s tests -v
```

Route enumeration, from the same directory (FastAPI 0.156 stores included routes in a nested router):

```bash
PYTHONDONTWRITEBYTECODE=1 ../../TrustFlow/venv/bin/python - <<'PY'
from app.main import app
from fastapi.routing import APIRoute

def walk(router):
    for route in getattr(router, 'routes', []):
        if isinstance(route, APIRoute):
            yield route
        else:
            nested = getattr(route, 'original_router', None)
            if nested is not None:
                yield from walk(nested)
            nested = getattr(route, 'router', None)
            if nested is not None and nested is not router:
                yield from walk(nested)

for route in walk(app):
    print(','.join(sorted(route.methods - {'HEAD', 'OPTIONS'})), route.path)
PY
```

Schema token comparison, also from `TrustFlow-team/backend/`:

```bash
python3 - <<'PY'
from pathlib import Path
import re

lexer = re.compile(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|[A-Za-z_][A-Za-z0-9_$]*|\d+(?:\.\d+)?|[^\s]")
original = lexer.findall(Path('../../TrustFlow/src/schema.sql').read_text())
migrated = lexer.findall(Path('app/db/schema.sql').read_text())
print('token_match', original == migrated)
print('token_counts', len(original), len(migrated))
PY
```

The CORS preflight probe, from the backend directory, can be reproduced without a socket or network call:

```bash
PYTHONDONTWRITEBYTECODE=1 ../../TrustFlow/venv/bin/python - <<'PY'
from fastapi.testclient import TestClient
from app.main import app

response = TestClient(app).options(
    '/paypal/create-order',
    headers={
        'Origin': 'http://localhost:5173',
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'content-type',
    },
)
print(response.status_code, response.headers.get('access-control-allow-origin'))
PY
```

The following local server command was attempted with external credentials and database access explicitly blanked. In this sandbox it fails at socket bind; it can be used in a local environment that permits loopback sockets:

```bash
PAYPAL_CLIENT_ID='' PAYPAL_CLIENT_SECRET='' DATABASE_URL='' PORT=39127 \
  ../../TrustFlow/venv/bin/python -m uvicorn app.main:app \
  --host 127.0.0.1 --port 39127 --log-level warning
```

Frontend checks, from `TrustFlow-team/frontend/`:

```bash
npm run build -- --outDir /private/tmp/trustflow-migration-audit-build-9c67
npm run lint
```

Original TypeScript check, from `TrustFlow/`:

```bash
npm run typecheck
```

The read-only Neon probe, from the workspace parent directory, uses the ignored migrated `backend/.env` without printing it. It performs metadata-only SQL in a read-only transaction:

```bash
TrustFlow/venv/bin/python - <<'PY'
from dotenv import dotenv_values
import psycopg

url = dotenv_values('TrustFlow-team/backend/.env')['DATABASE_URL']
with psycopg.connect(
    url, connect_timeout=8,
    options='-c default_transaction_read_only=on',
) as connection:
    with connection.cursor() as cursor:
        cursor.execute('SET TRANSACTION READ ONLY')
        cursor.execute('SELECT current_database(), current_user, NOW()')
        cursor.fetchone()
PY
```

This probe was blocked by DNS resolution in the audit environment.

## I. Changes made

- `backend/app/schemas/payments.py` — added JavaScript-compatible numeric parsing for ordinary JSON scalar and numeric-string inputs, including binary floating-point cent rounding and underflow/overflow rejection; explicit `currency:null` now follows the original USD nullish default for create and capture requests.
- `backend/tests/test_payment_schemas.py` — added regression coverage for cent rounding, numeric syntax and boundaries, and null currency defaults.
- `backend/tests/test_payment_routes.py` — expanded route coverage for all seven handlers, validation/provider failures, mocked database behavior, callback 404s, and unsupported methods.
- `backend/tests/test_paypal_http.py` — added mocked HTTP tests for OAuth, create, authorize, capture, timeouts, idempotency header format, and provider auth failure.
- `docs/MIGRATION_AUDIT.md` — this report.
- `frontend/package-lock.json` — contained a pre-existing uncommitted user change and was not edited by this audit.

No `.env` file, original Node source, original Node branch, database schema, or live PayPal account was modified. No packages were installed, and no changes were staged, committed, or pushed.
