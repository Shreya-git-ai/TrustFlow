import unittest
from decimal import Decimal

from app.schemas.payments import (
    AuthorizeOrderRequest,
    CaptureAuthorizationRequest,
    CreateOrderRequest,
    InvalidPaymentRequest,
)


class PaymentRequestSchemaTests(unittest.TestCase):
    def test_create_order_defaults_match_existing_contract(self):
        parsed = CreateOrderRequest.from_payload({})
        self.assertEqual(parsed.amount, Decimal("10.00"))
        self.assertEqual(parsed.currency, "USD")

    def test_create_order_accepts_numeric_string_and_rounds_to_cents(self):
        parsed = CreateOrderRequest.from_payload({"amount": "12.345", "currency": "EUR"})
        self.assertEqual(parsed.amount, Decimal("12.35"))
        self.assertEqual(parsed.currency, "EUR")

    def test_create_order_rejects_nonpositive_amount(self):
        with self.assertRaisesRegex(InvalidPaymentRequest, "positive number"):
            CreateOrderRequest.from_payload({"amount": 0})

    def test_create_order_rejects_nonuppercase_currency(self):
        with self.assertRaisesRegex(InvalidPaymentRequest, "uppercase code"):
            CreateOrderRequest.from_payload({"currency": "usd"})

    def test_authorize_order_requires_alphanumeric_id(self):
        self.assertEqual(
            AuthorizeOrderRequest.from_payload({"orderId": "ORDER123"}).order_id,
            "ORDER123",
        )
        with self.assertRaisesRegex(InvalidPaymentRequest, "orderId"):
            AuthorizeOrderRequest.from_payload({"orderId": "bad/id"})

    def test_capture_requires_milestone_approval(self):
        with self.assertRaisesRegex(InvalidPaymentRequest, "approval is required"):
            CaptureAuthorizationRequest.from_payload(
                {"authorizationId": "AUTH123", "milestoneApproved": False}
            )

    def test_capture_without_amount_uses_authorized_remaining_amount(self):
        parsed = CaptureAuthorizationRequest.from_payload(
            {"authorizationId": "AUTH123", "milestoneApproved": True}
        )
        self.assertIsNone(parsed.amount)
        self.assertEqual(parsed.currency, "USD")


if __name__ == "__main__":
    unittest.main()
