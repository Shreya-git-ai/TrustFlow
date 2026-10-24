# TrustFlow frontend

The React/TypeScript app serves the client and freelancer workspace. It uses the FastAPI backend for accounts, projects, evidence, assessments, decisions, payments, and audit history; it does not keep authoritative workflow state in the browser.

## Local development

```bash
npm ci
npm run dev
```

Vite serves `http://localhost:5173` and proxies `/api` to `http://127.0.0.1:3000`. The API requires PostgreSQL and its schema migration before account and workflow requests can succeed.

To build for a separate API origin, set `VITE_API_BASE_URL` before running `npm run build`, and add the frontend origin to backend `CORS_ORIGINS`. The browser sends the HttpOnly session cookie and an in-memory CSRF token for mutations.

Run `npm run lint` and `npm run build` for the available frontend checks. There is no browser automation test suite yet.
