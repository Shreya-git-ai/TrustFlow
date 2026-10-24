from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from urllib.parse import quote

from app.observability import log_event


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
        message["From"] = os.environ["SMTP_FROM_EMAIL"].strip()
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


def send_verification_email(email: str, name: str, token: str) -> bool:
    link = f"{_frontend_url()}/verify-email#{quote(token, safe='')}"
    body = (
        f"Hi {name or 'there'},\n\n"
        "Confirm your TrustFlow email address to activate your account:\n"
        f"{link}\n\n"
        "This link expires in 24 hours. If you did not create this account, you can ignore this email.\n"
    )
    _send(email, "Confirm your TrustFlow email", body)
    return True


def send_project_invitation_email(email: str, recipient_name: str, client_name: str, project_title: str) -> bool:
    if not email_delivery_configured():
        return False
    body = (
        f"Hi {recipient_name or 'there'},\n\n"
        f"{client_name or 'A TrustFlow client'} invited you to join the project “{project_title}”.\n"
        "Sign in to TrustFlow to review and accept the invitation:\n"
        f"{_frontend_url()}/\n\n"
        "You can review the project before accepting.\n"
    )
    try:
        _send(email, f"TrustFlow project invitation: {project_title}", body)
        return True
    except EmailDeliveryError:
        return False
    except Exception as error:
        log_event("error", "email.invitation.failed", error=type(error).__name__)
        return False
