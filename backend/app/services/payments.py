from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from app.db.repository import read_connection, transaction
from app.services.workflow import DomainError, _audit
from app.services.events import enqueue_event, milestone_review_url


def list_for_user(user: dict) -> list[dict]:
    with read_connection() as connection:
        rows = connection.execute(
            """SELECT payment.id, payment.milestone_id, project.id AS project_id,
                      project.title AS project_title, milestone.title AS milestone_title,
                      payment.amount, payment.refunded_amount, payment.currency, payment.status, payment.updated_at
               FROM payments AS payment
               JOIN milestones AS milestone ON milestone.id = payment.milestone_id
               JOIN projects AS project ON project.id = milestone.project_id
               WHERE project.client_id = %s OR project.freelancer_id = %s
               ORDER BY payment.updated_at DESC, payment.id DESC
               LIMIT 200""",
            (user["id"], user["id"]),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["id"] = str(item["id"])
        item["milestone_id"] = str(item["milestone_id"])
        item["project_id"] = str(item["project_id"])
        item["amount"] = str(item["amount"])
        item["refunded_amount"] = str(item["refunded_amount"])
        item["currency"] = item["currency"].strip()
        result.append(item)
    return result


def prepare_order(user: dict, milestone_id: str) -> dict:
    if user["role"] != "client":
        raise DomainError(403, "Only the project client can start a payment")
    with transaction() as connection:
        milestone = connection.execute(
            """SELECT m.*, p.client_id, p.membership_status, p.status AS project_status
               FROM milestones m JOIN projects p ON p.id = m.project_id
               WHERE m.id = %s FOR UPDATE OF m, p""",
            (milestone_id,),
        ).fetchone()
        if milestone is None or str(milestone["client_id"]) != user["id"]:
            raise DomainError(404, "Milestone not found")
        if milestone["membership_status"] != "accepted":
            raise DomainError(409, "The freelancer must accept the project first")
        if milestone["project_status"] != "active":
            raise DomainError(409, "Payments are unavailable for a cancelled project")
        if milestone["agreement_status"] != "accepted":
            raise DomainError(409, "The freelancer must accept the milestone terms before payment")
        row = connection.execute("SELECT * FROM payments WHERE milestone_id = %s FOR UPDATE", (milestone_id,)).fetchone()
        if row is None:
            row = connection.execute(
                """INSERT INTO payments(milestone_id, created_by, amount, currency, status,
                           create_request_id, authorize_request_id)
                   VALUES (%s, %s, %s, %s, 'created', %s, %s)
                   ON CONFLICT (milestone_id) DO NOTHING RETURNING *""",
                (milestone_id, user["id"], milestone["amount"], milestone["currency"], str(uuid4()), str(uuid4())),
            ).fetchone()
            if row is None:
                row = connection.execute("SELECT * FROM payments WHERE milestone_id = %s FOR UPDATE", (milestone_id,)).fetchone()
            else:
                _audit(connection, "payment.initiated", user, project_id=milestone["project_id"], milestone_id=milestone_id, payment_id=row["id"], details={"amount": str(row["amount"]), "currency": row["currency"]})
        elif row["status"] not in {"created", "buyer_approved"}:
            raise DomainError(409, "Payment has already moved beyond order creation")
        if row["paypal_order_id"]:
            return dict(row)
        # A row with no PayPal order has no provider-side marketplace routing to preserve.
        if row.get("paypal_payee_merchant_id"):
            row = connection.execute(
                "UPDATE payments SET paypal_payee_merchant_id = NULL WHERE id = %s RETURNING *",
                (row["id"],),
            ).fetchone()
        return dict(row)


def save_order(payment_id: str, response: dict, approval_url: str | None) -> dict:
    order_id = response.get("id")
    if not isinstance(order_id, str) or not order_id:
        raise DomainError(502, "PayPal did not return an order identifier")
    with transaction() as connection:
        row = connection.execute(
            """UPDATE payments SET paypal_order_id = %s, paypal_approval_url = %s, status = 'created', updated_at = NOW()
               WHERE id = %s AND status IN ('created', 'buyer_approved') RETURNING *""",
            (order_id, approval_url, payment_id),
        ).fetchone()
        if row is None:
            raise DomainError(409, "Payment state changed while creating the order")
        enqueue_event(connection, "payment.order_created", {"order_id": order_id, "status": response.get("status"), "amount": str(row["amount"]), "currency": row["currency"].strip()})
        return dict(row)


def payment_for_client(user: dict, milestone_id: str) -> dict:
    if user["role"] != "client":
        raise DomainError(403, "Only the project client can access payment operations")
    with read_connection() as connection:
        row = connection.execute(
            """SELECT pay.*, m.project_id, m.title AS milestone_title, p.title AS project_title,
                      m.evidence_revision, m.status AS milestone_status,
                      m.approved_evidence_revision, m.approved_assessment_id,
                      p.client_id, p.freelancer_id, client.email AS client_email,
                      freelancer.email AS freelancer_email, client.display_name AS client_name,
                      freelancer.display_name AS freelancer_name
               FROM payments pay JOIN milestones m ON m.id = pay.milestone_id
               JOIN projects p ON p.id = m.project_id
               JOIN users client ON client.id = p.client_id
               LEFT JOIN users freelancer ON freelancer.id = p.freelancer_id
               WHERE pay.milestone_id = %s""",
            (milestone_id,),
        ).fetchone()
    if row is None or str(row["client_id"]) != user["id"]:
        raise DomainError(404, "Payment not found")
    return dict(row)


def set_buyer_approved(user: dict, milestone_id: str) -> dict:
    payment = payment_for_client(user, milestone_id)
    if not payment["paypal_order_id"]:
        raise DomainError(409, "Create a PayPal order first")
    with transaction() as connection:
        row = connection.execute(
            "UPDATE payments SET status = 'buyer_approved', updated_at = NOW() WHERE id = %s AND status = 'created' RETURNING *",
            (payment["id"],),
        ).fetchone()
        if row is None:
            if payment["status"] == "buyer_approved":
                return payment
            raise DomainError(409, "Payment is not awaiting buyer approval")
        return dict(row)


def mark_authorized(user: dict, milestone_id: str, authorization_id: str, amount: Decimal, currency: str, provider_status: str) -> dict:
    payment = payment_for_client(user, milestone_id)
    if amount != payment["amount"] or currency != payment["currency"].strip():
        raise DomainError(502, "PayPal authorization amount does not match the milestone")
    if provider_status not in {"CREATED", "AUTHORIZED"}:
        raise DomainError(502, "PayPal did not confirm an active authorization")
    with transaction() as connection:
        row = connection.execute(
            """UPDATE payments SET paypal_authorization_id = %s, status = 'authorized', updated_at = NOW()
               WHERE id = %s AND status IN ('created', 'buyer_approved', 'authorized') RETURNING *""",
            (authorization_id, payment["id"]),
        ).fetchone()
        if row is None:
            raise DomainError(409, "Payment state changed while authorizing")
        _audit(connection, "payment.authorized", user, project_id=payment["project_id"], milestone_id=milestone_id, payment_id=row["id"], details={"authorization_id": authorization_id, "amount": str(amount), "currency": currency})
        enqueue_event(connection, "payment.authorized", {
            "order_id": payment["paypal_order_id"],
            "authorization_id": authorization_id,
            "status": provider_status,
            "amount": str(amount),
            "currency": currency,
            "project_id": str(payment["project_id"]),
            "project_title": payment["project_title"],
            "milestone_id": str(milestone_id),
            "milestone_title": payment["milestone_title"],
            "client_id": str(payment["client_id"]),
            "freelancer_id": str(payment["freelancer_id"]),
            "recipient_email": payment["freelancer_email"],
            "recipient_name": payment["freelancer_name"] or "",
            "client_email": payment["client_email"],
            "freelancer_email": payment["freelancer_email"],
            "client_name": payment["client_name"],
            "freelancer_name": payment["freelancer_name"],
            "actor_name": payment["client_name"],
            "review_url": milestone_review_url(str(payment["project_id"]), str(milestone_id)),
        })
    return dict(row)


def begin_capture(user: dict, milestone_id: str) -> dict:
    if user["role"] != "client":
        raise DomainError(403, "Only the project client can request capture")
    with transaction() as connection:
        row = connection.execute(
            """SELECT pay.*, m.project_id, m.evidence_revision, m.status AS milestone_status,
                      m.approved_evidence_revision, m.approved_assessment_id, p.client_id
               FROM payments pay JOIN milestones m ON m.id = pay.milestone_id
               JOIN projects p ON p.id = m.project_id WHERE pay.milestone_id = %s FOR UPDATE""",
            (milestone_id,),
        ).fetchone()
        if row is None or str(row["client_id"]) != user["id"]:
            raise DomainError(404, "Payment not found")
        if row["status"] == "captured":
            return dict(row)
        if row["status"] == "capture_pending":
            raise DomainError(409, "Capture result is pending PayPal reconciliation; do not submit another capture")
        if row["status"] != "authorized":
            raise DomainError(409, "Payment must be authorized before capture")
        if row["milestone_status"] != "approved" or row["approved_evidence_revision"] != row["evidence_revision"]:
            raise DomainError(409, "A current client approval is required before capture")
        decision = connection.execute(
            """SELECT decision, evidence_revision FROM milestone_decisions
               WHERE id = (SELECT id FROM milestone_decisions WHERE milestone_id = %s ORDER BY decision_no DESC LIMIT 1)""",
            (milestone_id,),
        ).fetchone()
        report = connection.execute(
            "SELECT evidence_revision, all_met, is_stale, outcome FROM assessment_reports WHERE id = %s",
            (row["approved_assessment_id"],),
        ).fetchone()
        if decision is None or decision["decision"] != "approved" or decision["evidence_revision"] != row["evidence_revision"]:
            raise DomainError(409, "The current approval is absent or revoked")
        if report is None or report["evidence_revision"] != row["evidence_revision"] or report["is_stale"] or not report["all_met"] or report["outcome"] != "ok":
            raise DomainError(409, "A current passing assessment is required before capture")
        request_id = row["capture_request_id"] or str(uuid4())
        updated = connection.execute(
            """UPDATE payments SET status = 'capture_pending', capture_request_id = %s,
                   updated_at = NOW(), last_provider_error = NULL WHERE id = %s RETURNING *""",
            (request_id, row["id"]),
        ).fetchone()
        _audit(connection, "payment.capture_started", user, project_id=row["project_id"], milestone_id=milestone_id, payment_id=row["id"], details={"evidence_revision": row["evidence_revision"], "assessment_id": str(row["approved_assessment_id"])})
    return dict(updated)


def finish_capture(payment_id: str, data: dict, error: str | None = None) -> dict:
    capture_id = data.get("id")
    status = data.get("status")
    with transaction() as connection:
        payment = connection.execute(
            """SELECT pay.*, m.project_id, m.title AS milestone_title, p.title AS project_title,
                      p.client_id, p.freelancer_id, client.email AS client_email,
                      freelancer.email AS freelancer_email
               FROM payments pay
               JOIN milestones m ON m.id = pay.milestone_id
               JOIN projects p ON p.id = m.project_id
               JOIN users client ON client.id = p.client_id
               JOIN users freelancer ON freelancer.id = p.freelancer_id
               WHERE pay.id = %s FOR UPDATE OF pay""",
            (payment_id,),
        ).fetchone()
        if payment is None:
            raise DomainError(404, "Payment not found")
        amount_data = data.get("amount") or {}
        try:
            amount_matches = Decimal(str(amount_data.get("value"))) == payment["amount"]
        except Exception:
            amount_matches = False
        completed = (
            isinstance(capture_id, str)
            and status == "COMPLETED"
            and amount_matches
            and amount_data.get("currency_code") == payment["currency"].strip()
        )
        if status == "COMPLETED" and not completed:
            error = "PayPal reported a completed capture with an unexpected amount or currency; manual reconciliation required"
        next_status = "captured" if completed else "capture_pending"
        row = connection.execute(
            """UPDATE payments SET status = %s, paypal_capture_id = COALESCE(%s, paypal_capture_id),
                   last_provider_error = %s, updated_at = NOW() WHERE id = %s RETURNING *""",
            (next_status, capture_id if isinstance(capture_id, str) else None, error, payment_id),
        ).fetchone()
        if completed:
            connection.execute("UPDATE milestones SET status = 'paid' WHERE id = %s AND approved_evidence_revision = evidence_revision", (payment["milestone_id"],))
            _audit(connection, "payment.captured", {"role": "system", "id": None}, project_id=payment["project_id"], milestone_id=payment["milestone_id"], payment_id=payment_id, details={"capture_id": capture_id, "status": status})
            enqueue_event(
                connection,
                "payment.captured",
                {
                    "payment_id": str(payment["id"]),
                    "project_id": str(payment["project_id"]),
                    "milestone_id": str(payment["milestone_id"]),
                    "project_title": payment["project_title"],
                    "milestone_title": payment["milestone_title"],
                    "capture_id": capture_id,
                    "amount": str(payment["amount"]),
                    "currency": payment["currency"].strip(),
                    "status": "captured",
                    "client_id": str(payment["client_id"]),
                    "freelancer_id": str(payment["freelancer_id"]),
                    "client_email": payment["client_email"],
                    "freelancer_email": payment["freelancer_email"],
                    "review_url": milestone_review_url(str(payment["project_id"]), str(payment["milestone_id"])),
                },
                idempotency_key=f"{payment['id']}:{capture_id}",
            )
    return dict(row)


def find_capture_by_order(order_id: str, capture_id: str, amount: Decimal, currency: str) -> bool:
    if not capture_id:
        return False
    with transaction() as connection:
        payment = connection.execute(
            """SELECT pay.*, m.project_id, m.title AS milestone_title, p.title AS project_title,
                      p.client_id, p.freelancer_id, client.email AS client_email,
                      freelancer.email AS freelancer_email
               FROM payments pay
               JOIN milestones m ON m.id = pay.milestone_id
               JOIN projects p ON p.id = m.project_id
               JOIN users client ON client.id = p.client_id
               JOIN users freelancer ON freelancer.id = p.freelancer_id
               WHERE pay.paypal_order_id = %s FOR UPDATE OF pay""",
            (order_id,),
        ).fetchone()
        if payment is None or payment["status"] != "capture_pending":
            return False
        if payment["amount"] != amount or payment["currency"].strip() != currency:
            return False
        connection.execute("UPDATE payments SET status = 'captured', paypal_capture_id = %s, last_provider_error = NULL, updated_at = NOW() WHERE id = %s", (capture_id, payment["id"]))
        connection.execute("UPDATE milestones SET status = 'paid' WHERE id = %s AND status = 'approved' AND approved_evidence_revision = evidence_revision", (payment["milestone_id"],))
        from psycopg.types.json import Jsonb
        connection.execute(
            """INSERT INTO audit_events(project_id, milestone_id, payment_id, event_type, actor_type, details)
               VALUES (%s, %s, %s, 'payment.webhook_confirmed', 'paypal', %s)""",
            (payment["project_id"], payment["milestone_id"], payment["id"], Jsonb({"capture_id": capture_id, "order_id": order_id})),
        )
        enqueue_event(
            connection,
            "payment.captured",
            {
                "payment_id": str(payment["id"]),
                "project_id": str(payment["project_id"]),
                "milestone_id": str(payment["milestone_id"]),
                "project_title": payment["project_title"],
                "milestone_title": payment["milestone_title"],
                "capture_id": capture_id,
                "order_id": order_id,
                "amount": str(amount),
                "currency": currency,
                "status": "captured",
                "client_id": str(payment["client_id"]),
                "freelancer_id": str(payment["freelancer_id"]),
                "client_email": payment["client_email"],
                "freelancer_email": payment["freelancer_email"],
                "review_url": milestone_review_url(str(payment["project_id"]), str(payment["milestone_id"])),
            },
            idempotency_key=f"{payment['id']}:{capture_id}",
        )
    return True


def store_webhook(event: dict, verified: bool) -> bool:
    from psycopg.types.json import Jsonb

    with transaction() as connection:
        cursor = connection.execute(
            """INSERT INTO webhook_events(provider_event_id, event_type, payload, verified, processing_status)
               VALUES (%s, %s, %s, %s, 'processing')
               ON CONFLICT (provider_event_id) DO UPDATE SET processing_status = 'processing', updated_at = NOW()
               WHERE webhook_events.verified = TRUE
                 AND (webhook_events.processing_status IN ('received', 'failed')
                      OR (webhook_events.processing_status = 'processing'
                          AND webhook_events.updated_at < NOW() - INTERVAL '5 minutes'))
               RETURNING id""",
            (event["id"], event.get("event_type", "unknown"), Jsonb(event), verified),
        )
        return cursor.fetchone() is not None


def complete_webhook(event_id: str, processed: bool) -> None:
    with transaction() as connection:
        connection.execute(
            "UPDATE webhook_events SET processing_status = %s, processed_at = CASE WHEN %s THEN NOW() ELSE processed_at END, updated_at = NOW() WHERE provider_event_id = %s",
            ("processed" if processed else "failed", processed, event_id),
        )


def find_payment_by_order(user: dict, milestone_id: str) -> dict:
    return payment_for_client(user, milestone_id)


def mark_reconciled_capture(user: dict, milestone_id: str, capture: dict) -> dict:
    payment = payment_for_client(user, milestone_id)
    if payment["status"] != "capture_pending":
        raise DomainError(409, "This payment does not need reconciliation")
    details = capture.get("amount") or {}
    amount = Decimal(details.get("value", "0"))
    currency = details.get("currency_code")
    if capture.get("status") != "COMPLETED" or amount != payment["amount"] or currency != payment["currency"].strip() or not capture.get("id"):
        raise DomainError(409, "PayPal has not confirmed a completed capture for this milestone")
    return finish_capture(payment["id"], capture)
