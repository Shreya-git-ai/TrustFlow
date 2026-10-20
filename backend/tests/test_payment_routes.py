import unittest
from importlib.util import find_spec


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

        async def test_auth(self):
            return None

        async def create_order(self, amount, currency):
            self.created_order = (amount, currency)
            return _FakeResponse(201), {
                "id": "ORDER123",
                "status": "CREATED",
                "links": [{"rel": "approve", "href": "https://paypal.example/approve"}],
            }

        async def authorize_order(self, order_id):
            self.authorized_order = order_id
            return _FakeResponse(), {
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
            return _FakeResponse(), {
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

        def test_create_order_contract(self):
            response = self.client.post("/paypal/create-order", json={})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()["orderId"], "ORDER123")
            self.assertEqual(response.json()["approvalUrl"], "https://paypal.example/approve")
            self.assertEqual(self.paypal.created_order, (10, "USD"))

        def test_authorize_order_contract(self):
            response = self.client.post(
                "/paypal/authorize-order", json={"orderId": "ORDER123"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["authorizationId"], "AUTH123")
            self.assertEqual(self.paypal.authorized_order, "ORDER123")

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
