from __future__ import annotations

import json
import logging
import re
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator
from uuid import uuid4

_TRACEPARENT = re.compile(r"^(?:[\da-f]{2})-([\da-f]{32})-([\da-f]{16})-(?:[\da-f]{2})$", re.I)


@dataclass(frozen=True)
class TraceContext:
    trace_id: str
    span_id: str
    started_at: float


_current_trace: ContextVar[TraceContext | None] = ContextVar("trustflow_trace", default=None)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        context = _current_trace.get()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "event": getattr(record, "event", record.getMessage()),
        }
        if context:
            payload.update(traceId=context.trace_id, spanId=context.span_id)
        fields = getattr(record, "fields", {})
        payload.update(fields)
        return json.dumps(payload, default=str, separators=(",", ":"))


_logger = logging.getLogger("trustflow")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(_JsonFormatter())
    _logger.addHandler(_handler)
_logger.setLevel(logging.INFO)
_logger.propagate = False


def log_event(level: str, event: str, **fields: Any) -> None:
    _logger.log(
        getattr(logging, level.upper(), logging.INFO),
        event,
        extra={"event": event, "fields": fields},
    )


def parse_traceparent(value: str | None) -> str | None:
    if not value:
        return None
    match = _TRACEPARENT.fullmatch(value.strip())
    if not match or match.group(1) == "0" * 32 or match.group(2) == "0" * 16:
        return None
    return match.group(1).lower()


@asynccontextmanager
async def request_trace(trace_id: str | None = None) -> AsyncIterator[TraceContext]:
    context = TraceContext(
        trace_id=trace_id or uuid4().hex,
        span_id=uuid4().hex[:16],
        started_at=time.monotonic(),
    )
    token = _current_trace.set(context)
    try:
        yield context
    finally:
        _current_trace.reset(token)


@asynccontextmanager
async def traced(name: str) -> AsyncIterator[None]:
    parent = _current_trace.get()
    context = TraceContext(
        trace_id=parent.trace_id if parent else uuid4().hex,
        span_id=uuid4().hex[:16],
        started_at=time.monotonic(),
    )
    token = _current_trace.set(context)
    log_event("info", "span.start", span=name)
    try:
        yield
    except Exception as error:
        log_event(
            "error",
            "span.end",
            span=name,
            durationMs=round((time.monotonic() - context.started_at) * 1000),
            status="error",
            error=type(error).__name__,
        )
        raise
    else:
        log_event(
            "info",
            "span.end",
            span=name,
            durationMs=round((time.monotonic() - context.started_at) * 1000),
            status="ok",
        )
    finally:
        _current_trace.reset(token)
