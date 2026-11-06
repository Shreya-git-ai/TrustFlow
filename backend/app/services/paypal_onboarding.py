from __future__ import annotations

from urllib.parse import urlsplit
from uuid import uuid4

import httpx

from app.db.repository import read_connection, transaction
from app.payments.paypal import PayPalClient
from app.services.workflow import DomainError


def _action_url(data: dict) -> str | None:
    for item in data.get("links", []) or []:
        if not isinstance(item, dict) or item.get("rel") != "action_url":
            continue
        value = item.get("href")
        parsed = urlsplit(value or "")
        if parsed.scheme == "https" and parsed.hostname and (parsed.hostname == "paypal.com" or parsed.hostname.endswith(".paypal.com")):
            return value
    return None


async def start(user: dict) -> dict:
    if user["role"] != "freelancer":
        raise DomainError(403, "Only freelancers can connect a PayPal receiving account")
    with read_connection() as connection:
        account = connection.execute(
            "SELECT email, paypal_merchant_id FROM users WHERE id = %s",
            (user["id"],),
        ).fetchone()
    if account is None:
        raise DomainError(404, "Account not found")
    if account["paypal_merchant_id"]:
        return {"connected": True}
    tracking_id = str(uuid4())
    try:
        referral = await PayPalClient().create_partner_referral(account["email"], tracking_id)
    except (RuntimeError, httpx.HTTPError) as error:
        raise DomainError(503, str(error)) from error
    action_url = _action_url(referral)
    if not action_url:
        raise DomainError(502, "PayPal did not return a valid seller onboarding link")
    with transaction() as connection:
        connection.execute(
            "UPDATE users SET paypal_onboarding_tracking_id = %s WHERE id = %s",
            (tracking_id, user["id"]),
        )
    return {"connected": False, "approval_url": action_url}


async def complete(
    user: dict,
    tracking_id: str,
    merchant_id: str,
    permissions_granted: bool,
    consent_status: bool,
) -> dict:
    if user["role"] != "freelancer":
        raise DomainError(403, "Only freelancers can connect a PayPal receiving account")
    with read_connection() as connection:
        account = connection.execute(
            "SELECT paypal_onboarding_tracking_id FROM users WHERE id = %s",
            (user["id"],),
        ).fetchone()
    if account is None or account["paypal_onboarding_tracking_id"] != tracking_id:
        raise DomainError(400, "This PayPal onboarding link is expired. Start again from account settings.")
    if not permissions_granted or not consent_status or not merchant_id:
        raise DomainError(400, "PayPal did not grant the requested seller permissions. Start onboarding again to connect your account.")
    try:
        status = await PayPalClient().get_seller_status(merchant_id)
    except (RuntimeError, httpx.HTTPError) as error:
        raise DomainError(502, "PayPal could not confirm seller permissions. Please retry the connection.") from error
    actual_merchant = status.get("merchant_id")
    if actual_merchant != merchant_id or status.get("tracking_id") != tracking_id:
        raise DomainError(400, "PayPal returned a seller account that does not match this onboarding request")
    if not status.get("payments_receivable") or not status.get("primary_email_confirmed"):
        raise DomainError(409, "PayPal requires a confirmed email and an eligible receiving account before payments can be enabled")
    scopes = {
        scope
        for integration in status.get("oauth_integrations", []) or []
        for oauth in integration.get("oauth_third_party", []) or []
        for scope in oauth.get("scopes", []) or []
    }
    if not any("authcapture" in scope for scope in scopes) or not any("refund" in scope for scope in scopes):
        raise DomainError(403, "PayPal has not granted TrustFlow payment and refund access for this seller")
    with transaction() as connection:
        updated = connection.execute(
            """UPDATE users SET paypal_merchant_id = %s, paypal_onboarding_tracking_id = NULL
               WHERE id = %s AND paypal_onboarding_tracking_id = %s RETURNING id""",
            (merchant_id, user["id"], tracking_id),
        ).fetchone()
    if updated is None:
        raise DomainError(409, "PayPal onboarding state changed. Refresh account settings and retry.")
    return {"connected": True}
