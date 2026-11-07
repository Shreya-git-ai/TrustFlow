from __future__ import annotations

import base64
import json
import os
from decimal import Decimal
from typing import Any
from uuid import uuid4

import httpx

from app.observability import log_event, traced
from app.security import public_frontend_origin


class PayPalClient:
    """Small async client for the PayPal REST operations used by TrustFlow."""

    def __init__(self) -> None:
        self.client_id = os.getenv("PAYPAL_CLIENT_ID", "")
        self.client_secret = os.getenv("PAYPAL_CLIENT_SECRET", "")
        self.base_url = os.getenv(
            "PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com"
        ).rstrip("/")
        frontend_origin = public_frontend_origin()
        if os.getenv("VERCEL_ENV", "").lower() == "production":
            self.return_url = f"{frontend_origin}/payment-return"
            self.cancel_url = f"{frontend_origin}/payment-cancel"
        else:
            self.return_url = os.getenv("PAYPAL_RETURN_URL", f"{frontend_origin}/payment-return")
            self.cancel_url = os.getenv("PAYPAL_CANCEL_URL", f"{frontend_origin}/payment-cancel")
        self.partner_merchant_id = os.getenv("PAYPAL_PARTNER_MERCHANT_ID", "").strip()
        self.attribution_id = os.getenv("PAYPAL_PARTNER_ATTRIBUTION_ID", "").strip()
        self.seller_return_url = (
            f"{frontend_origin}/paypal-onboarding-return"
            if os.getenv("VERCEL_ENV", "").lower() == "production"
            else os.getenv(
                "PAYPAL_SELLER_RETURN_URL",
                f"{frontend_origin}/paypal-onboarding-return",
            )
        )

    @property
    def marketplace_configured(self) -> bool:
        return bool(
            self.client_id and self.client_secret
            and self.partner_merchant_id and self.attribution_id
        )

    @staticmethod
    def _auth_assertion(client_id: str, merchant_id: str) -> str:
        def encode(value: dict[str, str]) -> str:
            raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
            return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

        return f"{encode({'alg': 'none'})}.{encode({'iss': client_id, 'payer_id': merchant_id})}."

    def _merchant_headers(self, access_token: str, merchant_id: str, request_id: str | None = None) -> dict[str, str]:
        if not merchant_id:
            raise RuntimeError("Freelancer PayPal account is not connected")
        if not self.partner_merchant_id or not self.attribution_id:
            raise RuntimeError("PayPal marketplace partner credentials are not configured")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "PayPal-Auth-Assertion": self._auth_assertion(self.client_id, merchant_id),
        }
        headers["PayPal-Partner-Attribution-Id"] = self.attribution_id
        if request_id:
            headers["PayPal-Request-Id"] = request_id
        return headers

    def _api_headers(
        self, access_token: str, request_id: str | None = None,
        payee_merchant_id: str | None = None,
    ) -> dict[str, str]:
        """Use standard merchant auth unless a legacy marketplace order has a payee."""
        if payee_merchant_id:
            return self._merchant_headers(access_token, payee_merchant_id, request_id)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        if request_id:
            headers["PayPal-Request-Id"] = request_id
        return headers

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
        self, amount: Decimal, currency: str, request_id: str | None = None,
        payee_merchant_id: str | None = None,
    ) -> tuple[httpx.Response, dict[str, Any]]:
        access_token = await self.get_access_token()
        purchase_unit: dict[str, Any] = {
            "amount": {
                "currency_code": currency,
                "value": f"{amount:.2f}",
            },
            "description": "TrustFlow milestone payment",
        }
        if payee_merchant_id:
            purchase_unit["payee"] = {"merchant_id": payee_merchant_id}
        return await self._request(
            "/v2/checkout/orders",
            method="POST",
            headers=self._api_headers(access_token, request_id or str(uuid4()), payee_merchant_id),
            json_body={
                "intent": "AUTHORIZE",
                "purchase_units": [purchase_unit],
                "payment_source": {
                    "paypal": {
                        "experience_context": {
                            "user_action": "PAY_NOW",
                            "return_url": self.return_url,
                            "cancel_url": self.cancel_url,
                        }
                    }
                },
            },
        )

    async def authorize_order(
        self, order_id: str, payee_merchant_id: str | None = None, request_id: str | None = None
    ) -> tuple[httpx.Response, dict[str, Any]]:
        access_token = await self.get_access_token()
        return await self._request(
            f"/v2/checkout/orders/{order_id}/authorize",
            method="POST",
            headers=self._api_headers(access_token, request_id or str(uuid4()), payee_merchant_id),
        )

    async def capture_authorization(
        self, authorization_id: str, amount: Decimal | None, currency: str,
        payee_merchant_id: str | None = None, request_id: str | None = None,
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
            headers=self._api_headers(access_token, request_id or str(uuid4()), payee_merchant_id),
            json_body=capture_body,
        )

    async def refund_capture(
        self, capture_id: str, amount: Decimal, currency: str, request_id: str,
        proposal_id: str, payee_merchant_id: str | None = None,
    ) -> tuple[httpx.Response, dict[str, Any]]:
        access_token = await self.get_access_token()
        return await self._request(
            f"/v2/payments/captures/{capture_id}/refund",
            method="POST",
            headers={
                **self._api_headers(access_token, request_id, payee_merchant_id),
                "Prefer": "return=representation",
            },
            json_body={
                "amount": {"currency_code": currency, "value": f"{amount:.2f}"},
                "custom_id": proposal_id,
            },
        )

    async def get_order(self, order_id: str, payee_merchant_id: str | None = None) -> tuple[httpx.Response, dict[str, Any]]:
        access_token = await self.get_access_token()
        return await self._request(
            f"/v2/checkout/orders/{order_id}",
            headers=self._api_headers(access_token, payee_merchant_id=payee_merchant_id),
        )

    async def get_authorization(self, authorization_id: str, payee_merchant_id: str | None = None) -> tuple[httpx.Response, dict[str, Any]]:
        access_token = await self.get_access_token()
        return await self._request(
            f"/v2/payments/authorizations/{authorization_id}",
            headers=self._api_headers(access_token, payee_merchant_id=payee_merchant_id),
        )

    async def create_partner_referral(self, email: str, tracking_id: str) -> dict[str, Any]:
        if not self.partner_merchant_id or not self.attribution_id:
            raise RuntimeError("PayPal partner onboarding is not configured")
        access_token = await self.get_access_token()
        response, data = await self._request(
            "/v2/customer/partner-referrals",
            method="POST",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "PayPal-Partner-Attribution-Id": self.attribution_id,
                "PayPal-Auth-Assertion": self._auth_assertion(self.client_id, self.partner_merchant_id),
            },
            json_body={
                "tracking_id": tracking_id,
                "email": email,
                "operations": [{
                    "operation": "API_INTEGRATION",
                    "api_integration_preference": {
                        "rest_api_integration": {
                            "integration_method": "PAYPAL",
                            "integration_type": "THIRD_PARTY",
                            "third_party_details": {"features": ["PAYMENT", "REFUND"]},
                        }
                    },
                }],
                "products": ["EXPRESS_CHECKOUT"],
                "legal_consents": [{"type": "SHARE_DATA_CONSENT", "granted": True}],
                "partner_config_override": {
                    "return_url": self.seller_return_url,
                    "return_url_description": "Return to TrustFlow after connecting your PayPal account.",
                    "show_add_credit_card": False,
                },
            },
        )
        if not response.is_success:
            raise RuntimeError("PayPal seller onboarding could not be started")
        return data

    async def get_seller_status(self, merchant_id: str) -> dict[str, Any]:
        if not self.partner_merchant_id or not self.attribution_id:
            raise RuntimeError("PayPal partner onboarding is not configured")
        access_token = await self.get_access_token()
        response, data = await self._request(
            f"/v1/customer/partners/{self.partner_merchant_id}/merchant-integrations/{merchant_id}",
            headers={
                **self._merchant_headers(access_token, merchant_id),
                "PayPal-Partner-Attribution-Id": self.attribution_id,
            },
        )
        if not response.is_success:
            raise RuntimeError("PayPal seller status could not be confirmed")
        return data

    async def verify_webhook(self, headers: dict[str, str], event: dict[str, Any]) -> bool:
        webhook_id = os.getenv("PAYPAL_WEBHOOK_ID", "")
        if not webhook_id:
            raise RuntimeError("PAYPAL_WEBHOOK_ID is not configured")
        access_token = await self.get_access_token()
        response, data = await self._request(
            "/v1/notifications/verify-webhook-signature",
            method="POST",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json_body={
                "auth_algo": headers.get("paypal-auth-algo"),
                "cert_url": headers.get("paypal-cert-url"),
                "transmission_id": headers.get("paypal-transmission-id"),
                "transmission_sig": headers.get("paypal-transmission-sig"),
                "transmission_time": headers.get("paypal-transmission-time"),
                "webhook_id": webhook_id,
                "webhook_event": event,
            },
        )
        return response.is_success and data.get("verification_status") == "SUCCESS"


def log_paypal_failure(event: str, error: Exception) -> None:
    log_event("error", event, error=type(error).__name__)
