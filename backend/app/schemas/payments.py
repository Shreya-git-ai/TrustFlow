from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import math
import re
from typing import Any


class InvalidPaymentRequest(ValueError):
    pass


_DECIMAL_NUMBER = re.compile(
    r"^[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?$"
)
_RADIX_NUMBER = re.compile(r"^0([xX][\da-fA-F]+|[bB][01]+|[oO][0-7]+)$")


def _javascript_number(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    if not isinstance(value, str):
        raise TypeError

    text = value.strip()
    if not text:
        return 0.0
    if _DECIMAL_NUMBER.fullmatch(text) or text in {"Infinity", "+Infinity", "-Infinity", "NaN"}:
        return float(text)
    radix = _RADIX_NUMBER.fullmatch(text)
    if radix:
        prefix = radix.group(1)[0].lower()
        base = {"x": 16, "b": 2, "o": 8}[prefix]
        return float(int(text[2:], base))
    raise ValueError


def _as_amount(value: Any) -> Decimal:
    try:
        # The original Express handler coerced input through Number() and then
        # called toFixed(2). Converting through float preserves those binary
        # rounding and underflow semantics at the API boundary.
        numeric_amount = _javascript_number(value)
        if not math.isfinite(numeric_amount) or numeric_amount <= 0:
            raise InvalidOperation
        amount = Decimal.from_float(numeric_amount)
        with localcontext() as context:
            context.prec = 1100
            return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, OverflowError, ValueError, TypeError):
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
        currency_value = body.get("currency")
        currency = _as_currency("USD" if currency_value is None else currency_value)
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
        amount: Decimal | None = None
        currency = "USD"
        if "amount" in body:
            amount = _as_amount(body["amount"])
            currency_value = body.get("currency")
            currency = _as_currency("USD" if currency_value is None else currency_value)
        return cls(
            authorization_id=authorization_id,
            amount=amount,
            currency=currency,
        )
