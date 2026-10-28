from __future__ import annotations

import ipaddress
import json
from decimal import Decimal
from urllib.parse import urlsplit

import base64
import binascii
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from app.agent.orchestrator import run_assessment
from app.agent.providers.gemini_provider import GeminiProvider
from app.schemas.assessment import AssessmentInput, CriterionInput
from app.security import get_current_user, require_csrf, set_session_cookie
from app.services import storage, workflow
from app.services.email import send_project_invitation_email
from app.services.events import deliver_pending

router = APIRouter(tags=["workflow"])


class ProjectBody(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    freelancer_email: str = Field(min_length=3, max_length=254)


class MilestoneBody(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=50)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    due_at: str | None = None


class DecisionBody(BaseModel):
    decision: str
    note: str = Field(default="", max_length=2000)


class AccountBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str | None = Field(default=None, min_length=12, max_length=128)


class EvidenceBody(BaseModel):
    description: str = Field(default="", max_length=20_000)
    links: list[str] = Field(default_factory=list, max_length=20)
    file_name: str | None = Field(default=None, max_length=255)
    file_content_type: str | None = Field(default=None, max_length=100)
    file_base64: str | None = Field(default=None, max_length=14_000_000)


def _domain(callable_, *args, **kwargs):
    try:
        return callable_(*args, **kwargs)
    except workflow.DomainError as error:
        raise HTTPException(error.status_code, error.detail) from error


def _safe_links(raw: str) -> list[str]:
    try:
        links = json.loads(raw or "[]")
    except json.JSONDecodeError as error:
        raise HTTPException(422, "Links must be a JSON array") from error
    if not isinstance(links, list) or len(links) > 20 or any(not isinstance(link, str) for link in links):
        raise HTTPException(422, "Provide at most 20 reference links")
    for link in links:
        parsed = urlsplit(link)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise HTTPException(422, "Reference links must be complete HTTP or HTTPS URLs")
        host = parsed.hostname.lower()
        if host in {"localhost", "localhost.localdomain"}:
            raise HTTPException(422, "Local reference URLs are not accepted")
        try:
            if ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback or ipaddress.ip_address(host).is_link_local:
                raise HTTPException(422, "Private network reference URLs are not accepted")
        except ValueError:
            pass
    return [link.strip() for link in links]


@router.get("/projects")
def projects(user: dict = Depends(get_current_user)):
    return _domain(workflow.list_projects, user)


@router.post("/projects", status_code=201)
def create_project(body: ProjectBody, background_tasks: BackgroundTasks, user: dict = Depends(require_csrf)):
    if not body.currency.isascii() or not body.currency.isalpha() or body.currency != body.currency.upper():
        raise HTTPException(422, "Currency must be a 3-letter uppercase code")
    result = _domain(workflow.create_project, user, body.title, body.description, body.currency, body.freelancer_email.strip().lower())
    background_tasks.add_task(deliver_pending)
    background_tasks.add_task(
        send_project_invitation_email,
        body.freelancer_email.strip().lower(),
        "",
        user.get("name", ""),
        body.title.strip(),
    )
    return result


@router.get("/projects/{project_id}")
def project(project_id: str, user: dict = Depends(get_current_user)):
    return _domain(workflow.get_project, user, project_id)


@router.post("/projects/{project_id}/accept")
def accept_invitation(project_id: str, user: dict = Depends(require_csrf)):
    return _domain(workflow.accept_project, user, project_id)


@router.get("/projects/{project_id}/audit")
def audit(project_id: str, user: dict = Depends(get_current_user)):
    return _domain(workflow.audit_timeline, user, project_id)


@router.get("/activity")
def activity(limit: int = Query(default=30, ge=1, le=100), user: dict = Depends(get_current_user)):
    return _domain(workflow.activity_feed, user, limit)


@router.post("/projects/{project_id}/milestones", status_code=201)
def add_milestone(project_id: str, body: MilestoneBody, user: dict = Depends(require_csrf)):
    due_at = None
    if body.due_at:
        from datetime import datetime
        try:
            due_at = datetime.fromisoformat(body.due_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise HTTPException(422, "Deadline must be an ISO 8601 timestamp") from error
        if due_at.tzinfo is None:
            raise HTTPException(422, "Deadline must include a timezone")
    return _domain(workflow.create_milestone, user, project_id, body.title, body.acceptance_criteria, body.amount, body.currency, due_at)


@router.put("/projects/{project_id}/milestones/{milestone_id}")
def edit_milestone(project_id: str, milestone_id: str, body: MilestoneBody, user: dict = Depends(require_csrf)):
    due_at = None
    if body.due_at:
        from datetime import datetime
        try:
            due_at = datetime.fromisoformat(body.due_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise HTTPException(422, "Deadline must be an ISO 8601 timestamp") from error
        if due_at.tzinfo is None:
            raise HTTPException(422, "Deadline must include a timezone")
    return _domain(workflow.update_milestone, user, project_id, milestone_id, body.title, body.acceptance_criteria, body.amount, body.currency, due_at)


@router.get("/milestones/{milestone_id}")
def milestone(milestone_id: str, user: dict = Depends(get_current_user)):
    return _domain(workflow.get_milestone, user, milestone_id)


@router.get("/milestones/{milestone_id}/evidence/{evidence_id}/file")
def evidence_file(milestone_id: str, evidence_id: str, user: dict = Depends(get_current_user)):
    metadata = _domain(workflow.get_evidence_file, user, milestone_id, evidence_id)
    if not metadata["file_key"] or metadata["file_data"] is None:
        raise HTTPException(404, "Evidence file not found")
    safe_name = storage.safe_filename(metadata["file_name"] or "evidence-file")
    response = Response(
        content=bytes(metadata["file_data"]),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    return response


@router.post("/milestones/{milestone_id}/evidence", status_code=201)
def submit_evidence(milestone_id: str, body: EvidenceBody, background_tasks: BackgroundTasks, user: dict = Depends(require_csrf)):
    checked_links = _safe_links(json.dumps(body.links))
    file_info = None
    if body.file_base64 is not None:
        try:
            content = base64.b64decode(body.file_base64, validate=True)
            file_info = storage.store_upload(body.file_name or "evidence-file", body.file_content_type or "", content)
        except (storage.UnsafeUpload, binascii.Error, ValueError) as error:
            raise HTTPException(422, str(error)) from error
    result = _domain(workflow.add_evidence, user, milestone_id, body.description, checked_links, file_info)
    background_tasks.add_task(deliver_pending)
    return result


@router.post("/milestones/{milestone_id}/assessments")
def assess_milestone(milestone_id: str, background_tasks: BackgroundTasks, user: dict = Depends(require_csrf)):
    milestone, evidence = _domain(workflow.evidence_snapshot, user, milestone_id)
    try:
        provider = GeminiProvider()
    except RuntimeError as error:
        raise HTTPException(503, "Assessment provider is not configured") from error
    criteria = [CriterionInput(id=index, text=text) for index, text in enumerate(milestone["acceptance_criteria"], 1)]
    inp = AssessmentInput(
        milestone_id=str(milestone["id"]),
        evidence_revision=evidence["evidence_revision"],
        criteria=criteria,
        evidence_text=evidence["evidence_text"],
        evidence_links=evidence.get("evidence_links") or [],
    )
    result = run_assessment(inp, provider).model_dump(mode="json")
    saved = _domain(workflow.persist_assessment, user, milestone, evidence, result, "trustflow-report-v1")
    background_tasks.add_task(deliver_pending)
    return saved


@router.post("/milestones/{milestone_id}/decision")
def milestone_decision(milestone_id: str, body: DecisionBody, background_tasks: BackgroundTasks, user: dict = Depends(require_csrf)):
    result = _domain(workflow.decide_milestone, user, milestone_id, body.decision, body.note)
    background_tasks.add_task(deliver_pending)
    return result


@router.patch("/auth/me")
def account_settings(body: AccountBody, request: Request, response: Response, user: dict = Depends(require_csrf)):
    if not body.name.strip():
        raise HTTPException(422, "Name cannot be blank")
    from app.services.auth import change_account
    try:
        updated, token, csrf = change_account(user, body.name.strip(), body.current_password, body.new_password, request.cookies.get("trustflow_session"))
    except ValueError as error:
        raise HTTPException(403, "Current password is incorrect") from error
    set_session_cookie(response, token)
    return {"user": updated, "csrf_token": csrf}
