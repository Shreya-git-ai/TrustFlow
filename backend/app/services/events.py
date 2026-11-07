from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit
from uuid import NAMESPACE_URL, uuid5

from psycopg.types.json import Jsonb

from app.db.repository import read_connection, transaction
from app.integrations.zapier import send_event
from app.observability import log_event
from app.security import public_frontend_origin
from app.services.email import is_workflow_email_event, send_workflow_email


def event_recipient_email(connection, user_id: str) -> str | None:
    """Load the intended user's email for a TrustFlow SMTP notification."""
    row = connection.execute("SELECT email FROM users WHERE id = %s", (user_id,)).fetchone()
    return row["email"] if row else None


def event_recipient_name(connection, user_id: str) -> str | None:
    """Load the intended user's display name for a TrustFlow SMTP notification."""
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


def _workflow_email_context(event: str, data: dict) -> dict:
    """Fill names and destinations for older outbox rows as well as new events."""
    if (data.get("recipient_email") and data.get("recipient_name") and data.get("actor_name")
            and data.get("project_title") and (data.get("milestone_title") or not data.get("milestone_id"))):
        return data
    project_id = data.get("project_id")
    milestone_id = data.get("milestone_id")
    if not project_id and not milestone_id:
        return data
    with read_connection() as connection:
        if milestone_id:
            row = connection.execute(
                """SELECT project.id AS project_id, project.title AS project_title,
                          project.invited_email, client.email AS client_email,
                          client.display_name AS client_name, freelancer.email AS freelancer_email,
                          freelancer.display_name AS freelancer_name, milestone.title AS milestone_title
                   FROM milestones milestone JOIN projects project ON project.id = milestone.project_id
                   JOIN users client ON client.id = project.client_id
                   LEFT JOIN users freelancer ON freelancer.id = project.freelancer_id
                   WHERE milestone.id = %s""",
                (milestone_id,),
            ).fetchone()
        else:
            row = connection.execute(
                """SELECT project.id AS project_id, project.title AS project_title,
                          project.invited_email, client.email AS client_email,
                          client.display_name AS client_name, freelancer.email AS freelancer_email,
                          freelancer.display_name AS freelancer_name, NULL::text AS milestone_title
                   FROM projects project JOIN users client ON client.id = project.client_id
                   LEFT JOIN users freelancer ON freelancer.id = project.freelancer_id
                   WHERE project.id = %s""",
                (project_id,),
            ).fetchone()
    if row is None:
        return data
    context = dict(data)
    context.setdefault("project_title", row["project_title"])
    context.setdefault("project_name", row["project_title"])
    if row["milestone_title"]:
        context.setdefault("milestone_title", row["milestone_title"])
    context.setdefault("client_name", row["client_name"])
    context.setdefault("freelancer_name", row["freelancer_name"] or "")
    if event in {"project.invited", "project.invitation_resent", "project.invitation_cancelled", "milestone.created", "milestone.updated"}:
        context["recipient_email"] = context.get("recipient_email") or row["freelancer_email"] or row["invited_email"]
        context["recipient_name"] = context.get("recipient_name") or row["freelancer_name"] or ""
        context["actor_name"] = context.get("actor_name") or row["client_name"] or "A TrustFlow client"
    elif event in {"project.invitation_accepted", "project.invitation_declined", "milestone.agreement_accepted", "milestone.agreement_changes_requested", "evidence.submitted", "assessment.completed", "assessment.failed"}:
        context["recipient_email"] = context.get("recipient_email") or row["client_email"]
        context["recipient_name"] = context.get("recipient_name") or row["client_name"] or ""
        context["actor_name"] = context.get("actor_name") or row["freelancer_name"] or "Your freelancer"
    else:
        context["recipient_email"] = context.get("recipient_email") or row["freelancer_email"]
        context["recipient_name"] = context.get("recipient_name") or row["freelancer_name"] or ""
        context["actor_name"] = context.get("actor_name") or row["client_name"] or "Your client"
    return context


def _frontend_origin() -> tuple[str, str] | None:
    base_url = public_frontend_origin()
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
    webhook_configured = bool(os.getenv("ZAPIER_WEBHOOK_URL", "").strip())
    now = datetime.now(timezone.utc)
    with transaction() as connection:
        rows = connection.execute(
            """SELECT id, event_name, dedupe_key, payload, attempts, created_at,
                      smtp_delivered_at, webhook_delivered_at FROM integration_outbox
               WHERE delivery_status = 'pending' AND next_attempt_at <= %s
                 AND (locked_until IS NULL OR locked_until < %s)
               ORDER BY id LIMIT %s FOR UPDATE SKIP LOCKED""",
            (now, now, max(1, min(limit, 50))),
        ).fetchall()
        for row in rows:
            connection.execute("UPDATE integration_outbox SET locked_until = %s WHERE id = %s", (now + timedelta(minutes=2), row["id"]))

    delivered = 0
    for row in rows:
        smtp_needed = is_workflow_email_event(row["event_name"])
        # Keep optional business automations, but never pass SMTP recipients to
        # Zapier for events that now send user-facing email directly.
        webhook_needed = True
        smtp_done = not smtp_needed or row["smtp_delivered_at"] is not None
        webhook_done = row["webhook_delivered_at"] is not None or (smtp_needed and not webhook_configured)
        failure = None
        if smtp_needed and not smtp_done:
            try:
                payload = _workflow_email_context(row["event_name"], dict(row["payload"]))
                await asyncio.to_thread(send_workflow_email, row["event_name"], payload)
                smtp_done = True
                with transaction() as connection:
                    connection.execute(
                        "UPDATE integration_outbox SET smtp_delivered_at = NOW() WHERE id = %s",
                        (row["id"],),
                    )
            except Exception as error:
                failure = type(error).__name__
                log_event("warning", "email.outbox.error", eventName=row["event_name"], error=failure)
        if webhook_needed and webhook_configured and not webhook_done:
            try:
                event_seed = row["dedupe_key"] or f"legacy-outbox-row:{row['id']}"
                event_id = str(uuid5(NAMESPACE_URL, f"trustflow:{row['event_name']}:{event_seed}"))
                occurred_at = row["created_at"]
                if occurred_at.tzinfo is None:
                    occurred_at = occurred_at.replace(tzinfo=timezone.utc)
                occurred_at = occurred_at.astimezone(timezone.utc)
                webhook_payload = dict(row["payload"])
                if smtp_needed:
                    for field in ("recipient_email", "recipient_emails", "client_email", "freelancer_email", "workspace_url"):
                        webhook_payload.pop(field, None)
                result = await send_event(
                    row["event_name"], webhook_payload,
                    event_id=event_id, occurred_at=occurred_at,
                )
                if not result.delivered:
                    failure = failure or result.error or "Zapier delivery failed"
                else:
                    webhook_done = True
                    with transaction() as connection:
                        connection.execute(
                            "UPDATE integration_outbox SET webhook_delivered_at = NOW() WHERE id = %s",
                            (row["id"],),
                        )
            except Exception as error:  # delivery must never change the transaction result
                failure = failure or type(error).__name__
                log_event("warning", "integration.outbox.error", eventName=row["event_name"], error=type(error).__name__)
        attempts = row["attempts"] + 1
        with transaction() as connection:
            if smtp_done and webhook_done and not failure:
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
                       locked_until = NULL, last_error = %s WHERE id = %s""",
                    (attempts, datetime.now(timezone.utc) + timedelta(seconds=delay_seconds), (failure or "Delivery pending")[0:240], row["id"]),
                )
    return delivered
