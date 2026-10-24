from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb

from app.db.repository import transaction
from app.integrations.zapier import send_event
from app.observability import log_event


def enqueue_event(connection, event_name: str, data: dict) -> None:
    if not os.getenv("ZAPIER_WEBHOOK_URL"):
        return
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    dedupe_key = hashlib.sha256(f"{event_name}:{canonical}".encode()).hexdigest()
    connection.execute(
        "INSERT INTO integration_outbox(event_name, dedupe_key, payload) VALUES (%s, %s, %s) ON CONFLICT (dedupe_key) DO NOTHING",
        (event_name, dedupe_key, Jsonb(data)),
    )


async def deliver_pending(limit: int = 10) -> int:
    if not os.getenv("ZAPIER_WEBHOOK_URL"):
        return 0
    now = datetime.now(timezone.utc)
    with transaction() as connection:
        rows = connection.execute(
            """SELECT id, event_name, payload, attempts FROM integration_outbox
               WHERE delivery_status = 'pending' AND next_attempt_at <= %s
                 AND (locked_until IS NULL OR locked_until < %s)
               ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED""",
            (now, now, max(1, min(limit, 50))),
        ).fetchall()
        for row in rows:
            connection.execute("UPDATE integration_outbox SET locked_until = %s WHERE id = %s", (now + timedelta(minutes=2), row["id"]))

    delivered = 0
    for row in rows:
        try:
            ok = await send_event(row["event_name"], row["payload"])
        except Exception as error:  # delivery must never change the transaction result
            ok = False
            log_event("warning", "integration.outbox.error", error=type(error).__name__)
        attempts = row["attempts"] + 1
        with transaction() as connection:
            if ok:
                connection.execute(
                    """UPDATE integration_outbox SET delivery_status = 'delivered', attempts = %s,
                       delivered_at = NOW(), locked_until = NULL, last_error = NULL WHERE id = %s""",
                    (attempts, row["id"]),
                )
                delivered += 1
            else:
                delay_seconds = min(3600, 15 * (2 ** min(attempts - 1, 8)))
                connection.execute(
                    """UPDATE integration_outbox SET attempts = %s, next_attempt_at = %s,
                       locked_until = NULL, last_error = 'delivery failed' WHERE id = %s""",
                    (attempts, datetime.now(timezone.utc) + timedelta(seconds=delay_seconds), row["id"]),
                )
    return delivered
