import unittest
from datetime import datetime, timezone
from importlib.util import find_spec
from unittest.mock import patch


if find_spec("fastapi") and find_spec("httpx"):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.routers.payments import get_paypal_client

    class _FakeResponse:
        def __init__(self, status_code=200):
            self.status_code = status_code
            self.is_success = 200 <= status_code < 300

    class _FakePayPalClient:
        def __init__(self):
            self.capture_calls = []
            self.auth_error = None
            self.create_error = None
            self.create_response = _FakeResponse(201)
            self.authorize_error = None
            self.authorize_response = _FakeResponse()
            self.capture_error = None
            self.capture_response = _FakeResponse()

        async def test_auth(self):
            if self.auth_error:
                raise self.auth_error
            return None

        async def create_order(self, amount, currency):
            self.created_order = (amount, currency)
            if self.create_error:
                raise self.create_error
            return self.create_response, {
                "id": "ORDER123",
                "status": "CREATED",
                "links": [{"rel": "approve", "href": "https://paypal.example/approve"}],
            }

        async def authorize_order(self, order_id):
            self.authorized_order = order_id
            if self.authorize_error:
                raise self.authorize_error
            return self.authorize_response, {
                "id": order_id,
                "status": "CREATED",
                "purchase_units": [
                    {
                        "payments": {
                            "authorizations": [
                                {
                                    "id": "AUTH123",
                                    "status": "CREATED",
                                    "amount": {"value": "10.00", "currency_code": "USD"},
                                }
                            ]
                        }
                    }
                ],
            }

        async def capture_authorization(self, authorization_id, amount, currency):
            self.capture_calls.append((authorization_id, amount, currency))
            if self.capture_error:
                raise self.capture_error
            return self.capture_response, {
                "id": "CAPTURE123",
                "status": "COMPLETED",
                "amount": {"value": "10.00", "currency_code": "USD"},
            }

    @unittest.skipUnless(
        find_spec("fastapi") and find_spec("httpx"),
        "install backend requirements to run route tests",
    )
    class PaymentRouteTests(unittest.TestCase):
        def setUp(self):
            self.paypal = _FakePayPalClient()
            app.dependency_overrides[get_paypal_client] = lambda: self.paypal
            self.client = TestClient(app)

        def tearDown(self):
            app.dependency_overrides.clear()

        def test_health_route(self):
            response = self.client.get("/health")
            self.assertEqual(response.json(), {"status": "ok", "service": "TrustFlow API"})
            self.assertIn("traceparent", response.headers)

        def test_paypal_auth_contract_and_provider_failure(self):
            response = self.client.get("/paypal/test-auth")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json(),
                {"success": True, "message": "Authenticated with PayPal"},
            )

            self.paypal.auth_error = RuntimeError("provider unavailable")
            failed = self.client.get("/paypal/test-auth")
            self.assertEqual(failed.status_code, 502)
            self.assertEqual(
                failed.json(),
                {"success": False, "error": "PayPal authentication failed"},
            )

        def test_create_order_contract(self):
            response = self.client.post("/paypal/create-order", json={})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["orderId"], "ORDER123")
            self.assertEqual(response.json()["approvalUrl"], "https://paypal.example/approve")
            self.assertEqual(self.paypal.created_order, (10, "USD"))

        def test_create_order_validation_and_provider_errors(self):
            for payload, expected_error in (
                ({"amount": 0}, "amount must be a positive number"),
                ({"amount": "nope"}, "amount must be a positive number"),
                ({"currency": "usd"}, "currency must be a 3-letter uppercase code"),
            ):
                with self.subTest(payload=payload):
                    response = self.client.post("/paypal/create-order", json=payload)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.json(), {"error": expected_error})

            self.paypal.create_response = _FakeResponse(429)
            failed = self.client.post("/paypal/create-order", json={"amount": 1})
            self.assertEqual(failed.status_code, 502)
            self.assertEqual(
                failed.json(),
                {"error": "PayPal order creation failed", "paypalStatus": 429},
            )

            self.paypal.create_error = TimeoutError()
            unavailable = self.client.post("/paypal/create-order", json={"amount": 1})
            self.assertEqual(unavailable.status_code, 502)
            self.assertEqual(
                unavailable.json(), {"error": "Could not create PayPal order"}
            )

        def test_authorize_order_contract(self):
            response = self.client.post(
                "/paypal/authorize-order", json={"orderId": "ORDER123"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["authorizationId"], "AUTH123")
            self.assertEqual(self.paypal.authorized_order, "ORDER123")

        def test_authorize_order_validation_and_provider_error(self):
            invalid = self.client.post("/paypal/authorize-order", json={})
            self.assertEqual(invalid.status_code, 400)
            self.assertEqual(invalid.json(), {"error": "A valid orderId is required"})

            self.paypal.authorize_response = _FakeResponse(503)
            failed = self.client.post(
                "/paypal/authorize-order", json={"orderId": "ORDER123"}
            )
            self.assertEqual(failed.status_code, 502)
            self.assertEqual(
                failed.json(),
                {"error": "PayPal authorization failed", "paypalStatus": 503},
            )

        def test_capture_requires_approval_and_maps_response(self):
            rejected = self.client.post(
                "/paypal/capture-authorization",
                json={"authorizationId": "AUTH123", "milestoneApproved": False},
            )
            self.assertEqual(rejected.status_code, 403)
            self.assertEqual(self.paypal.capture_calls, [])

            accepted = self.client.post(
                "/paypal/capture-authorization",
                json={"authorizationId": "AUTH123", "milestoneApproved": True},
            )
            self.assertEqual(accepted.status_code, 200)
            self.assertEqual(accepted.json()["captureId"], "CAPTURE123")
            self.assertEqual(self.paypal.capture_calls[0], ("AUTH123", None, "USD"))

        def test_capture_validation_and_provider_error(self):
            for payload, status, error in (
                ({}, 400, "A valid authorizationId is required"),
                (
                    {"authorizationId": "AUTH123", "milestoneApproved": True, "amount": 0},
                    400,
                    "amount must be a positive number",
                ),
                (
                    {"authorizationId": "AUTH123", "milestoneApproved": True, "amount": 1, "currency": "usd"},
                    400,
                    "currency must be a 3-letter uppercase code",
                ),
            ):
                with self.subTest(payload=payload):
                    response = self.client.post("/paypal/capture-authorization", json=payload)
                    self.assertEqual(response.status_code, status)
                    self.assertEqual(response.json(), {"error": error})

            self.paypal.capture_response = _FakeResponse(409)
            failed = self.client.post(
                "/paypal/capture-authorization",
                json={"authorizationId": "AUTH123", "milestoneApproved": True},
            )
            self.assertEqual(failed.status_code, 502)
            self.assertEqual(
                failed.json(), {"error": "PayPal capture failed", "paypalStatus": 409}
            )

        def test_database_routes_without_external_writes(self):
            with patch("app.main.test_connection", side_effect=RuntimeError):
                unavailable = self.client.get("/db/test")
            self.assertEqual(unavailable.status_code, 500)
            self.assertEqual(
                unavailable.json(),
                {"success": False, "error": "Database connection failed. Check DATABASE_URL."},
            )

            with patch(
                "app.main.test_connection",
                return_value=("audit-db", datetime(2026, 10, 20, tzinfo=timezone.utc)),
            ):
                connected = self.client.get("/db/test")
            self.assertEqual(connected.status_code, 200)
            self.assertEqual(connected.json()["database"], "audit-db")

            with patch("app.main.apply_schema") as apply_schema:
                setup = self.client.post("/db/setup-schema")
            self.assertEqual(setup.status_code, 200)
            self.assertEqual(
                setup.json()["tables"],
                ["users", "projects", "milestones", "evidence", "payments", "audit_events", "webhook_events"],
            )
            apply_schema.assert_called_once_with()

        def test_callback_paths_and_unsupported_methods(self):
            self.assertEqual(self.client.get("/paypal/return?token=ORDER123").status_code, 404)
            self.assertEqual(self.client.get("/paypal/cancel").status_code, 404)
            self.assertEqual(self.client.post("/health").status_code, 405)

        def test_invalid_json_matches_existing_error_shape(self):
            response = self.client.post(
                "/paypal/create-order",
                content="{",
                headers={"content-type": "application/json"},
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {"error": "Invalid request"})

        def test_oversized_json_matches_existing_error_shape(self):
            response = self.client.post(
                "/paypal/create-order",
                content='{"padding":"' + ("x" * (32 * 1024)) + '"}',
                headers={"content-type": "application/json"},
            )
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json(), {"error": "Invalid request"})

else:
    @unittest.skip("install backend requirements to run route tests")
    class PaymentRouteTests(unittest.TestCase):
        def test_backend_dependencies_are_installed(self):
            pass
