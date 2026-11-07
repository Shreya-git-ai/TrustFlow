import threading
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

from app.services import workflow


class _Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class _ApprovalDatabase:
    """Small transactional fake that serializes transactions like the row lock."""

    def __init__(self):
        self.lock = threading.Lock()
        self.milestone = {
            "id": "milestone-1",
            "project_id": "project-1",
            "project_title": "Website project",
            "title": "Homepage delivery",
            "client_id": "client-1",
            "freelancer_id": "freelancer-1",
            "membership_status": "accepted",
            "agreement_status": "accepted",
            "status": "submitted",
            "evidence_revision": 3,
            "approved_evidence_revision": None,
            "approved_assessment_id": None,
        }
        self.report = {
            "id": "report-1",
            "evidence_revision": 3,
            "outcome": "ok",
            "all_met": True,
            "is_stale": False,
        }
        self.decisions = []
        self.audit_events = []
        self.executed = []

    @contextmanager
    def transaction(self):
        with self.lock:
            yield self

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.executed.append((normalized, params))
        if "FROM milestones m JOIN projects p" in normalized:
            return _Cursor(dict(self.milestone))
        if normalized.startswith("SELECT status FROM payments"):
            return _Cursor(None)
        if normalized.startswith("SELECT id, evidence_revision, outcome, all_met, is_stale FROM assessment_reports"):
            return _Cursor(dict(self.report) if self.report else None)
        if normalized.startswith("SELECT id, decision, evidence_revision, note, created_at FROM milestone_decisions"):
            matches = [
                row for row in self.decisions
                if row["decision"] == "approved"
                and row["evidence_revision"] == params[2]
                and row["actor_id"] == params[1]
            ]
            return _Cursor(
                {key: matches[-1][key] for key in ("id", "decision", "evidence_revision", "note", "created_at")}
                if matches else None
            )
        if normalized.startswith("UPDATE milestones SET status = 'approved'"):
            self.milestone.update(
                status="approved",
                approved_evidence_revision=params[0],
                approved_assessment_id=params[1],
            )
            return _Cursor(None)
        if normalized.startswith("INSERT INTO milestone_decisions"):
            row = {
                "id": f"decision-{len(self.decisions) + 1}",
                "milestone_id": params[0],
                "actor_id": params[1],
                "decision": params[2],
                "evidence_revision": params[3],
                "assessment_report_id": params[4],
                "note": params[5],
                "created_at": datetime.now(timezone.utc),
            }
            self.decisions.append(row)
            return _Cursor({key: row[key] for key in ("id", "decision", "evidence_revision", "note", "created_at")})
        if normalized.startswith("INSERT INTO audit_events"):
            self.audit_events.append(params)
        return _Cursor(None)


class WorkflowApprovalIdempotencyTests(unittest.TestCase):
    def setUp(self):
        self.database = _ApprovalDatabase()
        self.user = {"id": "client-1", "role": "client"}
        self.events = []

    def _patched_transaction(self):
        @contextmanager
        def transaction():
            with self.database.transaction() as connection:
                yield connection

        return transaction

    def _approve(self, note="approval note"):
        with patch("app.services.workflow.transaction", self._patched_transaction()), patch(
            "app.services.workflow.enqueue_event",
            side_effect=lambda _connection, name, data, **kwargs: self.events.append((name, data, kwargs)),
        ):
            return workflow.decide_milestone(self.user, "milestone-1", "approved", note)

    def test_first_approval_writes_one_decision_and_audit(self):
        result = self._approve()

        self.assertEqual(result["id"], "decision-1")
        self.assertEqual(len(self.database.decisions), 1)
        self.assertEqual(len(self.database.audit_events), 1)
        self.assertEqual([event[0] for event in self.events], ["milestone.approved"])
        milestone_query = next(sql for sql, _ in self.database.executed if "FROM milestones m JOIN projects p" in sql)
        self.assertIn("FOR UPDATE OF m", milestone_query)

    def test_repeat_approval_returns_same_decision_without_side_effects(self):
        first = self._approve()
        second = self._approve("a retry with a different note")

        self.assertEqual(second, first)
        self.assertEqual(len(self.database.decisions), 1)
        self.assertEqual(len(self.database.audit_events), 1)
        self.assertEqual(len(self.events), 1)

    def test_new_evidence_revision_requires_a_current_assessment(self):
        self._approve()
        self.database.milestone.update(
            evidence_revision=4,
            status="submitted",
            approved_evidence_revision=None,
            approved_assessment_id=None,
        )

        with self.assertRaises(workflow.DomainError) as error:
            self._approve()

        self.assertEqual(error.exception.status_code, 409)
        self.assertIn("current successful assessment", error.exception.detail)
        self.assertEqual(len(self.database.decisions), 1)
        self.assertEqual(len(self.database.audit_events), 1)

    def test_concurrent_double_approval_creates_only_one_decision(self):
        barrier = threading.Barrier(2)
        results = []
        errors = []

        def approve():
            try:
                barrier.wait()
                results.append(self._approve())
            except Exception as error:  # surfaced in the main test thread
                errors.append(error)

        threads = [threading.Thread(target=approve) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.database.decisions), 1)
        self.assertEqual(len(self.database.audit_events), 1)
        self.assertEqual(len(self.events), 1)


if __name__ == "__main__":
    unittest.main()
