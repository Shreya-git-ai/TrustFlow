import base64
import json
import os
import unittest
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import parse_qs
from uuid import UUID

import httpx

from app.payments.paypal import PayPalClient


class PayPalHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_mocked_oauth_order_authorize_and_capture_requests(self):
        requests = []
        timeouts = []
        original_client = httpx.AsyncClient
        client_id = "audit-client-id"
        client_secret = "audit-client-secret"
        base_url = "https://api-m.sandbox.paypal.com"

        def handler(request):
            requests.append(request)
            if request.url.path == "/v1/oauth2/token":
                self.assertEqual(
                    request.headers["authorization"],
                    "Basic "
                    + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode(),
                )
                self.assertEqual(
                    parse_qs(request.content.decode()),
                    {"grant_type": ["client_credentials"]},
                )
                return httpx.Response(200, json={"access_token": "mock-access-token"})

            self.assertEqual(request.headers["authorization"], "Bearer mock-access-token")
            if request.url.path == "/v2/checkout/orders":
                body = json.loads(request.content)
                self.assertEqual(body["intent"], "AUTHORIZE")
                self.assertEqual(
                    body["purchase_units"][0]["amount"],
                    {"currency_code": "EUR", "value": "12.35"},
                )
                self.assertEqual(body["application_context"]["return_url"], "https://return.test")
                return httpx.Response(
                    201,
                    json={
                        "id": "ORDER123",
                        "status": "CREATED",
                        "links": [{"rel": "approve", "href": "https://approve.test"}],
                    },
                )

            if request.url.path == "/v2/checkout/orders/ORDER123/authorize":
                return httpx.Response(
                    200,
                    json={
                        "id": "ORDER123",
                        "status": "COMPLETED",
                        "purchase_units": [
                            {"payments": {"authorizations": [{"id": "AUTH123", "status": "CREATED"}]}}
                        ],
                    },
                )

            if request.url.path == "/v2/payments/authorizations/AUTH123/capture":
                body = json.loads(request.content)
                self.assertEqual(
                    body,
                    {
                        "amount": {"currency_code": "USD", "value": "5.25"},
                        "final_capture": True,
                    },
                )
                return httpx.Response(
                    201,
                    json={
                        "id": "CAPTURE123",
                        "status": "COMPLETED",
                        "amount": {"value": "5.25", "currency_code": "USD"},
                    },
                )

            self.fail(f"Unexpected mocked provider path: {request.url.path}")

        transport = httpx.MockTransport(handler)

        def mock_client(*, timeout):
            timeouts.append(timeout)
            return original_client(timeout=timeout, transport=transport)

        with patch.dict(
            os.environ,
            {
                "PAYPAL_CLIENT_ID": client_id,
                "PAYPAL_CLIENT_SECRET": client_secret,
                "PAYPAL_BASE_URL": base_url,
                "PAYPAL_RETURN_URL": "https://return.test",
                "PAYPAL_CANCEL_URL": "https://cancel.test",
            },
        ), patch("app.payments.paypal.httpx.AsyncClient", side_effect=mock_client):
            paypal = PayPalClient()
            order_response, order = await paypal.create_order(Decimal("12.35"), "EUR")
            authorization_response, authorization = await paypal.authorize_order("ORDER123")
            capture_response, capture = await paypal.capture_authorization(
                "AUTH123", Decimal("5.25"), "USD"
            )

        self.assertEqual(order_response.status_code, 201)
        self.assertEqual(order["id"], "ORDER123")
        self.assertEqual(authorization_response.status_code, 200)
        self.assertEqual(
            authorization["purchase_units"][0]["payments"]["authorizations"][0]["id"],
            "AUTH123",
        )
        self.assertEqual(capture_response.status_code, 201)
        self.assertEqual(capture["id"], "CAPTURE123")
        self.assertEqual(len(requests), 6)  # a fresh OAuth request for each operation
        self.assertTrue(all(timeout == 15.0 for timeout in timeouts))

        request_ids = [request.headers["paypal-request-id"] for request in requests if "paypal-request-id" in request.headers]
        self.assertEqual(len(request_ids), 3)
        self.assertEqual(len(set(request_ids)), 3)
        for request_id in request_ids:
            UUID(request_id)

    async def test_oauth_provider_failure_is_reported_without_token(self):
        original_client = httpx.AsyncClient
        requests = []

        def handler(request):
            requests.append(request)
            return httpx.Response(401, json={"error": "invalid_client"})

        transport = httpx.MockTransport(handler)

        def mock_client(*, timeout):
            return original_client(timeout=timeout, transport=transport)

        with patch.dict(
            os.environ,
            {"PAYPAL_CLIENT_ID": "audit-id", "PAYPAL_CLIENT_SECRET": "audit-secret"},
        ), patch("app.payments.paypal.httpx.AsyncClient", side_effect=mock_client):
            with self.assertRaisesRegex(RuntimeError, r"token request failed \(401\)"):
                await PayPalClient().test_auth()

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url.path, "/v1/oauth2/token")


if __name__ == "__main__":
    unittest.main()
