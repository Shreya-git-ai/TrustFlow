from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.observability import log_event
from app.payments.paypal import PayPalClient
from app.security import get_current_user, require_csrf
from app.services import refunds, workflow

router = APIRouter(tags=["refunds"])


class AgentRefundProposalBody(BaseModel):
    payment_id: UUID
    proposal_key: str = Field(min_length=8, max_length=128)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    reason: str = Field(min_length=10, max_length=3000)
    zendesk_ticket_id: int | None = Field(default=None, gt=0)
    slack_channel_id: str | None = Field(default=None, min_length=9, max_length=64, pattern=r"^[CDG][A-Z0-9]+$")
    slack_thread_ts: str | None = Field(default=None, min_length=3, max_length=32, pattern=r"^\d{6,}\.[0-9]+$")


class RefundDecisionBody(BaseModel):
    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=500)


def _domain(callable_, *args, **kwargs):
    try:
        return callable_(*args, **kwargs)
    except workflow.DomainError as error:
        raise HTTPException(error.status_code, error.detail) from error


@router.get("/refund-proposals")
def refund_proposals(status: str = "all", user: dict = Depends(get_current_user)):
    return _domain(refunds.list_for_merchant, user, status)


@router.post("/agent/refund-proposals", status_code=201)
def propose_refund(
    body: AgentRefundProposalBody,
    authorization: str = Header(default=""),
):
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not refunds.verify_agent_token(token):
        raise HTTPException(401, "Agent authentication failed")
    return _domain(
        refunds.create_agent_proposal,
        str(body.payment_id),
        body.proposal_key,
        body.amount,
        body.reason,
        zendesk_ticket_id=body.zendesk_ticket_id,
        slack_channel_id=body.slack_channel_id,
        slack_thread_ts=body.slack_thread_ts,
    )


@router.post("/refund-proposals/{proposal_id}/decision")
async def refund_decision(
    proposal_id: UUID,
    body: RefundDecisionBody,
    user: dict = Depends(require_csrf),
):
    proposal = _domain(refunds.decide_proposal, user, str(proposal_id), body.decision, body.note)
    if body.decision == "reject":
        return proposal
    if proposal["status"] == "refunded":
        return {
            "id": str(proposal_id),
            "paypal_refund_id": proposal.get("paypal_refund_id"),
            "status": "refunded",
        }

    try:
        response, result = await PayPalClient().refund_capture(
            proposal["paypal_capture_id"],
            Decimal(proposal["amount"]),
            str(proposal["currency"]).strip(),
            proposal["paypal_request_id"],
            str(proposal_id),
            proposal["paypal_payee_merchant_id"],
        )
    except Exception as error:
        log_event("warning", "payment.refund.result_unknown", error=type(error).__name__)
        return JSONResponse(
            status_code=202,
            content={"id": str(proposal_id), "status": "processing", "message": "Refund outcome is being confirmed with PayPal."},
        )

    if not response.is_success:
        if response.status_code in {400, 401, 403, 404, 422}:
            _domain(refunds.fail_proposal, str(proposal_id), "PayPal rejected the refund request")
            raise HTTPException(502, "PayPal did not accept the refund request")
        return JSONResponse(
            status_code=202,
            content={"id": str(proposal_id), "status": "processing", "message": "Refund outcome is being confirmed with PayPal."},
        )

    amount_data = result.get("amount") or {}
    try:
        actual_amount = Decimal(str(amount_data.get("value")))
    except (InvalidOperation, TypeError):
        actual_amount = Decimal("0")
    provider_status = str(result.get("status", "")).upper()
    refund_id = result.get("id")
    if provider_status == "FAILED":
        if isinstance(refund_id, str):
            recorded = _domain(
                refunds.record_paypal_refund,
                proposal["paypal_capture_id"],
                refund_id,
                actual_amount,
                str(amount_data.get("currency_code", "")),
                provider_status,
                proposal_id=str(proposal_id),
            )
            if not recorded:
                _domain(refunds.fail_proposal, str(proposal_id), "PayPal reported that the refund failed")
        else:
            _domain(refunds.fail_proposal, str(proposal_id), "PayPal reported that the refund failed")
        raise HTTPException(502, "PayPal could not complete this refund")
    if isinstance(refund_id, str) and provider_status in {"PENDING", "COMPLETED"}:
        recorded = _domain(
            refunds.record_paypal_refund,
            proposal["paypal_capture_id"],
            refund_id,
            actual_amount,
            str(amount_data.get("currency_code", "")),
            provider_status,
            proposal_id=str(proposal_id),
        )
        if recorded:
            return {
                "id": str(proposal_id),
                "paypal_refund_id": refund_id,
                "status": "refunded" if provider_status == "COMPLETED" else "processing",
            }

    return JSONResponse(
        status_code=202,
        content={"id": str(proposal_id), "status": "processing", "message": "Refund outcome is being confirmed with PayPal."},
    )
