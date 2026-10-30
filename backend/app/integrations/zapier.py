from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from app.observability import log_event


@dataclass(frozen=True)
class DeliveryResult:
    delivered: bool
    error: str | None = None


def _utc_iso(value: datetime | None) -> str:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


async def send_event(
    event: str,
    data: dict[str, Any],
    *,
    event_id: str | None = None,
    occurred_at: datetime | None = None,
) -> DeliveryResult:
    """Send a small, stable event envelope to a configured Zapier Catch Hook.

    The caller persists the event before this function is called. Do not include
    evidence text, credentials, or other sensitive values in event data.
    """
    webhook_url = os.getenv("ZAPIER_WEBHOOK_URL")
    if not webhook_url:
        return DeliveryResult(False, "ZAPIER_WEBHOOK_URL is not configured")

    payload = {
        "event": event,
        "event_type": event,
        "event_id": event_id,
        "occurred_at": _utc_iso(occurred_at),
        "data": data,
    }
    last_error = "Zapier delivery failed"
    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(webhook_url, json=payload)
            if response.is_success:
                log_event("info", "integration.zapier.delivered", eventName=event)
                return DeliveryResult(True)
            if response.status_code < 500 and response.status_code != 429:
                last_error = f"Zapier returned HTTP {response.status_code}"
                log_event(
                    "warning",
                    "integration.zapier.rejected",
                    eventName=event,
                    statusCode=response.status_code,
                )
                return DeliveryResult(False, last_error)
            last_error = f"Zapier returned HTTP {response.status_code}"
        except httpx.HTTPError as error:
            # Exception text can contain the secret Catch Hook URL; persist only
            # the safe class name in the outbox.
            last_error = type(error).__name__
        except Exception as error:
            last_error = type(error).__name__

        if attempt < 3:
            await asyncio.sleep(0.25 * (2 ** (attempt - 1)))

    log_event("warning", "integration.zapier.failed", eventName=event, error=last_error)
    return DeliveryResult(False, last_error)
