from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse

from app.integrations.zapier import send_event
from app.payments.paypal import PayPalClient, log_paypal_failure
from app.schemas.payments import (
    AuthorizeOrderRequest,
    CaptureAuthorizationRequest,
    CreateOrderRequest,
    InvalidPaymentRequest,
)

router = APIRouter()


def get_paypal_client() -> PayPalClient:
    return PayPalClient()


async def _request_body(request: Request) -> tuple[Any, bool]:
    content_type = (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    )
    if content_type != "application/json" and not content_type.endswith("+json"):
        return {}, True
    try:
        raw_body = await request.body()
        if not raw_body.strip():
            return {}, True
        if len(raw_body) > 32 * 1024:
            return None, False
        payload = json.loads(raw_body)
        if not isinstance(payload, (dict, list)):
            return None, False
        return payload, True
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, False


def _invalid_request(error: InvalidPaymentRequest) -> JSONResponse:
    if str(error) == "Milestone approval is required before capture":
        return JSONResponse(status_code=403, content={"error": str(error)})
    return JSONResponse(status_code=400, content={"error": str(error)})


@router.get("/paypal/test-auth")
async def test_paypal_auth(
    paypal: PayPalClient = Depends(get_paypal_client),
) -> JSONResponse:
    try:
        await paypal.test_auth()
        return JSONResponse(
            content={"success": True, "message": "Authenticated with PayPal"}
        )
    except Exception as error:
        log_paypal_failure("paypal.auth.failed", error)
        return JSONResponse(
            status_code=502,
            content={"success": False, "error": "PayPal authentication failed"},
        )


@router.post("/paypal/create-order")
async def create_order(
    request: Request,
    background_tasks: BackgroundTasks,
    paypal: PayPalClient = Depends(get_paypal_client),
) -> JSONResponse:
    try:
        payload, valid_json = await _request_body(request)
        if not valid_json:
            return JSONResponse(status_code=400, content={"error": "Invalid request"})
        payment = CreateOrderRequest.from_payload(payload)
    except InvalidPaymentRequest as error:
        return _invalid_request(error)
    try:
        response, data = await paypal.create_order(payment.amount, payment.currency)
        if not response.is_success:
            return JSONResponse(
                status_code=502,
                content={
                    "error": "PayPal order creation failed",
                    "paypalStatus": response.status_code,
                },
            )
        links = data.get("links") or []
        approval_url = next(
            (
                link.get("href")
                for link in links
                if isinstance(link, dict) and link.get("rel") == "approve"
            ),
            None,
        )
        response_body: dict[str, Any] = {
            "message": "PayPal order created",
            "approvalUrl": approval_url,
        }
        if "id" in data:
            response_body["orderId"] = data["id"]
        if "status" in data:
            response_body["status"] = data["status"]
        background_tasks.add_task(
            send_event,
            "payment.order_created",
            {
                "order_id": data.get("id"),
                "status": data.get("status"),
                "amount": str(payment.amount),
                "currency": payment.currency,
            },
        )
        return JSONResponse(
            status_code=201,
            content=response_body,
        )
    except Exception as error:
        log_paypal_failure("paypal.order.create.failed", error)
        return JSONResponse(
            status_code=502, content={"error": "Could not create PayPal order"}
        )


@router.post("/paypal/authorize-order")
async def authorize_order(
    request: Request,
    background_tasks: BackgroundTasks,
    paypal: PayPalClient = Depends(get_paypal_client),
) -> JSONResponse:
    try:
        payload, valid_json = await _request_body(request)
        if not valid_json:
            return JSONResponse(status_code=400, content={"error": "Invalid request"})
        payment = AuthorizeOrderRequest.from_payload(payload)
    except InvalidPaymentRequest as error:
        return _invalid_request(error)
    try:
        response, data = await paypal.authorize_order(payment.order_id)
        if not response.is_success:
            return JSONResponse(
                status_code=502,
                content={
                    "error": "PayPal authorization failed",
                    "paypalStatus": response.status_code,
                },
            )
        purchase_units = data.get("purchase_units") or []
        first_unit = (
            purchase_units[0]
            if purchase_units and isinstance(purchase_units[0], dict)
            else {}
        )
        payments = first_unit.get("payments") or {}
        authorizations = payments.get("authorizations") or []
        authorization = (
            authorizations[0]
            if authorizations and isinstance(authorizations[0], dict)
            else {}
        )
        response_body: dict[str, Any] = {
            "message": "PayPal authorization response received",
            "authorizationId": authorization.get("id"),
            "authorizationStatus": authorization.get("status"),
            "amount": authorization.get("amount"),
        }
        if "id" in data:
            response_body["orderId"] = data["id"]
        if "status" in data:
            response_body["orderStatus"] = data["status"]
        background_tasks.add_task(
            send_event,
            "payment.authorized",
            {
                "order_id": data.get("id", payment.order_id),
                "authorization_id": authorization.get("id"),
                "status": authorization.get("status"),
                "amount": authorization.get("amount"),
            },
        )
        return JSONResponse(content=response_body)
    except Exception as error:
        log_paypal_failure("paypal.order.authorize.failed", error)
        return JSONResponse(
            status_code=502, content={"error": "Could not authorize PayPal order"}
        )


@router.post("/paypal/capture-authorization")
async def capture_authorization(
    request: Request,
    background_tasks: BackgroundTasks,
    paypal: PayPalClient = Depends(get_paypal_client),
) -> JSONResponse:
    try:
        payload, valid_json = await _request_body(request)
        if not valid_json:
            return JSONResponse(status_code=400, content={"error": "Invalid request"})
        payment = CaptureAuthorizationRequest.from_payload(payload)
    except InvalidPaymentRequest as error:
        return _invalid_request(error)
    try:
        response, data = await paypal.capture_authorization(
            payment.authorization_id, payment.amount, payment.currency
        )
        if not response.is_success:
            return JSONResponse(
                status_code=502,
                content={
                    "error": "PayPal capture failed",
                    "paypalStatus": response.status_code,
                },
            )
        response_body: dict[str, Any] = {"message": "PayPal capture response received"}
        response_keys = {"id": "captureId", "status": "status", "amount": "amount"}
        for key in ("id", "status", "amount"):
            if key in data:
                response_body[response_keys[key]] = data[key]
        background_tasks.add_task(
            send_event,
            "payment.captured",
            {
                "capture_id": data.get("id"),
                "status": data.get("status"),
                "amount": data.get("amount"),
            },
        )
        return JSONResponse(content=response_body)
    except Exception as error:
        log_paypal_failure("paypal.authorization.capture.failed", error)
        return JSONResponse(
            status_code=502, content={"error": "Could not capture PayPal authorization"}
        )
