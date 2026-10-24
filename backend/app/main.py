from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db.connection import test_connection
from app.observability import log_event, parse_traceparent, request_trace
from app.routers.auth import router as auth_router
from app.routers.payments import router as payments_router
from app.routers.workflow import router as workflow_router
from app.security import allowed_origins, get_current_user

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)


def _configure_elastic_apm(app: FastAPI) -> None:
    server_url = os.getenv("ELASTIC_APM_SERVER_URL")
    if not server_url:
        return

    import elasticapm
    from elasticapm.contrib.starlette import ElasticAPM

    client = elasticapm.Client(
        service_name=os.getenv("ELASTIC_APM_SERVICE_NAME", "trustflow-backend"),
        server_url=server_url,
        secret_token=os.getenv("ELASTIC_APM_SECRET_TOKEN") or None,
        environment=os.getenv("ELASTIC_APM_ENVIRONMENT", "development"),
        capture_body="off",
    )
    app.add_middleware(ElasticAPM, client=client)


app = FastAPI(
    title="TrustFlow API", docs_url=None, redoc_url=None, openapi_url=None
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(allowed_origins()),
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "traceparent", "x-csrf-token"],
    allow_credentials=True,
)
_configure_elastic_apm(app)
app.include_router(auth_router)
app.include_router(workflow_router)
app.include_router(payments_router)
# Vercel's public API rewrite preserves /api in the incoming request path.
# Keep the unprefixed routes too for Render and the local Vite proxy.
app.include_router(auth_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")
app.include_router(payments_router, prefix="/api")


@app.middleware("http")
async def add_trace_context(request: Request, call_next):
    content_length = request.headers.get("content-length", "")
    if content_length.isdigit() and int(content_length) > 15_000_000:
        return JSONResponse(status_code=413, content={"detail": "Request body is too large"})
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


@app.exception_handler(Exception)
async def sanitized_unexpected_error(request: Request, error: Exception) -> JSONResponse:
    log_event("error", "http.unhandled_exception", method=request.method, path=request.url.path, error=type(error).__name__)
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


@app.get("/health")
@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "TrustFlow API"}


@app.get("/agent/health")
@app.get("/api/agent/health")
async def agent_health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def readiness(_user: dict = Depends(get_current_user)) -> JSONResponse:
    try:
        test_connection()
    except Exception as error:
        log_event("error", "database.connection.failed", error=type(error).__name__)
        return JSONResponse(
            status_code=503, content={"ready": False, "error": "Storage is unavailable"}
        )
    return JSONResponse(content={"ready": True})


if __name__ == "__main__":
    import uvicorn

    try:
        port = int(os.getenv("PORT", "3000"))
    except ValueError:
        port = 3000
    uvicorn.run(app, host="0.0.0.0", port=port or 3000)
