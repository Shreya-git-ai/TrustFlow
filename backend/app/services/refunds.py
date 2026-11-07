from __future__ import annotations

import hmac
import os
from decimal import Decimal

from psycopg.types.json import Jsonb

from app.db.repository import read_connection, transaction
from app.services.events import enqueue_event
from app.services.workflow import DomainError, _audit


def verify_agent_token(supplied: str) -> bool:
    expected = os.getenv("TRUSTFLOW_AGENT_TOKEN", "")
    return bool(expected and supplied and hmac.compare_digest(expected, supplied))


def _reserved_amount(connection, payment_id: str, exclude_proposal_id: str | None = None) -> Decimal:
    row = connection.execute(
        """SELECT
                 COALESCE((SELECT SUM(refund.amount) FROM payment_refunds refund
                           WHERE refund.payment_id = %s AND refund.status IN ('PENDING', 'COMPLETED')), 0)
               + COALESCE((SELECT SUM(proposal.amount) FROM refund_proposals proposal
                           WHERE proposal.payment_id = %s AND proposal.status IN ('pending', 'processing')
                             AND (%s::uuid IS NULL OR proposal.id <> %s::uuid)
                             AND NOT EXISTS (
                                 SELECT 1 FROM payment_refunds refund
                                 WHERE refund.proposal_id = proposal.id
                                   AND refund.status IN ('PENDING', 'COMPLETED')
                             )), 0) AS reserved""",
        (payment_id, payment_id, exclude_proposal_id, exclude_proposal_id),
    ).fetchone()
    return row["reserved"]


def _serialize_proposal(row: dict) -> dict:
    item = dict(row)
    for key in ("id", "payment_id", "milestone_id", "project_id", "reviewed_by"):
        if item.get(key) is not None:
            item[key] = str(item[key])
    item["amount"] = str(item["amount"])
    item["currency"] = item["currency"].strip()
    item["zendesk_ticket_id"] = str(item["zendesk_ticket_id"]) if item.get("zendesk_ticket_id") else None
    if item.get("refunded_amount") is not None:
        item["refunded_amount"] = str(item["refunded_amount"])
    return item


def _matches_proposal(row: dict, payment_id: str, amount: Decimal, reason: str,
                      zendesk_ticket_id: int | None, slack_channel_id: str | None,
                      slack_thread_ts: str | None) -> bool:
    return (
        str(row["payment_id"]) == payment_id
        and row["amount"] == amount
        and row["reason"] == reason.strip()
        and row["zendesk_ticket_id"] == zendesk_ticket_id
        and row["slack_channel_id"] == slack_channel_id
        and row["slack_thread_ts"] == slack_thread_ts
    )


def create_agent_proposal(
    payment_id: str,
    proposal_key: str,
    amount: Decimal,
    reason: str,
    *,
    zendesk_ticket_id: int | None = None,
    slack_channel_id: str | None = None,
    slack_thread_ts: str | None = None,
) -> dict:
    proposal_key = proposal_key.strip()
    reason = reason.strip()
    if not proposal_key or len(reason) < 10:
        raise DomainError(422, "Include a proposal key and a meaningful refund reason")
    if amount <= 0 or amount.as_tuple().exponent < -2:
        raise DomainError(422, "Refund amount must be positive with at most two decimal places")
    with transaction() as connection:
        duplicate = connection.execute(
            """SELECT proposal.*, payment.currency FROM refund_proposals proposal
               JOIN payments payment ON payment.id = proposal.payment_id
               WHERE proposal.proposal_key = %s FOR UPDATE OF proposal""",
            (proposal_key,),
        ).fetchone()
        if duplicate:
            if not _matches_proposal(duplicate, payment_id, amount, reason, zendesk_ticket_id, slack_channel_id, slack_thread_ts):
                raise DomainError(409, "This proposal key was already used for different refund details")
            return _serialize_proposal(duplicate)

        payment = connection.execute(
            """SELECT payment.*, milestone.project_id, milestone.id AS milestone_id,
                      project.client_id, project.title AS project_title,
                      milestone.title AS milestone_title
               FROM payments payment
               JOIN milestones milestone ON milestone.id = payment.milestone_id
               JOIN projects project ON project.id = milestone.project_id
               WHERE payment.id = %s FOR UPDATE OF payment""",
            (payment_id,),
        ).fetchone()
        if payment is None:
            raise DomainError(404, "Payment not found")
        if payment["status"] not in {"captured", "partially_refunded"} or not payment["paypal_capture_id"]:
            raise DomainError(409, "Only a captured PayPal payment can receive a refund proposal")
        available = payment["amount"] - _reserved_amount(connection, payment_id)
        if amount > available:
            raise DomainError(409, f"Refund amount exceeds the remaining refundable balance of {available:.2f}")

        row = connection.execute(
            """INSERT INTO refund_proposals(payment_id, proposal_key, amount, reason,
                       zendesk_ticket_id, slack_channel_id, slack_thread_ts, paypal_request_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s, gen_random_uuid()::text)
               ON CONFLICT (proposal_key) DO NOTHING
               RETURNING *""",
            (payment_id, proposal_key, amount, reason.strip(), zendesk_ticket_id, slack_channel_id, slack_thread_ts),
        ).fetchone()
        if row is None:
            duplicate = connection.execute(
                """SELECT proposal.*, payment.currency FROM refund_proposals proposal
                   JOIN payments payment ON payment.id = proposal.payment_id
                   WHERE proposal.proposal_key = %s FOR UPDATE OF proposal""",
                (proposal_key,),
            ).fetchone()
            if duplicate is None or not _matches_proposal(duplicate, payment_id, amount, reason, zendesk_ticket_id, slack_channel_id, slack_thread_ts):
                raise DomainError(409, "This proposal key was already used for different refund details")
            return _serialize_proposal(duplicate)
        _audit(
            connection,
            "refund.proposed",
            {"role": "agent", "id": None},
            project_id=payment["project_id"],
            milestone_id=payment["milestone_id"],
            payment_id=payment_id,
            details={"proposal_id": str(row["id"]), "amount": str(amount), "currency": payment["currency"].strip()},
        )
        return _serialize_proposal({**row, "currency": payment["currency"]})


def list_for_merchant(user: dict, status: str = "all") -> list[dict]:
    if user["role"] != "client":
        raise DomainError(403, "Only the project client can review refund proposals")
    if status not in {"all", "pending", "processing", "refunded", "rejected", "failed"}:
        raise DomainError(422, "Unsupported refund proposal status")
    with read_connection() as connection:
        rows = connection.execute(
            """SELECT proposal.id, proposal.payment_id, payment.milestone_id,
                      milestone.project_id, project.title AS project_title,
                      milestone.title AS milestone_title, proposal.amount, payment.currency,
                      proposal.reason, proposal.agent_name, proposal.status,
                      proposal.zendesk_ticket_id, proposal.slack_channel_id,
                      proposal.slack_thread_ts, proposal.paypal_refund_id,
                      proposal.proposed_at, proposal.reviewed_at, proposal.reviewed_by,
                      payment.paypal_capture_id, payment.refunded_amount
               FROM refund_proposals proposal
               JOIN payments payment ON payment.id = proposal.payment_id
               JOIN milestones milestone ON milestone.id = payment.milestone_id
               JOIN projects project ON project.id = milestone.project_id
               WHERE project.client_id = %s AND (%s = 'all' OR proposal.status = %s)
               ORDER BY CASE proposal.status WHEN 'pending' THEN 0 WHEN 'processing' THEN 1 ELSE 2 END,
                        proposal.proposed_at DESC
               LIMIT 500""",
            (user["id"], status, status),
        ).fetchall()
    return [_serialize_proposal(row) for row in rows]


def _proposal_for_update(connection, proposal_id: str, user: dict) -> dict:
    row = connection.execute(
        """SELECT proposal.*, payment.status AS payment_status,
                  payment.paypal_capture_id, payment.paypal_order_id, payment.paypal_payee_merchant_id,
                  payment.amount AS payment_amount,
                  payment.currency, payment.refunded_amount, payment.milestone_id,
                  milestone.project_id, project.client_id,
                  project.title AS project_title, milestone.title AS milestone_title
           FROM refund_proposals proposal
           JOIN payments payment ON payment.id = proposal.payment_id
           JOIN milestones milestone ON milestone.id = payment.milestone_id
           JOIN projects project ON project.id = milestone.project_id
           WHERE proposal.id = %s AND project.client_id = %s
           FOR UPDATE OF proposal, payment""",
        (proposal_id, user["id"]),
    ).fetchone()
    if row is None:
        raise DomainError(404, "Refund proposal not found")
    return dict(row)


def decide_proposal(user: dict, proposal_id: str, decision: str, note: str = "") -> dict:
    if user["role"] != "client":
        raise DomainError(403, "Only the project client can review refund proposals")
    with transaction() as connection:
        proposal = _proposal_for_update(connection, proposal_id, user)
        if decision == "reject":
            if proposal["status"] == "rejected":
                return _serialize_proposal(proposal)
            if proposal["status"] != "pending":
                raise DomainError(409, "Only pending refund proposals can be rejected")
            row = connection.execute(
                """UPDATE refund_proposals SET status = 'rejected', reviewed_by = %s,
                          reviewed_at = NOW(), updated_at = NOW()
                   WHERE id = %s RETURNING *""",
                (user["id"], proposal_id),
            ).fetchone()
            _audit(
                connection,
                "refund.rejected",
                user,
                project_id=proposal["project_id"],
                milestone_id=proposal["milestone_id"],
                payment_id=proposal["payment_id"],
                details={"proposal_id": proposal_id, "note": note.strip()[:500]},
            )
            return _serialize_proposal({**row, "currency": proposal["currency"]})

        if decision != "approve":
            raise DomainError(422, "Choose approve or reject")
        if proposal["status"] == "refunded":
            return _serialize_proposal(proposal)
        if proposal["status"] == "processing":
            return dict(proposal)
        if proposal["status"] != "pending":
            raise DomainError(409, "Only pending refund proposals can be approved")
        if proposal["payment_status"] not in {"captured", "partially_refunded"} or not proposal["paypal_capture_id"]:
            raise DomainError(409, "The PayPal payment is no longer refundable")
        if proposal["amount"] > proposal["payment_amount"] - _reserved_amount(connection, str(proposal["payment_id"]), proposal_id):
            raise DomainError(409, "The remaining refundable balance is lower than this proposal")

        row = connection.execute(
            """UPDATE refund_proposals SET status = 'processing', reviewed_by = %s,
                      reviewed_at = NOW(), updated_at = NOW()
               WHERE id = %s RETURNING *""",
            (user["id"], proposal_id),
        ).fetchone()
        _audit(
            connection,
            "refund.approved",
            user,
            project_id=proposal["project_id"],
            milestone_id=proposal["milestone_id"],
            payment_id=proposal["payment_id"],
            details={"proposal_id": proposal_id, "amount": str(proposal["amount"]), "currency": proposal["currency"].strip()},
        )
        return {
            **row,
            "currency": proposal["currency"],
            "project_id": proposal["project_id"],
            "project_title": proposal["project_title"],
            "milestone_id": proposal["milestone_id"],
            "milestone_title": proposal["milestone_title"],
            "paypal_capture_id": proposal["paypal_capture_id"],
        }


def fail_proposal(proposal_id: str, message: str) -> None:
    with transaction() as connection:
        row = connection.execute(
            """UPDATE refund_proposals SET status = 'failed', updated_at = NOW()
               WHERE id = %s AND status = 'processing'
               RETURNING id, payment_id""",
            (proposal_id,),
        ).fetchone()
        if row:
            connection.execute(
                "UPDATE payment_refunds SET status = 'FAILED', updated_at = NOW() WHERE proposal_id = %s AND status = 'PENDING'",
                (row["id"],),
            )
            payment = connection.execute(
                """SELECT payment.milestone_id, milestone.project_id FROM payments payment
                   JOIN milestones milestone ON milestone.id = payment.milestone_id
                   WHERE payment.id = %s""",
                (row["payment_id"],),
            ).fetchone()
            if payment:
                _audit(
                    connection,
                    "refund.failed",
                    {"role": "paypal", "id": None},
                    project_id=payment["project_id"],
                    milestone_id=payment["milestone_id"],
                    payment_id=row["payment_id"],
                    details={"proposal_id": proposal_id, "reason": message[:200]},
                )


def record_paypal_refund(
    capture_id: str,
    refund_id: str,
    amount: Decimal,
    currency: str,
    provider_status: str,
    *,
    webhook_event_id: str | None = None,
    proposal_id: str | None = None,
) -> bool:
    if not capture_id or not refund_id or amount <= 0 or provider_status not in {"PENDING", "COMPLETED", "FAILED"}:
        return False
    with transaction() as connection:
        payment = connection.execute(
            """SELECT payment.*, milestone.project_id, milestone.title AS milestone_title,
                      project.title AS project_title, client.email AS client_email,
                      client.display_name AS recipient_name
               FROM payments payment
               JOIN milestones milestone ON milestone.id = payment.milestone_id
               JOIN projects project ON project.id = milestone.project_id
               JOIN users client ON client.id = project.client_id
               WHERE payment.paypal_capture_id = %s
               FOR UPDATE OF payment""",
            (capture_id,),
        ).fetchone()
        if payment is None or currency != payment["currency"].strip():
            return False

        existing = connection.execute(
            "SELECT * FROM payment_refunds WHERE paypal_refund_id = %s FOR UPDATE",
            (refund_id,),
        ).fetchone()
        if existing and (str(existing["payment_id"]) != str(payment["id"]) or existing["amount"] != amount):
            return False

        proposal = None
        if existing and existing["proposal_id"]:
            proposal = connection.execute(
                "SELECT * FROM refund_proposals WHERE id = %s FOR UPDATE",
                (existing["proposal_id"],),
            ).fetchone()
        if proposal is None and proposal_id:
            proposal = connection.execute(
                "SELECT * FROM refund_proposals WHERE id = %s AND payment_id = %s FOR UPDATE",
                (proposal_id, payment["id"]),
            ).fetchone()
        if proposal is None:
            proposal = connection.execute(
                """SELECT * FROM refund_proposals
                   WHERE payment_id = %s AND status = 'processing' AND amount = %s
                   ORDER BY proposed_at LIMIT 2 FOR UPDATE""",
                (payment["id"], amount),
            ).fetchall()
            proposal = proposal[0] if len(proposal) == 1 else None
        if proposal and proposal["amount"] != amount:
            return False

        if existing and existing["status"] == "COMPLETED" and (not webhook_event_id or existing["completion_notified"]):
            return True
        if provider_status == "COMPLETED":
            other_completed = connection.execute(
                """SELECT COALESCE(SUM(amount), 0) AS amount FROM payment_refunds
                   WHERE payment_id = %s AND status = 'COMPLETED' AND paypal_refund_id <> %s""",
                (payment["id"], refund_id),
            ).fetchone()["amount"]
            if other_completed + amount > payment["amount"]:
                return False

        proposal_id = proposal["id"] if proposal else (existing["proposal_id"] if existing else None)
        if existing:
            connection.execute(
                """UPDATE payment_refunds SET status = %s,
                          webhook_confirmed = webhook_confirmed OR %s,
                          webhook_event_id = COALESCE(webhook_event_id, %s),
                          completion_notified = completion_notified OR %s, updated_at = NOW()
                   WHERE paypal_refund_id = %s""",
                (provider_status, bool(webhook_event_id), webhook_event_id,
                 bool(webhook_event_id and provider_status == "COMPLETED"), refund_id),
            )
        else:
            connection.execute(
                """INSERT INTO payment_refunds(payment_id, proposal_id, paypal_refund_id,
                          amount, currency, status, webhook_confirmed, webhook_event_id, completion_notified)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (payment["id"], proposal_id, refund_id, amount, currency, provider_status,
                 bool(webhook_event_id), webhook_event_id,
                 bool(webhook_event_id and provider_status == "COMPLETED")),
            )

        sums = connection.execute(
            """SELECT COALESCE(SUM(amount) FILTER (WHERE status = 'COMPLETED'), 0) AS completed,
                      COALESCE(SUM(amount) FILTER (WHERE status = 'PENDING'), 0) AS pending
               FROM payment_refunds WHERE payment_id = %s""",
            (payment["id"],),
        ).fetchone()
        completed_amount = sums["completed"]
        next_payment_status = (
            "refunded" if completed_amount == payment["amount"]
            else "partially_refunded" if completed_amount > 0
            else "captured"
        )
        connection.execute(
            "UPDATE payments SET refunded_amount = %s, status = %s, updated_at = NOW() WHERE id = %s",
            (completed_amount, next_payment_status, payment["id"]),
        )
        if proposal_id:
            connection.execute(
                """UPDATE refund_proposals SET paypal_refund_id = %s,
                          status = CASE WHEN %s = 'COMPLETED' THEN 'refunded'
                                        WHEN %s = 'FAILED' THEN 'failed' ELSE 'processing' END,
                          updated_at = NOW()
                   WHERE id = %s""",
                (refund_id, provider_status, provider_status, proposal_id),
            )

        confirmed_by_webhook_now = (
            bool(webhook_event_id)
            and provider_status == "COMPLETED"
            and not (existing and existing["completion_notified"])
        )
        if provider_status == "COMPLETED" and confirmed_by_webhook_now:
            ticket = proposal or {}
            payload = {
                "paypal_event_type": "PAYMENT.CAPTURE.REFUNDED",
                "paypal_webhook_event_id": webhook_event_id,
                "refund_id": refund_id,
                "capture_id": capture_id,
                "order_id": payment["paypal_order_id"],
                "payment_id": str(payment["id"]),
                "recipient_email": payment["client_email"],
                "recipient_name": payment["recipient_name"],
                "project_id": str(payment["project_id"]),
                "project_title": payment["project_title"],
                "milestone_id": str(payment["milestone_id"]),
                "milestone_title": payment["milestone_title"],
                "proposal_id": str(proposal_id) if proposal_id else None,
                "refund_amount": f"{amount:.2f}",
                "cumulative_refunded_amount": f"{completed_amount:.2f}",
                "currency": currency,
                "payment_refund_status": next_payment_status,
                "zendesk_ticket_id": str(ticket.get("zendesk_ticket_id")) if ticket.get("zendesk_ticket_id") else None,
                "slack_channel_id": ticket.get("slack_channel_id"),
                "slack_thread_ts": ticket.get("slack_thread_ts"),
                "ticket_lookup_key": capture_id,
            }
            enqueue_event(connection, "PAYMENT.CAPTURE.REFUNDED", payload)
            _audit(
                connection,
                "payment.refunded",
                {"role": "paypal", "id": None},
                project_id=payment["project_id"],
                milestone_id=payment["milestone_id"],
                payment_id=payment["id"],
                details={"refund_id": refund_id, "capture_id": capture_id, "amount": str(amount), "currency": currency, "proposal_id": str(proposal_id) if proposal_id else None},
            )
        return True
