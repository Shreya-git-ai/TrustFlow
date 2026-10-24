from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any

import httpx

from app.observability import log_event


async def send_event(event: str, data: dict[str, Any]) -> bool:
    """Send a small event to a configured Zapier Catch Hook.

    Delivery is best-effort for this prototype. Do not include evidence text,
    credentials, or other sensitive values in event data.
    """
    webhook_url = os.getenv("ZAPIER_WEBHOOK_URL")
    if not webhook_url:
        return False

    payload = {
        "event": event,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(webhook_url, json=payload)
            if response.is_success:
                log_event("info", "integration.zapier.delivered", eventName=event)
                return True
            if response.status_code < 500 and response.status_code != 429:
                log_event(
                    "warning",
                    "integration.zapier.rejected",
                    eventName=event,
                    statusCode=response.status_code,
                )
                return False
        except httpx.HTTPError as error:
            if attempt == 3:
                log_event(
                    "warning",
                    "integration.zapier.failed",
                    eventName=event,
                    error=type(error).__name__,
                )
                return False

        if attempt < 3:
            await asyncio.sleep(0.25 * (2 ** (attempt - 1)))

    log_event("warning", "integration.zapier.failed", eventName=event)
    return False
