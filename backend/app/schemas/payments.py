from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


class InvalidPaymentRequest(ValueError):
    pass


def _as_amount(value: Any) -> Decimal:
    if isinstance(value, bool):
        value = int(value)
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount <= 0:
            raise InvalidOperation
        return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        raise InvalidPaymentRequest("amount must be a positive number") from None


def _as_currency(value: Any) -> str:
    currency = "null" if value is None else str(value)
    if (
        len(currency) != 3
        or not currency.isascii()
        or not currency.isalpha()
        or not currency.isupper()
    ):
        raise InvalidPaymentRequest("currency must be a 3-letter uppercase code")
    return currency


def _body(payload: Any) -> dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


@dataclass(frozen=True)
class CreateOrderRequest:
    amount: Decimal
    currency: str

    @classmethod
    def from_payload(cls, payload: Any) -> "CreateOrderRequest":
        body = _body(payload)
        amount = body.get("amount", 10)
        if amount is None:
            amount = 10
        parsed_amount = _as_amount(amount)
        currency = _as_currency(body.get("currency", "USD"))
        return cls(amount=parsed_amount, currency=currency)


@dataclass(frozen=True)
class AuthorizeOrderRequest:
    order_id: str

    @classmethod
    def from_payload(cls, payload: Any) -> "AuthorizeOrderRequest":
        order_id = _body(payload).get("orderId")
        if (
            not isinstance(order_id, str)
            or not order_id.isascii()
            or not order_id.isalnum()
        ):
            raise InvalidPaymentRequest("A valid orderId is required")
        return cls(order_id=order_id)


@dataclass(frozen=True)
class CaptureAuthorizationRequest:
    authorization_id: str
    milestone_approved: bool
    amount: Decimal | None
    currency: str

    @classmethod
    def from_payload(cls, payload: Any) -> "CaptureAuthorizationRequest":
        body = _body(payload)
        authorization_id = body.get("authorizationId")
        if (
            not isinstance(authorization_id, str)
            or not authorization_id.isascii()
            or not authorization_id.isalnum()
        ):
            raise InvalidPaymentRequest("A valid authorizationId is required")
        if body.get("milestoneApproved") is not True:
            raise InvalidPaymentRequest("Milestone approval is required before capture")
        amount: Decimal | None = None
        currency = "USD"
        if "amount" in body:
            amount = _as_amount(body["amount"])
            currency = _as_currency(body.get("currency", "USD"))
        return cls(
            authorization_id=authorization_id,
            milestone_approved=True,
            amount=amount,
            currency=currency,
        )
