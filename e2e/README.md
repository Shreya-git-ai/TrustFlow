# TrustFlow E2E

This folder contains the reusable Playwright browser suite and guarded PostgreSQL seed, verification, and cleanup scripts. The suite uses the existing TrustFlow UI and API; it does not change backend or frontend business logic.

## Prerequisites

- Node.js 22.6 or newer (Node 24 is recommended; the database scripts use Node's TypeScript stripping).
- `npm ci` from this folder and Chromium installed with `npx playwright install chromium`.
- A running TrustFlow frontend and API, or an approved non-production E2E deployment.
- Dedicated, pre-created, verified client and freelancer accounts. Normal tests do not sign up accounts or test SMTP/email verification.
- Gemini configured on the backend for assessment workflow tests.
- A separate approved E2E database for seed and cleanup operations. The schema and migrations must already be applied.
- PayPal Sandbox credentials and buyer only for the optional payment test.

Do not point browser workflows at production: they create projects, milestones, evidence, decisions, and audit events. Use dedicated test accounts and a test deployment/database.

## Install and configure

```powershell
cd e2e
npm ci
npx playwright install chromium
Copy-Item .env.example .env
```

Edit `e2e/.env` locally. Never commit it. The root ignore rules already exclude it, and this folder also ignores it.

| Variable | Purpose |
| --- | --- |
| `BASE_URL` | TrustFlow frontend origin, e.g. `http://localhost:5173`. |
| `CLIENT_EMAIL`, `CLIENT_PASSWORD` | Existing dedicated client account for UI tests. |
| `FREELANCER_EMAIL`, `FREELANCER_PASSWORD` | Existing dedicated freelancer account for UI tests. |
| `OTHER_CLIENT_EMAIL`, `OTHER_CLIENT_PASSWORD` | Optional second client used to verify cross-client project privacy. That test is explicitly skipped when unset. |
| `DATABASE_URL` | PostgreSQL URL used only by E2E database scripts. Never printed. |
| `E2E_DATABASE_HOST_ALLOWLIST` | Comma-separated exact hostnames permitted for database operations. No wildcard matching. |
| `E2E_DATABASE_NAME_ALLOWLIST` | Comma-separated exact `current_database()` names permitted for database operations. |
| `E2E_DATABASE_USER_ALLOWLIST` | Comma-separated exact `current_user` names permitted for database operations. |
| `E2E_ALLOW_SEED` | Must equal `true` for seed and cleanup writes. Defaults to disabled. |
| `E2E_ALLOW_PRODUCTION_DATABASE` | Additional explicit override required if host/database names look production-related. Avoid setting it. |
| `PAYPAL_SANDBOX_BUYER_EMAIL`, `PAYPAL_SANDBOX_BUYER_PASSWORD` | Optional Sandbox buyer used by the PayPal test. The test is marked fixme if either is absent. |

For local testing, set all three database allowlists to the exact hostname, database name, and database user of a disposable E2E database. The scripts compare the parsed `DATABASE_URL` host and server-reported database/user identity; they refuse an empty or mismatched allowlist. A URL containing a production-looking host or database name is rejected unless the explicit override is set. The override does not replace any allowlist.

## Run Playwright

Start the API and frontend according to the repository README, then run from `e2e/`:

```powershell
npm run test:e2e
npm run test:e2e:headed
npm run test:e2e:report
```

The suite uses one worker because tests share dedicated accounts and create related records. CI retries twice; traces are saved on the first retry, screenshots on failure, and the HTML report is written to `e2e/playwright-report/`. Test outputs and reports are ignored by Git. Tests use the UI for primary workflows; API helper calls share the browser context cookies and fetch a fresh CSRF token from `GET /api/auth/me` before each mutation.

Assessment tests make real requests to the configured backend Gemini provider. A missing Gemini key/model causes the assessment workflow test to fail at the observed API response; this is reported as a blocker and is not treated as a pass. Assessment model verdicts can also vary, so use short, clear synthetic evidence.

The cross-client isolation test is skipped unless the optional second client account is configured. Signup, email verification, SMTP, and password recovery are outside this suite.

## Database connection, seed, verify, and cleanup

Run the read-only connectivity and identity check first. It reports only sanitized host and database identity, never credentials or the URL.

```powershell
npm run db:check
```

After confirming this is the approved disposable E2E database, enable the write gate and seed:

```powershell
$env:E2E_ALLOW_SEED = 'true'
npm run db:seed
npm run db:verify
```

Seed reuses the configured client and freelancer accounts and creates 30 projects, 120 milestones, evidence revisions, reports spanning all existing report outcomes, eligible approval decisions, several payment states, and audit rows. It is idempotent. IDs are kept in the ignored `e2e/.e2e-seed-manifest.json` file. E2E browser tests record newly created project IDs and the seeded milestone used for a Sandbox order in the ignored `e2e/.e2e-ui-manifest.json` file for cleanup.

Verification checks seed counts, evidence/report revision links, valid approved-assessment references, decisions, payment states, audit/project relationships, and checks recorded UI project IDs against the database. It is read-only but still requires the exact target allowlists.

Cleanup requires the write gate, allowlists, and the local manifests created by the seed and/or UI tests:

```powershell
npm run db:cleanup
```

Cleanup removes manifest-listed seed IDs and descendants of explicitly recorded UI-created projects whose `E2E_` title marker still exists. It preserves the client and freelancer accounts. Do not delete either manifest manually before cleanup; without it, the script refuses to guess what it may remove.

The scripts do not apply schema migrations. Apply them separately to the approved test database using the repository's documented setup procedure before seeding.

## PayPal Sandbox

The Sandbox test uses the seeded `E2E_SEED_PROJECT_03` / `E2E_SEED_MILESTONE_009`, a synthetic approved milestone with no payment row. It creates one Sandbox order, opens PayPal's buyer approval page, authorizes, captures once, and reconciles only if the capture response is pending. It never blindly retries capture. If buyer credentials are missing the test is marked fixme; if the approval page cannot be automated, it stops at that stage and reports the observed error. Configure the backend with PayPal Sandbox credentials and callback URLs before enabling the buyer credentials here. Never provide live PayPal credentials.

## Troubleshooting

- `BASE_URL must be set`: configure the frontend origin in `e2e/.env`.
- `401` during login: confirm both accounts are verified, active, and accessible on the selected E2E backend.
- `Assessment provider is not configured`: configure Gemini on the backend or treat assessment and PayPal-dependent approval coverage as blocked.
- Database connection or name/host allowlist failure: rerun `db:check`; confirm the backend and E2E scripts target the same approved test database. The URL is intentionally never included in errors.
- Seed/cleanup refuses to run: confirm `E2E_ALLOW_SEED=true`, both exact allowlists, and the correct local manifest. Production-looking targets need a separate explicit override and should generally not be used.
- PayPal approval stops: record the PayPal stage and sanitized page behavior. Do not click capture again unless the persisted state is known; use reconciliation for `capture_pending`.
- `npm run test:e2e:report`: run after a Playwright invocation that generated a report.
