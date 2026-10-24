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

        explicit_null = CreateOrderRequest.from_payload({"currency": None})
        self.assertEqual(explicit_null.currency, "USD")

    def test_create_order_accepts_numeric_string_and_rounds_to_cents(self):
        parsed = CreateOrderRequest.from_payload({"amount": "12.345", "currency": "EUR"})
        self.assertEqual(parsed.amount, Decimal("12.35"))
        self.assertEqual(parsed.currency, "EUR")

    def test_amount_rounding_matches_javascript_number_to_fixed(self):
        self.assertEqual(
            CreateOrderRequest.from_payload({"amount": "1.005"}).amount,
            Decimal("1.00"),
        )
        self.assertEqual(
            CreateOrderRequest.from_payload({"amount": "1.125"}).amount,
            Decimal("1.13"),
        )

    def test_amount_underflow_and_overflow_match_javascript_number(self):
        for amount in ("1e-400", "1e309"):
            with self.subTest(amount=amount):
                with self.assertRaisesRegex(InvalidPaymentRequest, "positive number"):
                    CreateOrderRequest.from_payload({"amount": amount})

    def test_amount_strings_follow_javascript_number_syntax(self):
        self.assertEqual(
            CreateOrderRequest.from_payload({"amount": "0x10"}).amount,
            Decimal("16.00"),
        )
        with self.assertRaisesRegex(InvalidPaymentRequest, "positive number"):
            CreateOrderRequest.from_payload({"amount": "1_0"})

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

    def test_capture_schema_does_not_accept_a_caller_approval_as_authority(self):
        parsed = CaptureAuthorizationRequest.from_payload({"authorizationId": "AUTH123", "milestoneApproved": True})
        self.assertEqual(parsed.authorization_id, "AUTH123")

    def test_capture_without_amount_uses_authorized_remaining_amount(self):
        parsed = CaptureAuthorizationRequest.from_payload(
            {"authorizationId": "AUTH123"}
        )
        self.assertIsNone(parsed.amount)
        self.assertEqual(parsed.currency, "USD")

    def test_capture_null_currency_uses_usd_default(self):
        parsed = CaptureAuthorizationRequest.from_payload(
            {
                "authorizationId": "AUTH123",
                "amount": 5,
                "currency": None,
            }
        )
        self.assertEqual(parsed.amount, Decimal("5.00"))
        self.assertEqual(parsed.currency, "USD")


if __name__ == "__main__":
    unittest.main()
