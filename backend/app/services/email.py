from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from urllib.parse import quote
from app.observability import log_event
from app.services import auth


class EmailDeliveryError(RuntimeError):
    pass


def email_delivery_configured() -> bool:
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM_EMAIL", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    return bool(host and sender and (not username or password))


def _send(to_address: str, subject: str, body: str) -> None:
    if not email_delivery_configured():
        raise EmailDeliveryError("Email delivery is not configured")

    try:
        message = EmailMessage()
        _, sender_address = parseaddr(os.environ["SMTP_FROM_EMAIL"].strip())
        if not sender_address:
            raise ValueError("SMTP_FROM_EMAIL must contain a valid email address")
        sender_name = os.getenv("SMTP_FROM_NAME", "TrustFlow").strip() or "TrustFlow"
        message["From"] = formataddr((sender_name, sender_address))
        message["To"] = to_address
        message["Subject"] = " ".join(subject.splitlines())[:180]
        message.set_content(body)

        host = os.environ["SMTP_HOST"].strip()
        port = int(os.getenv("SMTP_PORT", "587"))
        username = os.getenv("SMTP_USERNAME", "").strip()
        password = os.getenv("SMTP_PASSWORD", "")
        context = ssl.create_default_context()
        if os.getenv("SMTP_USE_SSL", "false").lower() == "true":
            with smtplib.SMTP_SSL(host, port, timeout=10, context=context) as client:
                if username:
                    client.login(username, password)
                client.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=10) as client:
                client.ehlo()
                if os.getenv("SMTP_USE_STARTTLS", "true").lower() == "true":
                    client.starttls(context=context)
                    client.ehlo()
                if username:
                    client.login(username, password)
                client.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError) as error:
        log_event("error", "email.delivery.failed", error=type(error).__name__)
        raise EmailDeliveryError("The email provider did not accept the message") from None


def _frontend_url() -> str:
    configured = os.getenv("TRUSTFLOW_FRONTEND_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    vercel_host = os.getenv("VERCEL_PROJECT_PRODUCTION_URL") or os.getenv("VERCEL_URL")
    if vercel_host:
        return f"https://{vercel_host.rstrip('/')}"
    return "http://localhost:5173"


def _mark_token_email_sent(mark_sent, token: str, event_name: str) -> None:
    try:
        mark_sent(token)
    except Exception as error:
        log_event("warning", event_name, error=type(error).__name__)


def send_verification_email(email: str, name: str, token: str) -> bool:
    if not email_delivery_configured():
        raise EmailDeliveryError("SMTP email delivery is not configured")
    link = f"{_frontend_url()}/verify-email#{quote(token, safe='')}"
    body = (
        f"Hi {name or 'there'},\n\n"
        "Confirm your TrustFlow email address to activate your account:\n"
        f"{link}\n\n"
        "This link expires in 24 hours. If you did not create this account, you can ignore this email.\n"
    )
    _send(email, "Confirm your TrustFlow email", body)
    _mark_token_email_sent(auth.mark_verification_email_sent, token, "email.verification.sent_at_failed")
    return True


def send_password_reset_email(email: str, name: str, token: str) -> bool:
    link = f"{_frontend_url()}/reset-password#{quote(token, safe='')}"
    body = (
        f"Hi {name or 'there'},\n\n"
        "Use this link to choose a new password for your TrustFlow account:\n"
        f"{link}\n\n"
        "This link expires in 30 minutes and can be used once. If you did not request a reset, you can ignore this email.\n"
    )
    _send(email, "Reset your TrustFlow password", body)
    _mark_token_email_sent(auth.mark_password_reset_email_sent, token, "email.password_reset.sent_at_failed")
    return True


_WORKFLOW_EMAILS = {
    "project.invited": ("You’re invited to TrustFlow", "invitation"),
    "project.invitation_resent": ("Your TrustFlow invitation is still waiting", "invitation_resent"),
    "project.invitation_cancelled": ("A TrustFlow project invitation was cancelled", "invitation_cancelled"),
    "project.invitation_accepted": ("Your TrustFlow invitation was accepted", "invitation_accepted"),
    "project.invitation_declined": ("A TrustFlow project invitation was declined", "invitation_declined"),
    "milestone.created": ("New milestone terms to review", "milestone_created"),
    "milestone.updated": ("Milestone terms were updated", "milestone_updated"),
    "milestone.agreement_accepted": ("Milestone terms accepted", "agreement_accepted"),
    "milestone.agreement_changes_requested": ("Changes requested to milestone terms", "agreement_changes_requested"),
    "evidence.submitted": ("New milestone evidence to review", "evidence_submitted"),
    "assessment.completed": ("Milestone review is ready", "assessment_completed"),
    "assessment.failed": ("Milestone review could not be prepared", "assessment_failed"),
    "revision.requested": ("A milestone revision was requested", "revision_requested"),
    "milestone.approved": ("Your milestone was approved", "milestone_approved"),
    "milestone.revoked": ("A milestone approval was withdrawn", "milestone_revoked"),
    "payment.authorized": ("PayPal authorized a milestone payment", "payment_authorized"),
    "payment.captured": ("Milestone payment completed", "payment_captured"),
    "PAYMENT.CAPTURE.REFUNDED": ("PayPal confirmed a milestone refund", "payment_refunded"),
}


def is_workflow_email_event(event: str) -> bool:
    return event in _WORKFLOW_EMAILS


def send_workflow_email(event: str, data: dict) -> bool:
    """Send a TrustFlow-written notification for a persisted workflow event."""
    definition = _WORKFLOW_EMAILS.get(event)
    if definition is None:
        return False
    subject, kind = definition
    if event == "payment.captured" and (data.get("client_email") or data.get("freelancer_email")):
        recipients = [
            (str(data[email_key]).strip(), data.get(name_key) or "there")
            for email_key, name_key in (("client_email", "client_name"), ("freelancer_email", "freelancer_name"))
            if isinstance(data.get(email_key), str) and data[email_key].strip()
        ]
    elif data.get("recipient_emails"):
        recipients = [(str(address).strip(), "there") for address in data["recipient_emails"] if isinstance(address, str) and address.strip()]
    elif data.get("recipient_email"):
        recipients = [(str(data["recipient_email"]).strip(), data.get("recipient_name") or data.get("display_name") or "there")]
    else:
        recipients = [
            (str(data[email_key]).strip(), data.get(name_key) or "there")
            for email_key, name_key in (("client_email", "client_name"), ("freelancer_email", "freelancer_name"))
            if isinstance(data.get(email_key), str) and data[email_key].strip()
        ]
    if not recipients:
        raise EmailDeliveryError(f"No recipient is configured for {event}")

    project = data.get("project_title") or data.get("project_name") or "your project"
    milestone = data.get("milestone_title") or "the milestone"
    actor = data.get("actor_name") or data.get("client_name") or data.get("freelancer_name") or "Your collaborator"
    action_url = data.get("review_url") or data.get("workspace_url")
    amount = data.get("amount")
    currency = data.get("currency")
    amount_line = f"Agreed amount: {currency} {amount}" if amount is not None and currency else None
    messages = {
        "invitation": f"{actor} invited you to collaborate on “{project}”. Sign in or create your freelancer account to review the scope and respond to the invitation.",
        "invitation_resent": f"{actor} is waiting for your response to the invitation for “{project}”. Sign in to review it when you’re ready.",
        "invitation_cancelled": f"{actor} cancelled the invitation to “{project}”. No action is needed.",
        "invitation_accepted": f"{data.get('freelancer_name') or actor} accepted the invitation to “{project}”. You can now agree on the project milestones together.",
        "invitation_declined": f"{data.get('freelancer_name') or actor} declined the invitation to “{project}”. You can review the project in your workspace.",
        "milestone_created": f"{actor} proposed “{milestone}” for “{project}”. Review the criteria and accept the terms or request a change before work begins.",
        "milestone_updated": f"{actor} updated the terms for “{milestone}” in “{project}”. Please review the latest criteria and amount.",
        "agreement_accepted": f"{data.get('freelancer_name') or actor} accepted the terms for “{milestone}” in “{project}”. Evidence submission can now begin.",
        "agreement_changes_requested": f"{data.get('freelancer_name') or actor} requested a change to “{milestone}” in “{project}”. Review their note and update the terms if needed.",
        "evidence_submitted": f"{data.get('freelancer_name') or actor} submitted revision {data.get('evidence_revision', '')} for “{milestone}” in “{project}”. Review the evidence and decide on the next step.",
        "assessment_completed": f"The advisory review for revision {data.get('evidence_revision', '')} of “{milestone}” in “{project}” is ready. It supports your review but does not make the approval decision.",
        "assessment_failed": f"TrustFlow could not prepare an advisory review for “{milestone}” in “{project}”. Your milestone and evidence are unchanged; you can retry the review from the workspace.",
        "revision_requested": f"{actor} requested a revision for “{milestone}” in “{project}”. Review the feedback and submit an updated revision.",
        "milestone_approved": f"{actor} approved “{milestone}” in “{project}”. The client can now continue with the payment step.",
        "milestone_revoked": f"{actor} withdrew approval for “{milestone}” in “{project}”. Sign in to review the latest status.",
        "payment_authorized": f"The client authorized {currency} {amount} for “{milestone}” in “{project}”. PayPal has not captured the payment yet; capture happens after the milestone is approved.",
        "payment_captured": f"PayPal confirmed the payment for “{milestone}” in “{project}”. The captured amount is {currency} {amount}.",
        "payment_refunded": f"PayPal confirmed a refund of {data.get('refund_amount', amount)} {currency} for “{milestone}” in “{project}”.",
    }
    detail_lines = [f"Project: {project}"]
    if data.get("milestone_title"):
        detail_lines.append(f"Milestone: {milestone}")
    if amount_line and kind in {"milestone_created", "milestone_updated"}:
        detail_lines.append(amount_line)
    if data.get("agreement_note"):
        detail_lines.extend(("", "Note from your collaborator:", str(data["agreement_note"])))
    if action_url:
        detail_lines.extend(("", f"Open TrustFlow: {action_url}"))
    detail_lines.extend(("", "TrustFlow keeps project terms, evidence, decisions, and payment updates together.", "If you weren’t expecting this update, you can ignore this email."))
    for recipient, recipient_name in recipients:
        body = f"TrustFlow\n\nHi {recipient_name},\n\n{messages[kind]}\n\n" + "\n".join(detail_lines) + "\n"
        _send(recipient, f"TrustFlow · {subject}", body)
    log_event("info", "email.workflow.sent", eventName=event, recipientCount=len(recipients))
    return True
