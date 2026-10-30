import asyncio
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.integrations.zapier import DeliveryResult, send_event
from app.services import events, payments, workflow
from app.main import app


class _Cursor:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class _WorkflowConnection:
    def __init__(self, revision=3, report=None, payment=None):
        self.revision = revision
        self.report = report
        self.payment = payment
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        if "INSERT INTO evidence" in sql:
            return _Cursor({
                "id": "evidence-1",
                "milestone_id": "milestone-1",
                "evidence_revision": 3,
                "description": "secret evidence text",
                "evidence_text": "secret evidence text",
                "evidence_links": [],
                "file_name": None,
                "file_content_type": None,
                "submitted_at": datetime.now(timezone.utc),
            })
        if "SELECT evidence_revision FROM milestones" in sql:
            return _Cursor({"evidence_revision": self.revision})
        if "SELECT id FROM assessment_reports" in sql:
            return _Cursor(None)
        if "INSERT INTO assessment_reports" in sql:
            return _Cursor({"id": params[0]})
        if "SELECT status FROM payments" in sql:
            return _Cursor(self.payment)
        if "SELECT id, evidence_revision, outcome, all_met, is_stale FROM assessment_reports" in sql:
            return _Cursor(self.report)
        if "INSERT INTO milestone_decisions" in sql:
            return _Cursor({
                "id": "decision-1",
                "decision": params[2],
                "evidence_revision": params[3],
                "note": params[5],
                "created_at": datetime.now(timezone.utc),
            })
        return _Cursor(None)


class _PaymentConnection:
    def __init__(self, payment):
        self.payment = payment
        self.executed = []

    def execute(self, sql, params=()):
        self.executed.append((sql, params))
        if "SELECT pay.*" in sql:
            return _Cursor(self.payment)
        if "UPDATE payments SET status = %s, paypal_capture_id" in sql:
            updated = dict(self.payment)
            updated.update(status=params[0], paypal_capture_id=params[1])
            return _Cursor(updated)
        return _Cursor(None)


class _OutboxDatabase:
    def __init__(self, row):
        self.row = dict(row)
        self.inserts = []

    @contextmanager
    def transaction(self):
        yield self

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        if normalized.startswith("INSERT INTO integration_outbox"):
            self.inserts.append(params)
            return _Cursor(None)
        if normalized.startswith("SELECT id, event_name, dedupe_key"):
            now = params[0]
            if self.row["delivery_status"] == "pending" and self.row["next_attempt_at"] <= now:
                return _Cursor(rows=[dict(self.row)])
            return _Cursor(rows=[])
        if "SET locked_until = %s WHERE id = %s" in normalized:
            self.row["locked_until"] = params[0]
            return _Cursor(None)
        if "SET delivery_status = 'delivered'" in normalized:
            self.row.update(
                delivery_status="delivered",
                attempts=params[0],
                delivered_at=datetime.now(timezone.utc),
                locked_until=None,
                last_error=None,
            )
            return _Cursor(None)
        if "SET attempts = %s, next_attempt_at = %s" in normalized:
            self.row.update(
                attempts=params[0],
                next_attempt_at=params[1],
                locked_until=None,
                last_error=params[2],
            )
            return _Cursor(None)
        return _Cursor(None)


def _tx(connection):
    @contextmanager
    def context():
        yield connection
    return context


def _assessment_result(outcome="ok"):
    assessment = {
        "all_supported": True,
        "blockers": [],
        "verdicts": [{
            "criterion_id": 1, "verdict": "met", "quote": "secret evidence text",
            "reasoning": "private model reasoning", "missing_or_contradictory": [],
            "recommended_next_action": None, "requested_revision": None,
        }],
        "overall_summary": "Secret assessment summary",
    }
    return {
        "assessment": assessment if outcome == "ok" else None,
        "trace": {
            "outcome": outcome,
            "model": "gemini:test-model",
            "prompt_version": "assessor-v2",
            "duration_ms": 23,
            "attempts": 1,
            "error": None if outcome == "ok" else "provider failed",
        },
    }


class ZapierWorkflowEventTests(unittest.TestCase):
    def setUp(self):
        self.project_id = "project-1"
        self.milestone_id = "milestone-1"
        self.user = {"id": "freelancer-1", "role": "freelancer"}
        self.milestone = {
            "id": self.milestone_id,
            "project_id": self.project_id,
            "client_id": "client-1",
            "freelancer_id": "freelancer-1",
            "membership_status": "accepted",
            "status": "submitted",
            "evidence_revision": 2,
            "acceptance_criteria": ["Deliver the work"],
        }
        self.env = patch.dict("os.environ", {"TRUSTFLOW_FRONTEND_URL": "https://trustflow.example.test"})
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_evidence_submission_queues_one_safe_event_after_writes(self):
        connection = _WorkflowConnection()
        events_seen = []

        def enqueue(conn, name, data, **kwargs):
            self.assertTrue(any("INSERT INTO evidence" in sql for sql, _ in conn.executed))
            self.assertTrue(any("UPDATE milestones SET evidence_revision" in sql for sql, _ in conn.executed))
            events_seen.append((name, data, kwargs))

        with patch("app.services.workflow.transaction", _tx(connection)), \
             patch("app.services.workflow._milestone_for", return_value=(self.milestone, None)), \
             patch("app.services.workflow.enqueue_event", side_effect=enqueue):
            workflow.add_evidence(self.user, self.milestone_id, "secret evidence text", [], None)

        self.assertEqual(len(events_seen), 1)
        name, data, kwargs = events_seen[0]
        self.assertEqual(name, "evidence.submitted")
        self.assertEqual(data["evidence_revision"], 3)
        self.assertEqual(data["client_id"], "client-1")
        self.assertEqual(data["freelancer_id"], "freelancer-1")
        self.assertIn("project_id=project-1", data["review_url"])
        self.assertNotIn("evidence_text", data)
        self.assertNotIn("secret evidence text", repr(data))
        self.assertEqual(kwargs["idempotency_key"], "milestone-1:3")

    def test_evidence_rejection_does_not_queue_an_event(self):
        with patch("app.services.workflow.transaction", side_effect=AssertionError("must not transact")), \
             patch("app.services.workflow.enqueue_event") as enqueue:
            with self.assertRaises(workflow.DomainError):
                workflow.add_evidence({"id": "client-1", "role": "client"}, self.milestone_id, "text", [], None)
        enqueue.assert_not_called()

    def _persist_assessment(self, result):
        connection = _WorkflowConnection(revision=2)
        captured = []

        def enqueue(conn, name, data, **kwargs):
            self.assertTrue(any("INSERT INTO assessment_reports" in sql for sql, _ in conn.executed))
            if name == "assessment.completed":
                self.assertTrue(any("INSERT INTO assessment_findings" in sql for sql, _ in conn.executed))
            captured.append((name, data, kwargs))

        milestone = {**self.milestone, "evidence_revision": 2}
        evidence = {"evidence_revision": 2, "evidence_text": "secret evidence text", "file_key": None}
        with patch("app.services.workflow.transaction", _tx(connection)), \
             patch("app.services.workflow.enqueue_event", side_effect=enqueue):
            saved = workflow.persist_assessment(
                {"id": "client-1", "role": "client"}, milestone, evidence, result, "trustflow-report-v1"
            )
        return saved, captured

    def test_assessment_completion_is_queued_after_persistence_and_is_advisory(self):
        _, captured = self._persist_assessment(_assessment_result())
        self.assertEqual(len(captured), 1)
        name, data, kwargs = captured[0]
        self.assertEqual(name, "assessment.completed")
        self.assertEqual(data["overall_result"], "all_met")
        self.assertEqual(data["criterion_summary"], [{"criterion_id": 1, "result": "met"}])
        self.assertTrue(data["advisory"])
        self.assertTrue(data["client_approval_required"])
        self.assertEqual(data["client_id"], "client-1")
        self.assertNotIn("secret evidence text", repr(data))
        self.assertNotIn("secret evidence text", repr(kwargs))

    def test_failed_assessment_never_queues_assessment_completed(self):
        _, captured = self._persist_assessment(_assessment_result("provider_error"))
        self.assertEqual([name for name, _, _ in captured], ["assessment.failed"])

    def _decide(self, user, decision, report=None, client_id="client-1"):
        connection = _WorkflowConnection(report=report, payment=None)
        events_seen = []
        milestone = {**self.milestone, "client_id": client_id, "evidence_revision": 3, "status": "submitted"}
        with patch("app.services.workflow.transaction", _tx(connection)), \
             patch("app.services.workflow._milestone_for", return_value=(milestone, None)), \
             patch("app.services.workflow.enqueue_event", side_effect=lambda *args, **kwargs: events_seen.append((args, kwargs))):
            result = workflow.decide_milestone(user, self.milestone_id, decision, "private feedback")
        return result, events_seen

    def test_revision_request_event_is_created_for_authorized_client_only(self):
        report = {"id": "report-1", "evidence_revision": 3, "outcome": "ok", "all_met": False, "is_stale": False}
        _, events_seen = self._decide({"id": "client-1", "role": "client"}, "revision_requested", report)
        self.assertEqual(len(events_seen), 1)
        args, kwargs = events_seen[0]
        self.assertEqual(args[1], "revision.requested")
        self.assertEqual(args[2]["freelancer_id"], "freelancer-1")
        self.assertEqual(args[2]["client_id"], "client-1")
        self.assertEqual(args[2]["evidence_revision"], 3)
        self.assertNotIn("private feedback", repr(args[2]))
        self.assertEqual(kwargs["idempotency_key"], "milestone-1:3")

    def test_milestone_approval_event_requires_current_successful_report(self):
        report = {"id": "report-1", "evidence_revision": 3, "outcome": "ok", "all_met": True, "is_stale": False}
        _, events_seen = self._decide({"id": "client-1", "role": "client"}, "approved", report)
        self.assertEqual(len(events_seen), 1)
        args, kwargs = events_seen[0]
        self.assertEqual(args[1], "milestone.approved")
        self.assertEqual(args[2]["assessment_id"], "report-1")
        self.assertEqual(kwargs["idempotency_key"], "milestone-1:3")

    def test_invalid_approval_and_freelancer_cannot_emit_approval_event(self):
        stale_report = {"id": "report-1", "evidence_revision": 2, "outcome": "ok", "all_met": True, "is_stale": False}
        with self.assertRaises(workflow.DomainError):
            self._decide({"id": "client-1", "role": "client"}, "approved", stale_report)
        with self.assertRaises(workflow.DomainError):
            self._decide({"id": "freelancer-1", "role": "freelancer"}, "approved", stale_report)

    def test_client_cannot_decide_another_clients_milestone(self):
        report = {"id": "report-1", "evidence_revision": 3, "outcome": "ok", "all_met": True, "is_stale": False}
        with self.assertRaises(workflow.DomainError):
            self._decide({"id": "other-client", "role": "client"}, "approved", report)

    def test_confirmed_capture_event_has_only_safe_payment_metadata(self):
        payment = {
            "id": "payment-1",
            "milestone_id": self.milestone_id,
            "project_id": self.project_id,
            "client_id": "client-1",
            "freelancer_id": "freelancer-1",
            "amount": Decimal("25.00"),
            "currency": "USD ",
            "status": "capture_pending",
        }
        connection = _PaymentConnection(payment)
        captured = []
        with patch("app.services.payments.transaction", _tx(connection)), \
             patch("app.services.payments.enqueue_event", side_effect=lambda *args, **kwargs: captured.append((args, kwargs))):
            result = payments.finish_capture("payment-1", {
                "id": "capture-1", "status": "COMPLETED",
                "amount": {"value": "25.00", "currency_code": "USD"},
            })
        self.assertEqual(result["status"], "captured")
        self.assertEqual(len(captured), 1)
        args, kwargs = captured[0]
        self.assertEqual(args[1], "payment.captured")
        self.assertEqual(args[2]["payment_id"], "payment-1")
        self.assertEqual(args[2]["status"], "captured")
        self.assertEqual(args[2]["amount"], "25.00")
        self.assertEqual(args[2]["currency"], "USD")
        self.assertNotIn("access_token", repr(args[2]).lower())
        self.assertNotIn("secret", repr(args[2]).lower())
        self.assertEqual(kwargs["idempotency_key"], "payment-1:capture-1")

    def test_uncertain_or_failed_capture_does_not_emit_payment_captured(self):
        payment = {
            "id": "payment-1", "milestone_id": self.milestone_id, "project_id": self.project_id,
            "client_id": "client-1", "freelancer_id": "freelancer-1",
            "amount": Decimal("25.00"), "currency": "USD ", "status": "capture_pending",
        }
        connection = _PaymentConnection(payment)
        with patch("app.services.payments.transaction", _tx(connection)), \
             patch("app.services.payments.enqueue_event") as enqueue:
            result = payments.finish_capture("payment-1", {}, "provider outcome is uncertain")
        self.assertEqual(result["status"], "capture_pending")
        enqueue.assert_not_called()

    def test_event_idempotency_key_is_stable_across_capture_paths(self):
        connection = _OutboxDatabase({
            "id": 1, "event_name": "", "dedupe_key": None, "payload": {}, "attempts": 0,
            "created_at": datetime.now(timezone.utc), "next_attempt_at": datetime.now(timezone.utc),
            "delivery_status": "pending", "locked_until": None,
        })
        events.enqueue_event(connection, "payment.captured", {"payment_id": "p1"}, idempotency_key="p1:c1")
        events.enqueue_event(connection, "payment.captured", {"payment_id": "p1", "source": "webhook"}, idempotency_key="p1:c1")
        self.assertEqual(len(connection.inserts), 2)
        self.assertEqual(connection.inserts[0][1], connection.inserts[1][1])


class ZapierOutboxTests(unittest.IsolatedAsyncioTestCase):
    def _row(self):
        return {
            "id": 7,
            "event_name": "evidence.submitted",
            "dedupe_key": "stable-dedupe-key",
            "payload": {"project_id": "p1", "milestone_id": "m1"},
            "attempts": 0,
            "created_at": datetime(2026, 10, 30, 9, 15, tzinfo=timezone.utc),
            "next_attempt_at": datetime.now(timezone.utc) - timedelta(seconds=1),
            "delivery_status": "pending",
            "locked_until": None,
            "last_error": None,
        }

    async def test_event_is_queued_without_a_hook_and_dedupe_key_is_stable(self):
        db = _OutboxDatabase(self._row())
        with patch.dict("os.environ", {}, clear=True), patch("app.services.events.os.getenv", return_value=None):
            events.enqueue_event(db, "evidence.submitted", {"milestone_id": "m1"}, idempotency_key="m1:2")
            events.enqueue_event(db, "evidence.submitted", {"milestone_id": "m1"}, idempotency_key="m1:2")
        self.assertEqual(len(db.inserts), 2)
        self.assertEqual(db.inserts[0][1], db.inserts[1][1])

    async def test_delivery_failure_stays_pending_then_retry_marks_delivered(self):
        db = _OutboxDatabase(self._row())
        sender = AsyncMock(side_effect=[DeliveryResult(False, "HTTP 503"), DeliveryResult(True)])
        with patch.dict("os.environ", {"ZAPIER_WEBHOOK_URL": "https://hooks.example.test/hook"}), \
             patch("app.services.events.transaction", db.transaction), patch("app.services.events.send_event", sender):
            first = await events.deliver_pending()
            self.assertEqual(first, 0)
            self.assertEqual(db.row["delivery_status"], "pending")
            self.assertEqual(db.row["attempts"], 1)
            self.assertEqual(db.row["last_error"], "HTTP 503")
            self.assertGreater(db.row["next_attempt_at"], datetime.now(timezone.utc))

            # Simulate the scheduled retry running after the backoff interval.
            db.row["next_attempt_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
            second = await events.deliver_pending()

        self.assertEqual(second, 1)
        self.assertEqual(db.row["delivery_status"], "delivered")
        self.assertEqual(db.row["attempts"], 2)
        self.assertIsNone(db.row["last_error"])
        self.assertEqual(sender.await_count, 2)
        self.assertEqual(sender.await_args_list[0].kwargs["event_id"], sender.await_args_list[1].kwargs["event_id"])
        self.assertEqual(sender.await_args_list[0].kwargs["occurred_at"], sender.await_args_list[1].kwargs["occurred_at"])

    async def test_sender_envelope_has_stable_id_and_utc_timestamp(self):
        sent = {}

        class FakeClient:
            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return False

            async def post(self, url, json):
                sent["url"] = url
                sent["payload"] = json
                return SimpleNamespace(is_success=True, status_code=200)

        occurred_at = datetime(2026, 10, 30, 9, 15, tzinfo=timezone.utc)
        with patch.dict("os.environ", {"ZAPIER_WEBHOOK_URL": "https://hooks.example.test/secret-token"}), \
             patch("app.integrations.zapier.httpx.AsyncClient", FakeClient):
            result = await send_event(
                "assessment.completed", {"milestone_id": "m1", "advisory": True},
                event_id="stable-event-id", occurred_at=occurred_at,
            )
        self.assertTrue(result.delivered)
        self.assertEqual(sent["payload"]["event"], "assessment.completed")
        self.assertEqual(sent["payload"]["event_type"], "assessment.completed")
        self.assertEqual(sent["payload"]["event_id"], "stable-event-id")
        self.assertEqual(sent["payload"]["occurred_at"], "2026-10-30T09:15:00Z")
        self.assertNotIn("secret-token", repr(sent["payload"]))

    async def test_retry_is_bounded_per_delivery_attempt_and_records_safe_error(self):
        class FakeClient:
            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_):
                return False

            async def post(self, _url, json):
                return SimpleNamespace(is_success=False, status_code=503)

        with patch.dict("os.environ", {"ZAPIER_WEBHOOK_URL": "https://hooks.example.test/secret-token"}), \
             patch("app.integrations.zapier.httpx.AsyncClient", FakeClient), \
             patch("app.integrations.zapier.asyncio.sleep", new=AsyncMock()) as sleep:
            result = await send_event("payment.captured", {}, event_id="id-1")
        self.assertFalse(result.delivered)
        self.assertEqual(result.error, "Zapier returned HTTP 503")
        self.assertEqual(sleep.await_count, 2)


class PayPalWebhookEventTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.headers = {
            "paypal-auth-algo": "SHA256withRSA",
            "paypal-cert-url": "https://api-m.paypal.com/certs/test",
            "paypal-transmission-id": "transmission-1",
            "paypal-transmission-sig": "signature-placeholder",
            "paypal-transmission-time": "2026-10-30T12:00:00Z",
        }

    def test_duplicate_capture_webhook_is_processed_once(self):
        event = {
            "id": "paypal-capture-event-1",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {
                "id": "capture-1",
                "status": "COMPLETED",
                "amount": {"value": "25.00", "currency_code": "USD"},
                "supplementary_data": {"related_ids": {"order_id": "order-1"}},
            },
        }
        paypal = SimpleNamespace(verify_webhook=AsyncMock(return_value=True))
        with patch("app.routers.payments.PayPalClient", return_value=paypal), \
             patch("app.routers.payments.payments.store_webhook", side_effect=[True, False]) as store, \
             patch("app.routers.payments.payments.find_capture_by_order", return_value=True) as capture, \
             patch("app.routers.payments.payments.complete_webhook") as complete, \
             patch("app.routers.payments.deliver_pending", new_callable=AsyncMock) as deliver:
            first = self.client.post("/webhooks/paypal", json=event, headers=self.headers)
            second = self.client.post("/webhooks/paypal", json=event, headers=self.headers)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), {"received": True, "processed": True})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json(), {"received": True, "duplicate": True})
        self.assertEqual(store.call_count, 2)
        capture.assert_called_once_with("order-1", "capture-1", Decimal("25.00"), "USD")
        complete.assert_called_once_with("paypal-capture-event-1", True)
        self.assertEqual(deliver.await_count, 1)

    def test_verified_refund_webhook_still_uses_refund_service_and_outbox_worker(self):
        event = {
            "id": "paypal-refund-event-1",
            "event_type": "PAYMENT.CAPTURE.REFUNDED",
            "resource": {
                "id": "refund-1",
                "status": "COMPLETED",
                "amount": {"value": "1.00", "currency_code": "USD"},
                "custom_id": "proposal-1",
                "links": [{"rel": "up", "href": "https://api-m.paypal.com/v2/payments/captures/capture-1"}],
            },
        }
        paypal = SimpleNamespace(verify_webhook=AsyncMock(return_value=True))
        with patch("app.routers.payments.PayPalClient", return_value=paypal), \
             patch("app.routers.payments.payments.store_webhook", return_value=True), \
             patch("app.routers.payments.refunds.record_paypal_refund", return_value=True) as record, \
             patch("app.routers.payments.payments.complete_webhook") as complete, \
             patch("app.routers.payments.deliver_pending", new_callable=AsyncMock) as deliver:
            response = self.client.post("/webhooks/paypal", json=event, headers=self.headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"received": True, "processed": True})
        record.assert_called_once_with(
            "capture-1", "refund-1", Decimal("1.00"), "USD", "COMPLETED",
            webhook_event_id="paypal-refund-event-1", proposal_id="proposal-1",
        )
        complete.assert_called_once_with("paypal-refund-event-1", True)
        self.assertEqual(deliver.await_count, 1)


if __name__ == "__main__":
    unittest.main()
