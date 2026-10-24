import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.security import get_current_user


class PaymentRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        app.dependency_overrides.clear()

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_health_is_public_and_readiness_is_authenticated(self):
        response = self.client.get("/health")
        self.assertEqual(response.json(), {"status": "ok", "service": "TrustFlow API"})
        self.assertIn("traceparent", response.headers)
        self.assertEqual(self.client.get("/ready").status_code, 401)

    def test_legacy_unscoped_payment_routes_are_not_exposed(self):
        for path in ("/paypal/create-order", "/paypal/authorize-order", "/paypal/capture-authorization"):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, json={"milestoneApproved": True}).status_code, 404)

    def test_capture_requires_session_and_ignores_caller_approval_claim(self):
        response = self.client.post("/milestones/abc/payment/capture", json={"milestoneApproved": True})
        self.assertEqual(response.status_code, 401)

    def test_only_client_can_request_capture(self):
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "freelancer-id", "email": "f@example.test", "name": "Freelancer",
            "role": "freelancer", "csrf_token": "csrf-value",
        }
        response = self.client.post(
            "/milestones/abc/payment/capture",
            json={},
            headers={"x-csrf-token": "csrf-value", "origin": "http://localhost:5173"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "Only the project client can access payment operations")

    def test_webhook_requires_paypal_signature_headers(self):
        response = self.client.post("/webhooks/paypal", json={"id": "event-1"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "PayPal signature headers are missing")

    def test_cors_allows_frontend_account_and_milestone_edits(self):
        response = self.client.options(
            "/auth/me",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("PATCH", response.headers["access-control-allow-methods"])
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:5173")

    def test_capture_fails_closed_when_paypal_omits_authorization_expiry(self):
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "client-id", "email": "c@example.test", "name": "Client",
            "role": "client", "csrf_token": "csrf-value",
        }
        payment = {
            "id": "payment-id", "status": "authorized", "paypal_authorization_id": "AUTH123",
            "amount": Decimal("10.00"), "currency": "USD",
        }
        paypal = SimpleNamespace(
            get_authorization=AsyncMock(return_value=(
                SimpleNamespace(is_success=True),
                {"status": "CREATED", "amount": {"value": "10.00", "currency_code": "USD"}},
            )),
        )
        with patch("app.routers.payments.payments.payment_for_client", return_value=payment), \
             patch("app.routers.payments.PayPalClient", return_value=paypal), \
             patch("app.routers.payments.payments.begin_capture") as begin_capture:
            response = self.client.post(
                "/milestones/m1/payment/capture",
                headers={"x-csrf-token": "csrf-value", "origin": "http://localhost:5173"},
            )
        self.assertEqual(response.status_code, 409)
        self.assertIn("expiry could not be verified", response.json()["detail"])
        begin_capture.assert_not_called()


if __name__ == "__main__":
    unittest.main()
