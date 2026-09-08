"""
M-Pesa C2B validation/confirmation callbacks — split into their own router
at /api/payments/c2b (not /api/payments/mpesa/c2b) because Daraja's sandbox
flatly rejects any C2B ValidationURL/ConfirmationURL containing the literal
substring "mpesa" (error 400.003.02, "URL has the word MPESA"). Everything
else M-Pesa-related stays in routers/mpesa.py — only these two public
callback endpoints needed to move, since they're the ones Safaricom's
RegisterURL call actually points at.
"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_system_db
from app.schemas.mpesa import C2BPayload
from app.services.mpesa_reconciliation_service import record_c2b_transaction

logger = logging.getLogger("ledgr.mpesa")

router = APIRouter(prefix="/api/payments/c2b", tags=["mpesa"])


@router.post("/validation")
async def c2b_validation(request: Request):
    """
    PUBLIC — Safaricom calls this BEFORE the transaction completes, giving
    us a chance to reject it (e.g. unknown account). We deliberately always
    accept: rejecting a payment here bounces real money back to the payer
    with no clean way to recover it, whereas an unmatched account reference
    just becomes a review item in /reconciliation/lookup — a much safer
    failure mode for school fees than an incorrectly bounced payment.
    """
    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.post("/confirmation")
async def c2b_confirmation(request: Request, db: Session = Depends(get_system_db)):
    """
    PUBLIC — Safaricom's confirmation that a C2B (direct paybill) payment
    completed. Unlike /stk-push + /callback, this transaction was never
    initiated by Ledgr, so there's no CheckoutRequestID or pre-created
    PENDING payment to resolve — the raw transaction is recorded and
    matched (or queued for manual review) from scratch. See
    mpesa_reconciliation_service.record_c2b_transaction.
    """
    raw_body = await request.json()

    try:
        payload = C2BPayload.model_validate(raw_body)
    except Exception:
        logger.warning("Received malformed M-Pesa C2B confirmation: %s", raw_body)
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    record_c2b_transaction(db, payload)

    return {"ResultCode": 0, "ResultDesc": "Accepted"}
