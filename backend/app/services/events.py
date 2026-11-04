from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit
from uuid import NAMESPACE_URL, uuid5

from psycopg.types.json import Jsonb

from app.db.repository import transaction
from app.integrations.zapier import send_event
from app.observability import log_event


def event_recipient_email(connection, user_id: str) -> str | None:
    """Load only the intended notification recipient's email for Zapier delivery."""
    row = connection.execute("SELECT email FROM users WHERE id = %s", (user_id,)).fetchone()
    return row["email"] if row else None


def event_recipient_name(connection, user_id: str) -> str | None:
    """Load the intended notification recipient's display name for Zapier."""
    row = connection.execute("SELECT display_name FROM users WHERE id = %s", (user_id,)).fetchone()
    return row["display_name"] if row else None


def enqueue_event(connection, event_name: str, data: dict, *, idempotency_key: str | None = None) -> None:
    """Persist an event in the caller's business transaction.

    Queueing is independent of Zapier configuration so provider downtime or a
    temporarily missing hook URL cannot discard a successfully saved event.
    """
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    identity = idempotency_key if idempotency_key is not None else canonical
    dedupe_key = hashlib.sha256(f"{event_name}:{identity}".encode()).hexdigest()
    connection.execute(
        "INSERT INTO integration_outbox(event_name, dedupe_key, payload) VALUES (%s, %s, %s) ON CONFLICT (dedupe_key) DO NOTHING",
        (event_name, dedupe_key, Jsonb(data)),
    )


def _frontend_origin() -> tuple[str, str] | None:
    base_url = os.getenv("TRUSTFLOW_FRONTEND_URL", "").strip()
    if not base_url and os.getenv("TRUSTFLOW_ENV", "development").lower() != "production":
        base_url = "http://localhost:5173"
    try:
        parsed = urlsplit(base_url)
        hostname = (parsed.hostname or "").lower()
        parsed.port  # Validate an explicitly configured port.
    except ValueError:
        return None
    local_host = hostname in {"localhost", "127.0.0.1", "::1"}
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or (parsed.scheme != "https" and not local_host)
    ):
        return None
    return parsed.scheme, parsed.netloc


def workspace_url() -> str | None:
    """Return a safe frontend URL for signing in and opening workspace invitations."""
    origin = _frontend_origin()
    if origin is None:
        return None
    return urlunsplit((origin[0], origin[1], "/", "", ""))


def milestone_review_url(project_id: str, milestone_id: str) -> str | None:
    """Return an authenticated SPA deep link, or None if no safe host is configured."""
    origin = _frontend_origin()
    if origin is None:
        return None
    query = urlencode({"project_id": project_id, "milestone_id": milestone_id})
    return urlunsplit((origin[0], origin[1], "/", query, ""))


async def deliver_pending(limit: int = 10) -> int:
    if not os.getenv("ZAPIER_WEBHOOK_URL", "").strip():
        return 0
    now = datetime.now(timezone.utc)
    with transaction() as connection:
        rows = connection.execute(
            """SELECT id, event_name, dedupe_key, payload, attempts, created_at FROM integration_outbox
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
            event_seed = row["dedupe_key"] or f"legacy-outbox-row:{row['id']}"
            event_id = str(uuid5(NAMESPACE_URL, f"trustflow:{row['event_name']}:{event_seed}"))
            occurred_at = row["created_at"]
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.replace(tzinfo=timezone.utc)
            occurred_at = occurred_at.astimezone(timezone.utc)
            result = await send_event(
                row["event_name"],
                row["payload"],
                event_id=event_id,
                occurred_at=occurred_at,
            )
        except Exception as error:  # delivery must never change the transaction result
            result = None
            log_event("warning", "integration.outbox.error", error=type(error).__name__)
        attempts = row["attempts"] + 1
        with transaction() as connection:
            if result and result.delivered:
                connection.execute(
                    """UPDATE integration_outbox SET delivery_status = 'delivered', attempts = %s,
                       delivered_at = NOW(), locked_until = NULL, last_error = NULL WHERE id = %s""",
                    (attempts, row["id"]),
                )
                delivered += 1
            else:
                delay_seconds = min(3600, 15 * (2 ** min(attempts - 1, 8)))
                last_error = result.error if result else "Zapier delivery failed unexpectedly"
                connection.execute(
                    """UPDATE integration_outbox SET attempts = %s, next_attempt_at = %s,
                       locked_until = NULL, last_error = %s WHERE id = %s""",
                    (attempts, datetime.now(timezone.utc) + timedelta(seconds=delay_seconds), last_error[:240], row["id"]),
                )
    return delivered
