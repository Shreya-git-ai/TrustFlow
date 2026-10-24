import unittest
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import patch

from app.services import payments, workflow


class _Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class _CaptureConnection:
    def __init__(self, payment, decision=None, report=None):
        self.payment = payment
        self.decision = decision
        self.report = report
        self.updated = False

    def execute(self, sql, params=()):
        if "SELECT pay.*" in sql:
            return _Cursor(self.payment)
        if "SELECT decision, evidence_revision" in sql:
            return _Cursor(self.decision)
        if "SELECT evidence_revision, all_met" in sql:
            return _Cursor(self.report)
        if "UPDATE payments SET status = 'capture_pending'" in sql:
            self.updated = True
            updated = dict(self.payment)
            updated.update(status="capture_pending", capture_request_id=params[0])
            return _Cursor(updated)
        return _Cursor(None)


class WorkflowSafetyTests(unittest.TestCase):
    def test_freelancer_cannot_create_projects_or_decide_or_capture(self):
        freelancer = {"id": "freelancer-1", "role": "freelancer"}
        for call in (
            lambda: workflow.create_project(freelancer, "title", "", "USD", "f@example.test"),
            lambda: workflow.decide_milestone(freelancer, "m1", "approved"),
            lambda: payments.begin_capture(freelancer, "m1"),
        ):
            with self.assertRaises(workflow.DomainError) as error:
                call()
            self.assertEqual(error.exception.status_code, 403)

    def test_missing_client_owned_project_is_not_found(self):
        class Connection:
            def execute(self, sql, params):
                self.assert_owner_filter = "client_id = %s OR freelancer_id = %s" in sql
                self.params = params
                return _Cursor(None)

        connection = Connection()

        @contextmanager
        def read():
            yield connection

        with patch("app.services.workflow.read_connection", read):
            with self.assertRaises(workflow.DomainError) as error:
                workflow.get_project({"id": "other-user", "role": "client"}, "foreign-project")
        self.assertEqual(error.exception.status_code, 404)
        self.assertTrue(connection.assert_owner_filter)
        self.assertEqual(connection.params, ("foreign-project", "other-user", "other-user"))

    def test_capture_rejects_missing_or_stale_approval_without_provider_call(self):
        base = {
            "id": "pay-1", "milestone_id": "m-1", "project_id": "p-1", "client_id": "client-1",
            "status": "authorized", "evidence_revision": 3, "milestone_status": "submitted",
            "approved_evidence_revision": None, "approved_assessment_id": None,
        }
        connection = _CaptureConnection(base)

        @contextmanager
        def tx():
            yield connection

        with patch("app.services.payments.transaction", tx):
            with self.assertRaises(workflow.DomainError) as error:
                payments.begin_capture({"id": "client-1", "role": "client"}, "m-1")
        self.assertEqual(error.exception.status_code, 409)
        self.assertFalse(connection.updated)

    def test_webhook_capture_without_provider_id_is_ignored(self):
        with patch("app.services.payments.transaction", side_effect=AssertionError("must not query without capture id")):
            self.assertFalse(payments.find_capture_by_order("ORDER123", "", Decimal("10.00"), "USD"))

    def test_capture_requires_latest_decision_and_current_passing_report(self):
        payment = {
            "id": "pay-1", "milestone_id": "m-1", "project_id": "p-1", "client_id": "client-1",
            "status": "authorized", "evidence_revision": 3, "milestone_status": "approved",
            "approved_evidence_revision": 3, "approved_assessment_id": "report-1",
        }
        connection = _CaptureConnection(payment, {"decision": "approved", "evidence_revision": 3},
                                        {"evidence_revision": 2, "all_met": True, "is_stale": True, "outcome": "ok"})

        @contextmanager
        def tx():
            yield connection

        with patch("app.services.payments.transaction", tx):
            with self.assertRaises(workflow.DomainError) as error:
                payments.begin_capture({"id": "client-1", "role": "client"}, "m-1")
        self.assertIn("current passing assessment", error.exception.detail)
        self.assertFalse(connection.updated)


if __name__ == "__main__":
    unittest.main()
