from __future__ import annotations

import base64
import os
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx

from app.observability import log_event, traced


class PayPalClient:
    """Small async client for the PayPal REST operations used by TrustFlow."""

    def __init__(self) -> None:
        self.client_id = os.getenv("PAYPAL_CLIENT_ID", "")
        self.client_secret = os.getenv("PAYPAL_CLIENT_SECRET", "")
        self.base_url = os.getenv(
            "PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com"
        ).rstrip("/")
        self.return_url = os.getenv(
            "PAYPAL_RETURN_URL", "http://localhost:3000/paypal/return"
        )
        self.cancel_url = os.getenv(
            "PAYPAL_CANCEL_URL", "http://localhost:3000/paypal/cancel"
        )

    async def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> tuple[httpx.Response, dict[str, Any]]:
        async with traced(f"paypal.{method.lower()}"):
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=headers,
                    data=data,
                    json=json_body,
                )
            try:
                response_data = response.json()
            except ValueError:
                response_data = {}
            if not isinstance(response_data, dict):
                response_data = {}
            log_event(
                "info" if response.is_success else "warn",
                "paypal.response",
                statusCode=response.status_code,
                path=path,
            )
            return response, response_data

    async def get_access_token(self) -> str:
        if not self.client_id or not self.client_secret:
            raise RuntimeError("PayPal credentials are missing")
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("utf-8")
        ).decode("ascii")
        response, data = await self._request(
            "/v1/oauth2/token",
            method="POST",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={"grant_type": "client_credentials"},
        )
        access_token = data.get("access_token")
        if not response.is_success or not isinstance(access_token, str) or not access_token:
            raise RuntimeError(f"PayPal token request failed ({response.status_code})")
        return access_token

    async def test_auth(self) -> None:
        await self.get_access_token()

    async def create_order(
        self, amount: Decimal, currency: str
    ) -> tuple[httpx.Response, dict[str, Any]]:
        access_token = await self.get_access_token()
        return await self._request(
            "/v2/checkout/orders",
            method="POST",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "PayPal-Request-Id": str(uuid4()),
            },
            json_body={
                "intent": "AUTHORIZE",
                "purchase_units": [
                    {
                        "amount": {
                            "currency_code": currency,
                            "value": f"{amount:.2f}",
                        },
                        "description": "TrustFlow milestone payment",
                    }
                ],
                "application_context": {
                    "user_action": "PAY_NOW",
                    "return_url": self.return_url,
                    "cancel_url": self.cancel_url,
                },
            },
        )

    async def authorize_order(
        self, order_id: str
    ) -> tuple[httpx.Response, dict[str, Any]]:
        access_token = await self.get_access_token()
        return await self._request(
            f"/v2/checkout/orders/{order_id}/authorize",
            method="POST",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "PayPal-Request-Id": str(uuid4()),
            },
        )

    async def capture_authorization(
        self, authorization_id: str, amount: Decimal | None, currency: str
    ) -> tuple[httpx.Response, dict[str, Any]]:
        access_token = await self.get_access_token()
        capture_body: dict[str, Any] = {}
        if amount is not None:
            capture_body = {
                "amount": {"currency_code": currency, "value": f"{amount:.2f}"},
                "final_capture": True,
            }
        return await self._request(
            f"/v2/payments/authorizations/{authorization_id}/capture",
            method="POST",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "PayPal-Request-Id": str(uuid4()),
            },
            json_body=capture_body,
        )


def log_paypal_failure(event: str, error: Exception) -> None:
    log_event("error", event, error=type(error).__name__)
