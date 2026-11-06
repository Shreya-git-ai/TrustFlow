from __future__ import annotations

from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.observability import log_event
from app.payments.paypal import PayPalClient
from app.security import get_current_user, require_csrf
from app.services import payments, refunds, workflow
from app.services.events import deliver_pending

router = APIRouter(tags=["payments"])


def _domain(callable_, *args, **kwargs):
    try:
        return callable_(*args, **kwargs)
    except workflow.DomainError as error:
        raise HTTPException(error.status_code, error.detail) from error


def _approval_url(data: dict) -> str | None:
    for item in data.get("links", []) or []:
        if not isinstance(item, dict) or item.get("rel") != "approve":
            continue
        value = item.get("href")
        parsed = urlsplit(value or "")
        if parsed.scheme == "https" and parsed.hostname and (parsed.hostname == "paypal.com" or parsed.hostname.endswith(".paypal.com")):
            return value
    return None


def _refund_capture_id(resource: dict) -> str | None:
    related = (resource.get("supplementary_data") or {}).get("related_ids") or {}
    capture_id = related.get("capture_id")
    if isinstance(capture_id, str) and capture_id:
        return capture_id
    for link in resource.get("links", []) or []:
        if not isinstance(link, dict) or link.get("rel") != "up":
            continue
        path = urlsplit(link.get("href") or "").path.rstrip("/")
        parts = path.split("/")
        if len(parts) >= 2 and parts[-2] == "captures" and parts[-1]:
            return parts[-1]
    return None


@router.get("/payments")
def payment_list(user: dict = Depends(get_current_user)):
    return _domain(payments.list_for_user, user)


@router.post("/milestones/{milestone_id}/payment/order", status_code=201)
async def create_order(milestone_id: str, background_tasks: BackgroundTasks, user: dict = Depends(require_csrf)):
    payment = _domain(payments.prepare_order, user, milestone_id)
    if payment.get("paypal_order_id"):
        return {
            "payment_id": str(payment["id"]),
            "order_id": payment["paypal_order_id"],
            "approval_url": payment.get("paypal_approval_url"),
            "status": payment["status"],
        }
    paypal = PayPalClient()
    if not paypal.marketplace_configured:
        raise HTTPException(503, "PayPal direct seller payments are not configured. Marketplace partner approval and credentials are required.")
    try:
        response, data = await paypal.create_order(
            payment["amount"], payment["currency"].strip(), payment["create_request_id"],
            payee_merchant_id=payment["paypal_payee_merchant_id"],
        )
    except Exception as error:
        log_event("error", "payment.order.create.unknown", error=type(error).__name__)
        raise HTTPException(502, "PayPal order result is unknown; retry this operation to reconcile the same request") from error
    if not response.is_success:
        raise HTTPException(502, "PayPal order creation failed")
    approval = _approval_url(data)
    if not approval:
        raise HTTPException(502, "PayPal did not return a valid approval link")
    saved = _domain(payments.save_order, str(payment["id"]), data, approval)
    background_tasks.add_task(deliver_pending)
    return {"payment_id": str(saved["id"]), "order_id": saved["paypal_order_id"], "approval_url": approval, "status": saved["status"]}


@router.post("/milestones/{milestone_id}/payment/authorize")
async def authorize_order(milestone_id: str, background_tasks: BackgroundTasks, user: dict = Depends(require_csrf)):
    payment = _domain(payments.payment_for_client, user, milestone_id)
    if payment["status"] == "authorized" and payment.get("paypal_authorization_id"):
        return {"status": "authorized", "authorization_id": payment["paypal_authorization_id"]}
    if not payment.get("paypal_order_id"):
        raise HTTPException(409, "Create the PayPal order before authorizing")
    paypal = PayPalClient()
    try:
        order_response, order = await paypal.get_order(payment["paypal_order_id"], payment["paypal_payee_merchant_id"])
        if not order_response.is_success:
            raise HTTPException(502, "Could not confirm PayPal buyer approval")
        existing_auth = _extract_authorization(order)
        if existing_auth:
            data = order
            response = order_response
            auth = existing_auth
        elif order.get("status") != "APPROVED":
            raise HTTPException(409, "PayPal has not confirmed buyer approval")
        else:
            _domain(payments.set_buyer_approved, user, milestone_id)
            response, data = await paypal.authorize_order(payment["paypal_order_id"], payment["paypal_payee_merchant_id"], payment["authorize_request_id"])
            if not response.is_success:
                raise HTTPException(502, "PayPal authorization failed")
            auth = _extract_authorization(data)
    except HTTPException:
        raise
    except Exception as error:
        log_event("error", "payment.authorization.unknown", error=type(error).__name__)
        raise HTTPException(502, "PayPal authorization result is unknown; retry the same operation to reconcile") from error
    if not response.is_success or auth is None:
        raise HTTPException(502, "PayPal did not confirm an authorization")
    amount_data = auth.get("amount") or {}
    try:
        amount = Decimal(str(amount_data.get("value")))
    except InvalidOperation as error:
        raise HTTPException(502, "PayPal authorization did not include a valid amount") from error
    saved = _domain(payments.mark_authorized, user, milestone_id, auth.get("id"), amount, amount_data.get("currency_code", ""), auth.get("status", ""))
    background_tasks.add_task(deliver_pending)
    return {"status": saved["status"], "authorization_id": saved["paypal_authorization_id"]}


def _extract_authorization(data: dict) -> dict | None:
    units = data.get("purchase_units") or []
    for unit in units:
        if not isinstance(unit, dict):
            continue
        auths = (unit.get("payments") or {}).get("authorizations") or []
        for item in auths:
            if isinstance(item, dict) and item.get("id"):
                return item
    return None


@router.post("/milestones/{milestone_id}/payment/capture")
async def capture_authorization(milestone_id: str, background_tasks: BackgroundTasks, user: dict = Depends(require_csrf)):
    existing = _domain(payments.payment_for_client, user, milestone_id)
    if existing["status"] == "authorized":
        try:
            auth_response, authorization = await PayPalClient().get_authorization(existing["paypal_authorization_id"], existing["paypal_payee_merchant_id"])
        except Exception as error:
            log_event("error", "payment.authorization.check.failed", error=type(error).__name__)
            raise HTTPException(502, "Could not confirm authorization eligibility") from error
        if not auth_response.is_success or authorization.get("status") != "CREATED":
            raise HTTPException(409, "PayPal does not report an active authorization; reconcile the payment status")
        amount = authorization.get("amount") or {}
        try:
            eligible_amount = Decimal(str(amount.get("value"))) == existing["amount"]
        except InvalidOperation:
            eligible_amount = False
        expiration = authorization.get("expiration_time")
        if not isinstance(expiration, str) or not expiration:
            raise HTTPException(409, "PayPal authorization expiry could not be verified")
        try:
            expires_at = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(409, "PayPal authorization expiry could not be verified")
        if expires_at.tzinfo is None or expires_at <= datetime.now(timezone.utc):
            raise HTTPException(409, "PayPal authorization has expired")
        if not eligible_amount or amount.get("currency_code") != existing["currency"].strip():
            raise HTTPException(409, "PayPal authorization amount no longer matches the milestone")
    payment = _domain(payments.begin_capture, user, milestone_id)
    if payment["status"] == "captured":
        return {"status": "captured", "capture_id": payment.get("paypal_capture_id")}
    paypal = PayPalClient()
    try:
        response, data = await paypal.capture_authorization(
            payment["paypal_authorization_id"], payment["amount"], payment["currency"].strip(),
            payment["paypal_payee_merchant_id"], payment["capture_request_id"],
        )
    except Exception as error:
        log_event("error", "payment.capture.unknown", error=type(error).__name__)
        _domain(payments.finish_capture, str(payment["id"]), {}, "PayPal capture response was not confirmed; reconciliation required")
        return JSONResponse(status_code=202, content={"status": "capture_pending", "message": "PayPal outcome must be reconciled before another capture"})
    if not response.is_success:
        _domain(payments.finish_capture, str(payment["id"]), {}, f"PayPal returned HTTP {response.status_code}; reconciliation required")
        return JSONResponse(status_code=202, content={"status": "capture_pending", "message": "PayPal outcome must be reconciled before another capture"})
    saved = _domain(payments.finish_capture, str(payment["id"]), data)
    if saved["status"] != "captured":
        return JSONResponse(status_code=202, content={"status": "capture_pending", "message": "PayPal has not confirmed a completed capture"})
    background_tasks.add_task(deliver_pending)
    return {"status": "captured", "capture_id": saved["paypal_capture_id"]}


def _walk_captures(value):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "captures" and isinstance(child, list):
                yield from (item for item in child if isinstance(item, dict))
            else:
                yield from _walk_captures(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_captures(child)


@router.post("/milestones/{milestone_id}/payment/reconcile")
async def reconcile_capture(
    milestone_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_csrf),
):
    payment = _domain(payments.payment_for_client, user, milestone_id)
    if payment["status"] != "capture_pending" or not payment.get("paypal_order_id"):
        raise HTTPException(409, "This payment does not need reconciliation")
    response, order = await PayPalClient().get_order(payment["paypal_order_id"], payment["paypal_payee_merchant_id"])
    if not response.is_success:
        raise HTTPException(502, "Could not reconcile PayPal order")
    capture = next((item for item in _walk_captures(order) if item.get("status") == "COMPLETED"), None)
    if capture is None:
        return JSONResponse(status_code=202, content={"status": "capture_pending", "message": "PayPal has not reported a completed capture yet"})
    saved = _domain(payments.mark_reconciled_capture, user, milestone_id, capture)
    background_tasks.add_task(deliver_pending)
    return {"status": saved["status"], "capture_id": saved["paypal_capture_id"]}


@router.post("/webhooks/paypal")
async def paypal_webhook(request: Request, background_tasks: BackgroundTasks):
    if request.headers.get("content-length", "0").isdigit() and int(request.headers["content-length"]) > 1_000_000:
        raise HTTPException(413, "Webhook payload is too large")
    raw = await request.body()
    if len(raw) > 1_000_000:
        raise HTTPException(413, "Webhook payload is too large")
    try:
        event = await request.json()
    except Exception as error:
        raise HTTPException(400, "Invalid webhook payload") from error
    if not isinstance(event, dict) or not isinstance(event.get("id"), str) or not event["id"]:
        raise HTTPException(400, "Invalid PayPal event")
    headers = {key.lower(): value for key, value in request.headers.items()}
    required = ("paypal-auth-algo", "paypal-cert-url", "paypal-transmission-id", "paypal-transmission-sig", "paypal-transmission-time")
    if any(not headers.get(key) for key in required):
        raise HTTPException(400, "PayPal signature headers are missing")
    try:
        verified = await PayPalClient().verify_webhook(headers, event)
    except RuntimeError as error:
        log_event("error", "paypal.webhook.verification_unavailable", error=type(error).__name__)
        raise HTTPException(503, "Webhook verification is not configured") from error
    except Exception as error:
        log_event("error", "paypal.webhook.verification_failed", error=type(error).__name__)
        raise HTTPException(502, "PayPal webhook verification failed") from error
    if not verified:
        raise HTTPException(400, "PayPal webhook signature was not verified")
    claimed = _domain(payments.store_webhook, event, True)
    if not claimed:
        return {"received": True, "duplicate": True}
    processed = True
    try:
        if event.get("event_type") == "PAYMENT.CAPTURE.COMPLETED":
            resource = event.get("resource") or {}
            related = (resource.get("supplementary_data") or {}).get("related_ids") or {}
            order_id = related.get("order_id")
            amount_data = resource.get("amount") or {}
            try:
                processed = bool(order_id and resource.get("id") and resource.get("status") == "COMPLETED" and payments.find_capture_by_order(order_id, resource["id"], Decimal(str(amount_data.get("value"))), amount_data.get("currency_code", "")))
            except (InvalidOperation, TypeError):
                processed = False
        elif event.get("event_type") == "PAYMENT.CAPTURE.REFUNDED":
            resource = event.get("resource") or {}
            amount_data = resource.get("amount") or {}
            try:
                processed = bool(_domain(
                    refunds.record_paypal_refund,
                    _refund_capture_id(resource) or "",
                    resource.get("id") or "",
                    Decimal(str(amount_data.get("value"))),
                    amount_data.get("currency_code", ""),
                    str(resource.get("status", "COMPLETED")).upper(),
                    webhook_event_id=event["id"],
                    proposal_id=resource.get("custom_id") if isinstance(resource.get("custom_id"), str) else None,
                ))
            except (InvalidOperation, TypeError):
                processed = False
        _domain(payments.complete_webhook, event["id"], processed)
    except Exception:
        _domain(payments.complete_webhook, event["id"], False)
        raise
    background_tasks.add_task(deliver_pending)
    return {"received": True, "processed": processed}
