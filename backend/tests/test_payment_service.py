import unittest
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import patch

from app.services import payments


class _Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class _OrderDatabase:
    def __init__(self):
        self.milestone = {
            "id": "milestone-1",
            "project_id": "project-1",
            "client_id": "client-1",
            "membership_status": "accepted",
            "project_status": "active",
            "agreement_status": "accepted",
            "amount": Decimal("10.00"),
            "currency": "USD ",
        }
        self.payment = None
        self.executed = []

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.executed.append((normalized, params))
        if normalized.startswith("SELECT m.*"):
            return _Cursor(dict(self.milestone))
        if normalized.startswith("SELECT * FROM payments"):
            return _Cursor(dict(self.payment) if self.payment else None)
        if normalized.startswith("INSERT INTO payments"):
            self.payment = {
                "id": "payment-1",
                "milestone_id": params[0],
                "created_by": params[1],
                "amount": params[2],
                "currency": params[3],
                "status": "created",
                "create_request_id": params[4],
                "authorize_request_id": params[5],
                "paypal_payee_merchant_id": None,
                "paypal_order_id": None,
            }
            return _Cursor(dict(self.payment))
        if normalized.startswith("INSERT INTO audit_events"):
            return _Cursor(None)
        if normalized.startswith("UPDATE payments SET paypal_payee_merchant_id = NULL"):
            self.payment["paypal_payee_merchant_id"] = None
            return _Cursor(dict(self.payment))
        return _Cursor(None)


class PaymentOrderServiceTests(unittest.TestCase):
    def test_prepare_order_uses_milestone_amount_without_freelancer_onboarding(self):
        database = _OrderDatabase()

        @contextmanager
        def transaction():
            yield database

        with patch("app.services.payments.transaction", transaction):
            payment = payments.prepare_order({"id": "client-1", "role": "client"}, "milestone-1")

        self.assertEqual(payment["amount"], Decimal("10.00"))
        self.assertEqual(payment["currency"], "USD ")
        self.assertIsNone(payment["paypal_payee_merchant_id"])
        insert = next(sql for sql, _ in database.executed if sql.startswith("INSERT INTO payments"))
        self.assertNotIn("paypal_payee_merchant_id", insert)

    def test_prepare_order_clears_unsubmitted_legacy_payee_routing(self):
        database = _OrderDatabase()
        database.payment = {
            "id": "payment-1", "status": "created", "paypal_order_id": None,
            "paypal_payee_merchant_id": "OLD_SELLER", "create_request_id": "create-1",
        }

        @contextmanager
        def transaction():
            yield database

        with patch("app.services.payments.transaction", transaction):
            payment = payments.prepare_order({"id": "client-1", "role": "client"}, "milestone-1")

        self.assertIsNone(payment["paypal_payee_merchant_id"])
        self.assertTrue(any(sql.startswith("UPDATE payments SET paypal_payee_merchant_id = NULL") for sql, _ in database.executed))


if __name__ == "__main__":
    unittest.main()
