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
            "amount": Decimal("10.00"), "currency": "USD", "paypal_payee_merchant_id": None,
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

    def test_order_authorize_capture_route_flow_with_mocked_paypal(self):
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "client-id", "email": "c@example.test", "name": "Client",
            "role": "client", "csrf_token": "csrf-value",
        }
        headers = {"x-csrf-token": "csrf-value", "origin": "http://localhost:5173"}
        success = SimpleNamespace(is_success=True, status_code=201)
        paypal = SimpleNamespace(
            marketplace_configured=True,
            create_order=AsyncMock(return_value=(success, {
                "id": "ORDER123", "status": "CREATED",
                "links": [{"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER123"}],
            })),
            get_order=AsyncMock(return_value=(success, {"id": "ORDER123", "status": "APPROVED", "purchase_units": [{}]})),
            authorize_order=AsyncMock(return_value=(success, {"purchase_units": [{"payments": {"authorizations": [{
                "id": "AUTH123", "status": "CREATED", "amount": {"value": "10.00", "currency_code": "USD"},
            }]}}]})),
            get_authorization=AsyncMock(return_value=(success, {
                "status": "CREATED", "expiration_time": "2099-01-01T00:00:00Z",
                "amount": {"value": "10.00", "currency_code": "USD"},
            })),
            capture_authorization=AsyncMock(return_value=(success, {
                "id": "CAPTURE123", "status": "COMPLETED",
                "amount": {"value": "10.00", "currency_code": "USD"},
            })),
        )
        payment = {
            "id": "PAYMENT1", "status": "created", "amount": Decimal("10.00"),
            "currency": "USD", "paypal_payee_merchant_id": None,
            "create_request_id": "create-1", "authorize_request_id": "authorize-1",
            "capture_request_id": "capture-1",
            "paypal_authorization_id": "AUTH123",
        }
        ordered_payment = {**payment, "paypal_order_id": "ORDER123"}
        authorized_payment = {**payment, "status": "authorized"}
        captured_payment = {**payment, "status": "captured", "paypal_capture_id": "CAPTURE123"}
        with patch("app.routers.payments.PayPalClient", return_value=paypal), \
             patch("app.routers.payments.payments.prepare_order", return_value=payment), \
             patch("app.routers.payments.payments.save_order", return_value=ordered_payment), \
             patch("app.routers.payments.payments.payment_for_client", side_effect=[ordered_payment, authorized_payment]), \
             patch("app.routers.payments.payments.set_buyer_approved"), \
             patch("app.routers.payments.payments.mark_authorized", return_value=authorized_payment), \
             patch("app.routers.payments.payments.begin_capture", return_value=authorized_payment), \
             patch("app.routers.payments.payments.finish_capture", return_value=captured_payment), \
             patch("app.routers.payments.deliver_pending", new_callable=AsyncMock):
            order = self.client.post(
                "/milestones/m1/payment/order",
                headers=headers,
                json={"amount": "0.01", "currency": "EUR", "paypal_order_id": "ATTACKER_ORDER"},
            )
            authorization = self.client.post("/milestones/m1/payment/authorize", headers=headers)
            capture = self.client.post("/milestones/m1/payment/capture", headers=headers)

        self.assertEqual(order.status_code, 201, order.text)
        self.assertEqual(order.json()["order_id"], "ORDER123")
        self.assertEqual(authorization.status_code, 200, authorization.text)
        self.assertEqual(authorization.json(), {"status": "authorized", "authorization_id": "AUTH123"})
        self.assertEqual(capture.status_code, 200, capture.text)
        self.assertEqual(capture.json(), {"status": "captured", "capture_id": "CAPTURE123"})
        paypal.create_order.assert_awaited_once()
        paypal.create_order.assert_awaited_once_with(Decimal("10.00"), "USD", "create-1")
        paypal.authorize_order.assert_awaited_once()
        paypal.capture_authorization.assert_awaited_once()

    def test_standard_order_does_not_require_marketplace_or_freelancer_onboarding(self):
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "client-id", "email": "c@example.test", "name": "Client",
            "role": "client", "csrf_token": "csrf-value",
        }
        payment = {
            "id": "payment-id", "status": "created", "amount": Decimal("10.00"),
            "currency": "USD", "create_request_id": "create-1", "paypal_payee_merchant_id": None,
        }
        success = SimpleNamespace(is_success=True, status_code=201)
        paypal = SimpleNamespace(create_order=AsyncMock(return_value=(success, {
            "id": "ORDER123", "status": "CREATED",
            "links": [{"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER123"}],
        })))
        with patch("app.routers.payments.payments.prepare_order", return_value=payment), \
             patch("app.routers.payments.payments.save_order", return_value={**payment, "paypal_order_id": "ORDER123"}), \
             patch("app.routers.payments.PayPalClient", return_value=paypal), \
             patch("app.routers.payments.deliver_pending", new_callable=AsyncMock):
            response = self.client.post(
                "/milestones/m1/payment/order",
                headers={"x-csrf-token": "csrf-value", "origin": "http://localhost:5173"},
            )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["approval_url"], "https://www.sandbox.paypal.com/checkoutnow?token=ORDER123")
        paypal.create_order.assert_awaited_once_with(Decimal("10.00"), "USD", "create-1")


if __name__ == "__main__":
    unittest.main()
