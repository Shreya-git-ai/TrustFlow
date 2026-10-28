from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb

from app.db.repository import read_connection, transaction
from app.services.events import enqueue_event


class DomainError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _project_for(connection, project_id: str, user: dict) -> dict:
    row = connection.execute(
        "SELECT * FROM projects WHERE id = %s AND (client_id = %s OR freelancer_id = %s)",
        (project_id, user["id"], user["id"]),
    ).fetchone()
    if row is None:
        raise DomainError(404, "Project not found")
    return row


def _milestone_for(connection, milestone_id: str, user: dict) -> tuple[dict, dict]:
    row = connection.execute(
        """SELECT m.*, p.client_id, p.freelancer_id, p.membership_status
           FROM milestones m JOIN projects p ON p.id = m.project_id
           WHERE m.id = %s AND (p.client_id = %s OR p.freelancer_id = %s)""",
        (milestone_id, user["id"], user["id"]),
    ).fetchone()
    if row is None:
        raise DomainError(404, "Milestone not found")
    return row, row


def _audit(connection, event: str, user: dict, project_id=None, milestone_id=None, details=None, payment_id=None):
    connection.execute(
        """INSERT INTO audit_events(project_id, milestone_id, payment_id, event_type, actor_type, actor_id, details)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (project_id, milestone_id, payment_id, event, user.get("role", "system"), user.get("id"), Jsonb(details or {})),
    )


def list_projects(user: dict) -> list[dict]:
    with read_connection() as connection:
        rows = connection.execute(
            """SELECT p.*, c.display_name AS client_name, f.display_name AS freelancer_name,
                      COUNT(m.id) AS milestone_count,
                      COUNT(m.id) FILTER (WHERE m.status = 'submitted') AS submitted_count,
                      COUNT(m.id) FILTER (WHERE m.status = 'revision_requested') AS revision_count,
                      COUNT(m.id) FILTER (
                          WHERE m.status = 'submitted' AND latest_review.outcome = 'ok'
                            AND latest_review.evidence_revision = m.evidence_revision
                            AND NOT COALESCE(latest_review.is_stale, TRUE)
                      ) AS decision_due_count,
                      COUNT(m.id) FILTER (WHERE pay.status IN ('created', 'buyer_approved', 'authorized', 'capture_pending')) AS active_payment_count
               FROM projects p JOIN users c ON c.id = p.client_id JOIN users f ON f.id = p.freelancer_id
               LEFT JOIN milestones m ON m.project_id = p.id
               LEFT JOIN payments pay ON pay.milestone_id = m.id
               LEFT JOIN LATERAL (
                   SELECT a.outcome, a.evidence_revision, a.is_stale
                   FROM assessment_reports a WHERE a.milestone_id = m.id
                   ORDER BY a.created_at DESC LIMIT 1
               ) latest_review ON TRUE
               WHERE p.client_id = %s OR p.freelancer_id = %s
               GROUP BY p.id, c.display_name, f.display_name ORDER BY p.created_at DESC""",
            (user["id"], user["id"]),
        ).fetchall()
    return [dict(row) for row in rows]


def create_project(user: dict, title: str, description: str, currency: str, freelancer_email: str) -> dict:
    if user["role"] != "client":
        raise DomainError(403, "Only clients can create projects")
    with transaction() as connection:
        freelancer = connection.execute(
            "SELECT id FROM users WHERE lower(email) = lower(%s) AND role = 'freelancer'",
            (freelancer_email,),
        ).fetchone()
        if freelancer is None:
            raise DomainError(404, "Create a freelancer account before inviting them")
        if freelancer["id"] == user["id"]:
            raise DomainError(422, "A client cannot invite their own account")
        row = connection.execute(
            """INSERT INTO projects(client_id, freelancer_id, title, description, currency,
                                  status, membership_status)
               VALUES (%s, %s, %s, %s, %s, 'active', 'invited') RETURNING *""",
            (user["id"], freelancer["id"], title.strip(), description.strip() or None, currency, ),
        ).fetchone()
        connection.execute("UPDATE projects SET membership_status = 'invited', membership_accepted_at = NULL WHERE id = %s", (row["id"],))
        _audit(connection, "project.created", user, project_id=row["id"], details={"title": title.strip(), "invited_freelancer": freelancer_email})
        enqueue_event(connection, "project.created", {"project_id": str(row["id"]), "title": title.strip()})
    return dict(row)


def accept_project(user: dict, project_id: str) -> dict:
    if user["role"] != "freelancer":
        raise DomainError(403, "Only freelancers can accept project invitations")
    with transaction() as connection:
        row = connection.execute(
            """UPDATE projects SET membership_status = 'accepted', membership_accepted_at = NOW()
               WHERE id = %s AND freelancer_id = %s AND membership_status = 'invited'
               RETURNING *""",
            (project_id, user["id"]),
        ).fetchone()
        if row is None:
            raise DomainError(404, "Project invitation not found")
        _audit(connection, "project.invitation_accepted", user, project_id=row["id"])
    return dict(row)


def get_project(user: dict, project_id: str) -> dict:
    with read_connection() as connection:
        project = _project_for(connection, project_id, user)
        milestones = connection.execute(
            """SELECT m.*, (SELECT COUNT(*) FROM evidence e WHERE e.milestone_id = m.id) AS evidence_count,
                      (SELECT COUNT(*) FROM assessment_reports a WHERE a.milestone_id = m.id) AS assessment_count,
                      (SELECT status FROM payments p WHERE p.milestone_id = m.id) AS payment_status
               FROM milestones m WHERE m.project_id = %s ORDER BY m.created_at""",
            (project_id,),
        ).fetchall()
    result = dict(project)
    result["milestones"] = [dict(row) for row in milestones]
    return result


def create_milestone(user: dict, project_id: str, title: str, criteria: list[str], amount: Decimal, currency: str, due_at: datetime | None) -> dict:
    clean_criteria = [item.strip() for item in criteria]
    if not clean_criteria or any(not item or len(item) > 1000 for item in clean_criteria):
        raise DomainError(422, "Add 1 to 50 non-empty acceptance criteria (up to 1,000 characters each)")
    if len(clean_criteria) > 50 or amount <= 0 or amount.as_tuple().exponent < -2:
        raise DomainError(422, "Amount or milestone criteria are invalid")
    if currency != currency.upper() or not re.fullmatch(r"[A-Z]{3}", currency):
        raise DomainError(422, "Currency must be a 3-letter uppercase code")
    with transaction() as connection:
        project = _project_for(connection, project_id, user)
        if str(project["client_id"]) != user["id"]:
            raise DomainError(403, "Only the project client can manage milestones")
        row = connection.execute(
            """INSERT INTO milestones(project_id, title, acceptance_criteria, amount, currency, due_at, status)
               VALUES (%s, %s, %s, %s, %s, %s, 'pending') RETURNING *""",
            (project_id, title.strip(), Jsonb(clean_criteria), amount, currency, due_at),
        ).fetchone()
        _audit(connection, "milestone.created", user, project_id=project_id, milestone_id=row["id"], details={"criteria_count": len(clean_criteria), "amount": str(amount), "currency": currency})
    return dict(row)


def update_milestone(user: dict, project_id: str, milestone_id: str, title: str, criteria: list[str], amount: Decimal, currency: str, due_at: datetime | None) -> dict:
    clean_criteria = [item.strip() for item in criteria]
    if not clean_criteria or len(clean_criteria) > 50 or any(not item or len(item) > 1000 for item in clean_criteria):
        raise DomainError(422, "Add 1 to 50 non-empty acceptance criteria (up to 1,000 characters each)")
    if amount <= 0 or amount.as_tuple().exponent < -2:
        raise DomainError(422, "Amount must be positive with at most two decimal places")
    if currency != currency.upper() or not re.fullmatch(r"[A-Z]{3}", currency):
        raise DomainError(422, "Currency must be a 3-letter uppercase code")
    with transaction() as connection:
        project = _project_for(connection, project_id, user)
        if user["role"] != "client" or str(project["client_id"]) != user["id"]:
            raise DomainError(403, "Only the project client can edit milestones")
        milestone = connection.execute("SELECT * FROM milestones WHERE id = %s AND project_id = %s FOR UPDATE", (milestone_id, project_id)).fetchone()
        if milestone is None:
            raise DomainError(404, "Milestone not found")
        evidence = connection.execute("SELECT 1 FROM evidence WHERE milestone_id = %s LIMIT 1", (milestone_id,)).fetchone()
        payment = connection.execute("SELECT status FROM payments WHERE milestone_id = %s", (milestone_id,)).fetchone()
        if milestone["evidence_revision"] > 0 or evidence or payment:
            raise DomainError(409, "Milestone terms are locked after evidence or payment begins")
        row = connection.execute(
            """UPDATE milestones SET title = %s, acceptance_criteria = %s, amount = %s, currency = %s, due_at = %s
               WHERE id = %s AND project_id = %s RETURNING *""",
            (title.strip(), Jsonb(clean_criteria), amount, currency, due_at, milestone_id, project_id),
        ).fetchone()
        _audit(connection, "milestone.updated", user, project_id=project_id, milestone_id=milestone_id, details={"criteria_count": len(clean_criteria), "amount": str(amount), "currency": currency})
        enqueue_event(connection, "milestone.updated", {"project_id": str(project_id), "milestone_id": str(milestone_id)})
    return dict(row)


def add_evidence(user: dict, milestone_id: str, description: str, links: list[str], file_info: tuple[str, str, str, bytes] | None) -> dict:
    if user["role"] != "freelancer":
        raise DomainError(403, "Only the assigned freelancer can submit evidence")
    if len(description) > 20_000 or not description.strip() and not links and file_info is None:
        raise DomainError(422, "Provide evidence text, a reference link, or an attachment")
    with transaction() as connection:
        milestone, _ = _milestone_for(connection, milestone_id, user)
        if str(milestone["freelancer_id"]) != user["id"]:
            raise DomainError(403, "Only the assigned freelancer can submit evidence")
        if milestone["membership_status"] != "accepted":
            raise DomainError(403, "Accept the project invitation before submitting work")
        if milestone["status"] in {"approved", "paid"}:
            raise DomainError(409, "This milestone is already approved and cannot accept a new revision")
        revision = milestone["evidence_revision"] + 1
        file_key, file_name, file_type, file_data = file_info or (None, None, None, None)
        row = connection.execute(
            """INSERT INTO evidence(milestone_id, evidence_revision, description, evidence_text,
                                   evidence_links, file_key, file_name, file_content_type, file_data)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id, milestone_id, evidence_revision,
                             description, evidence_text, evidence_links, file_name, file_content_type, submitted_at""",
            (milestone_id, revision, description.strip(), description.strip(), Jsonb(links), file_key, file_name, file_type, file_data),
        ).fetchone()
        connection.execute(
            "UPDATE milestones SET evidence_revision = %s, status = 'submitted', approved_at = NULL, approved_evidence_revision = NULL, approved_assessment_id = NULL WHERE id = %s",
            (revision, milestone_id),
        )
        _audit(connection, "evidence.submitted", user, project_id=milestone["project_id"], milestone_id=milestone_id, details={"evidence_revision": revision, "file_attached": bool(file_key)})
        enqueue_event(connection, "evidence.submitted", {"project_id": str(milestone["project_id"]), "milestone_id": str(milestone_id), "evidence_revision": revision, "file_attached": bool(file_key)})
    return dict(row)


def get_milestone(user: dict, milestone_id: str) -> dict:
    with read_connection() as connection:
        milestone, _ = _milestone_for(connection, milestone_id, user)
        evidence_rows = connection.execute(
            """SELECT id, evidence_revision, description, evidence_links, file_key, file_name,
                      file_content_type, submitted_at FROM evidence
               WHERE milestone_id = %s ORDER BY evidence_revision DESC""",
            (milestone_id,),
        ).fetchall()
        reports = connection.execute(
            """SELECT id, evidence_revision, report_version, prompt_version, model, outcome,
                      all_met, is_stale, result_json, created_at FROM assessment_reports
               WHERE milestone_id = %s ORDER BY created_at DESC""",
            (milestone_id,),
        ).fetchall()
        decisions = connection.execute(
            "SELECT decision, evidence_revision, note, created_at FROM milestone_decisions WHERE milestone_id = %s ORDER BY created_at DESC",
            (milestone_id,),
        ).fetchall()
        payment = connection.execute(
            "SELECT amount, currency, status, paypal_order_id, paypal_approval_url, paypal_authorization_id, paypal_capture_id, created_at, updated_at FROM payments WHERE milestone_id = %s",
            (milestone_id,),
        ).fetchone()
    result = dict(milestone)
    result["evidence_history"] = [
        {**dict(row), "file_url": f"/milestones/{milestone_id}/evidence/{row['id']}/file" if row["file_key"] else None}
        for row in evidence_rows
    ]
    result["assessment_history"] = [dict(row) for row in reports]
    result["decisions"] = [dict(row) for row in decisions]
    result["payment"] = dict(payment) if payment else None
    return result


def get_evidence_file(user: dict, milestone_id: str, evidence_id: str) -> dict:
    with read_connection() as connection:
        _milestone_for(connection, milestone_id, user)
        row = connection.execute(
            """SELECT file_key, file_name, file_content_type, file_data FROM evidence
               WHERE id = %s AND milestone_id = %s""",
            (evidence_id, milestone_id),
        ).fetchone()
    if row is None or not row["file_key"]:
        raise DomainError(404, "Evidence file not found")
    return dict(row)


def evidence_snapshot(user: dict, milestone_id: str) -> tuple[dict, dict]:
    with read_connection() as connection:
        milestone, _ = _milestone_for(connection, milestone_id, user)
        if str(milestone["client_id"]) != user["id"]:
            raise DomainError(403, "Only the project client can request an assessment")
        if milestone["membership_status"] != "accepted":
            raise DomainError(409, "The freelancer has not accepted this project")
        evidence = connection.execute(
            "SELECT * FROM evidence WHERE milestone_id = %s ORDER BY evidence_revision DESC LIMIT 1",
            (milestone_id,),
        ).fetchone()
    if evidence is None:
        raise DomainError(409, "No evidence has been submitted")
    return dict(milestone), dict(evidence)


def persist_assessment(user: dict, milestone: dict, evidence: dict, result: dict, report_version: str) -> dict:
    assessment = result.get("assessment") or {}
    trace = result["trace"]
    current_revision = evidence["evidence_revision"]
    is_stale = False
    report_id = None
    with transaction() as connection:
        latest = connection.execute("SELECT evidence_revision FROM milestones WHERE id = %s FOR UPDATE", (milestone["id"],)).fetchone()
        is_stale = latest["evidence_revision"] != current_revision
        existing = connection.execute(
            "SELECT id FROM assessment_reports WHERE milestone_id = %s AND evidence_revision = %s AND report_version = %s FOR UPDATE",
            (milestone["id"], current_revision, report_version),
        ).fetchone()
        report_id = existing["id"] if existing else uuid4()
        limitations = list(assessment.get("limitations", []))
        if evidence.get("file_key"):
            message = "An attachment was stored but its contents were not extracted or inspected."
            if message not in limitations:
                limitations.append(message)
        report_metadata = {"report_id": str(report_id), "report_version": report_version, "evidence_revision": current_revision, "stale": is_stale, "limitations": limitations}
        result["report"] = report_metadata
        cursor = connection.execute(
            """INSERT INTO assessment_reports(id, milestone_id, evidence_revision, report_version,
                    prompt_version, model, outcome, all_met, is_stale, result_json)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (milestone_id, evidence_revision, report_version) DO UPDATE SET
                    prompt_version = EXCLUDED.prompt_version, model = EXCLUDED.model,
                    outcome = EXCLUDED.outcome, all_met = EXCLUDED.all_met,
                    is_stale = EXCLUDED.is_stale, result_json = EXCLUDED.result_json
               RETURNING id""",
            (report_id, milestone["id"], current_revision, report_version, trace["prompt_version"], trace["model"], trace["outcome"], bool(assessment.get("all_supported")), is_stale, Jsonb(result)),
        )
        report_id = cursor.fetchone()["id"]
        report_metadata["report_id"] = str(report_id)
        if result["report"]["report_id"] != str(report_id):
            result["report"] = report_metadata
            connection.execute("UPDATE assessment_reports SET result_json = %s WHERE id = %s", (Jsonb(result), report_id))
        connection.execute("DELETE FROM assessment_findings WHERE report_id = %s", (report_id,))
        for finding in assessment.get("verdicts", []):
            connection.execute(
                """INSERT INTO assessment_findings(report_id, criterion_id, status, explanation,
                      quote, missing_or_contradictory, recommended_next_action)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (report_id, finding["criterion_id"], finding["verdict"], finding["reasoning"], finding.get("quote"), Jsonb(finding.get("missing_or_contradictory", [])), finding.get("recommended_next_action") or finding.get("requested_revision")),
            )
        _audit(connection, "assessment.completed" if trace["outcome"] == "ok" else "assessment.failed", user, project_id=milestone["project_id"], milestone_id=milestone["id"], details={"report_id": str(report_id), "evidence_revision": current_revision, "outcome": trace["outcome"], "model": trace["model"], "prompt_version": trace["prompt_version"], "duration_ms": trace["duration_ms"], "stale": is_stale})
        enqueue_event(connection, "assessment.completed" if trace["outcome"] == "ok" else "assessment.failed", {"milestone_id": str(milestone["id"]), "evidence_revision": current_revision, "outcome": trace["outcome"], "all_met": bool(assessment.get("all_supported")), "blocker_count": len(assessment.get("blockers", [])), "stale": is_stale})
    return {"report_id": str(report_id), "evidence_revision": current_revision, "stale": is_stale, "result": result}


def decide_milestone(user: dict, milestone_id: str, decision: str, note: str = "") -> dict:
    if user["role"] != "client":
        raise DomainError(403, "Only the project client can make milestone decisions")
    with transaction() as connection:
        milestone, _ = _milestone_for(connection, milestone_id, user)
        if str(milestone["client_id"]) != user["id"]:
            raise DomainError(403, "Only the project client can make milestone decisions")
        payment = connection.execute("SELECT status FROM payments WHERE milestone_id = %s FOR UPDATE", (milestone_id,)).fetchone()
        latest = connection.execute(
            """SELECT id, evidence_revision, outcome, all_met, is_stale FROM assessment_reports
               WHERE milestone_id = %s ORDER BY created_at DESC LIMIT 1 FOR UPDATE""",
            (milestone_id,),
        ).fetchone()
        if decision == "approved":
            if latest is None or latest["evidence_revision"] != milestone["evidence_revision"] or latest["is_stale"] or latest["outcome"] != "ok":
                raise DomainError(409, "A current successful assessment is required before approval")
            if not latest["all_met"]:
                raise DomainError(409, "All criteria must be met before this milestone can be approved")
            if payment and payment["status"] in {"capture_pending", "captured"}:
                raise DomainError(409, "Payment capture has started; approval cannot be changed")
            connection.execute("UPDATE milestones SET status = 'approved', approved_at = NOW(), approved_evidence_revision = %s, approved_assessment_id = %s WHERE id = %s", (milestone["evidence_revision"], latest["id"], milestone_id))
        elif decision == "revision_requested":
            if latest is None or latest["evidence_revision"] != milestone["evidence_revision"] or latest["outcome"] != "ok" or latest["is_stale"]:
                raise DomainError(409, "A current successful assessment is required before requesting a revision")
            if payment and payment["status"] in {"capture_pending", "captured"}:
                raise DomainError(409, "Payment capture has started; revisions are closed")
            connection.execute("UPDATE milestones SET status = 'revision_requested', approved_at = NULL, approved_evidence_revision = NULL, approved_assessment_id = NULL WHERE id = %s", (milestone_id,))
        elif decision == "revoked":
            if milestone["status"] != "approved" or payment and payment["status"] in {"capture_pending", "captured"}:
                raise DomainError(409, "Approval cannot be revoked after payment capture begins")
            connection.execute("UPDATE milestones SET status = 'submitted', approved_at = NULL, approved_evidence_revision = NULL, approved_assessment_id = NULL WHERE id = %s", (milestone_id,))
        else:
            raise DomainError(422, "Unsupported milestone decision")
        cursor = connection.execute(
            """INSERT INTO milestone_decisions(milestone_id, actor_id, decision, evidence_revision, assessment_report_id, note)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, decision, evidence_revision, note, created_at""",
            (milestone_id, user["id"], decision, milestone["evidence_revision"], latest["id"] if latest else None, note[:2000]),
        )
        row = cursor.fetchone()
        _audit(connection, f"milestone.{decision}", user, project_id=milestone["project_id"], milestone_id=milestone_id, details={"evidence_revision": milestone["evidence_revision"], "assessment_report_id": str(latest["id"]) if latest else None})
        enqueue_event(connection, f"milestone.{decision}", {"milestone_id": str(milestone_id), "evidence_revision": milestone["evidence_revision"]})
    return dict(row)


def audit_timeline(user: dict, project_id: str) -> list[dict]:
    with read_connection() as connection:
        project = _project_for(connection, project_id, user)
        rows = connection.execute(
            """SELECT event_type, actor_type, details, created_at FROM audit_events
               WHERE project_id = %s ORDER BY created_at DESC LIMIT 200""",
            (project["id"],),
        ).fetchall()
    return [dict(row) for row in rows]


def activity_feed(user: dict, limit: int = 30) -> list[dict]:
    with read_connection() as connection:
        rows = connection.execute(
            """SELECT a.event_type, a.actor_type, a.details, a.created_at,
                      a.project_id, p.title AS project_title,
                      a.milestone_id, m.title AS milestone_title
               FROM audit_events AS a
               JOIN projects AS p ON p.id = a.project_id
               LEFT JOIN milestones AS m ON m.id = a.milestone_id
               WHERE p.client_id = %s OR p.freelancer_id = %s
               ORDER BY a.created_at DESC, a.id DESC
               LIMIT %s""",
            (user["id"], user["id"], limit),
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["project_id"] = str(item["project_id"])
        item["milestone_id"] = str(item["milestone_id"]) if item["milestone_id"] else None
        result.append(item)
    return result
