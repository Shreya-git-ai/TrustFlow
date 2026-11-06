from __future__ import annotations

import asyncio
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from urllib.parse import quote, urlencode
from uuid import uuid4

from app.integrations.zapier import send_event
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


def _send_auth_email_via_zapier(event: str, email: str, name: str, link: str, expires_minutes: int) -> None:
    webhook_url = os.getenv("ZAPIER_AUTH_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise EmailDeliveryError("Transactional email delivery is not configured")
    result = asyncio.run(send_event(
        event,
        {
            "recipient_email": email,
            "display_name": name or "there",
            "action_url": link,
            "expires_minutes": expires_minutes,
        },
        event_id=str(uuid4()),
        webhook_url=webhook_url,
    ))
    if not result.delivered:
        raise EmailDeliveryError("Zapier did not accept the message")


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
    if email_delivery_configured():
        body = (
            f"Hi {name or 'there'},\n\n"
            "Use this link to choose a new password for your TrustFlow account:\n"
            f"{link}\n\n"
            "This link expires in 30 minutes and can be used once. If you did not request a reset, you can ignore this email.\n"
        )
        _send(email, "Reset your TrustFlow password", body)
    else:
        _send_auth_email_via_zapier("auth.password_reset", email, name, link, 30)
    _mark_token_email_sent(auth.mark_password_reset_email_sent, token, "email.password_reset.sent_at_failed")
    return True


def send_project_invitation_email(email: str, recipient_name: str, client_name: str, project_title: str) -> bool:
    if not email_delivery_configured():
        return False
    invite_url = f"{_frontend_url()}/?{urlencode({'signup': 'freelancer', 'email': email})}"
    body = (
        f"Hi {recipient_name or 'there'},\n\n"
        f"{client_name or 'A TrustFlow client'} invited you to join the project “{project_title}”.\n"
        "Sign in to TrustFlow to review and accept the invitation:\n"
        f"{invite_url}\n\n"
        "Create or sign in to your freelancer account with this email to review the invitation.\n"
    )
    try:
        _send(email, f"TrustFlow project invitation: {project_title}", body)
        return True
    except EmailDeliveryError:
        return False
    except Exception as error:
        log_event("error", "email.invitation.failed", error=type(error).__name__)
        return False


def send_project_invitation_cancelled_email(email: str, client_name: str, project_title: str) -> bool:
    if not email_delivery_configured():
        return False
    body = (
        f"Hi there,\n\n"
        f"{client_name or 'A TrustFlow client'} cancelled the invitation to join “{project_title}”.\n"
        "You do not need to take any action for this project.\n"
    )
    try:
        _send(email, f"TrustFlow invitation cancelled: {project_title}", body)
        return True
    except EmailDeliveryError:
        return False
    except Exception as error:
        log_event("error", "email.invitation_cancelled.failed", error=type(error).__name__)
        return False
