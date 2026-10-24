from __future__ import annotations
from app.agent.api import router as agent_router


import os
import time
from datetime import timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.db.connection import apply_schema, test_connection
from app.observability import log_event, parse_traceparent, request_trace
from app.routers.assessments import router as assessments_router
from app.payments.paypal import PayPalClient
from app.routers.payments import router as payments_router

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

app = FastAPI(
    title="TrustFlow API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

_configure_elastic_apm(app)

app.include_router(payments_router)
app.include_router(assessments_router)
app.include_router(agent_router)


@app.middleware("http")
async def add_trace_context(request: Request, call_next):
    trace_id = parse_traceparent(request.headers.get("traceparent"))
    async with request_trace(trace_id) as context:
        started = context.started_at
        try:
            response = await call_next(request)
        except Exception as error:
            log_event(
                "error",
                "http.request",
                method=request.method,
                path=request.url.path,
                statusCode=500,
                error=type(error).__name__,
            )
            raise
        response.headers["traceparent"] = f"00-{context.trace_id}-{context.span_id}-01"
        log_event(
            "error" if response.status_code >= 500 else "info",
            "http.request",
            method=request.method,
            path=request.url.path,
            statusCode=response.status_code,
            durationMs=round((time.monotonic() - started) * 1000),
        )
        return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "TrustFlow API"}


@app.get("/db/test")
def database_health() -> JSONResponse:
    try:
        database_name, database_time = test_connection()
    except Exception as error:
        log_event("error", "database.connection.failed", error=type(error).__name__)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Database connection failed. Check DATABASE_URL.",
            },
        )
    return JSONResponse(
        content={
            "success": True,
            "message": "Connected to Neon PostgreSQL",
            "database": database_name,
            "databaseTime": database_time.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
        }
    )


@app.post("/db/setup-schema")
def setup_database_schema() -> JSONResponse:
    try:
        apply_schema()
    except Exception as error:
        log_event("error", "database.schema.setup.failed", error=type(error).__name__)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Schema setup failed. Check DATABASE_URL.",
            },
        )
    return JSONResponse(
        content={
            "success": True,
            "message": "TrustFlow database schema created",
            "tables": [
                "users",
                "projects",
                "milestones",
                "evidence",
                "payments",
                "audit_events",
                "webhook_events",
            ],
        }
    )


if __name__ == "__main__":
    import uvicorn

    try:
        port = int(os.getenv("PORT", "3000"))
    except ValueError:
        port = 3000
    uvicorn.run(app, host="0.0.0.0", port=port or 3000)
