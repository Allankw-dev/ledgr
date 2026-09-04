import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db, get_system_db
from app.core.deps import get_current_user, get_school_scope, CurrentUser
from app.core.config import settings
from app.schemas.mpesa import StkPushRequest, StkPushResponse, MpesaCallbackPayload
from app.services.mpesa_service import initiate_stk_push, normalize_phone_number, MpesaConfigError
from app.services.payment_service import create_pending_mpesa_payment, resolve_mpesa_callback
from app.models.invoice import Invoice
from app.models.student import Student, StudentGuardian

logger = logging.getLogger("ledgr.mpesa")

router = APIRouter(prefix="/api/payments/mpesa", tags=["mpesa"])


@router.post("/stk-push", response_model=StkPushResponse, status_code=201)
async def request_stk_push(
    data: StkPushRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    school_id: str = Depends(get_school_scope),
):
    """
    Triggers an M-Pesa prompt on the payer's phone. Callable by a bursar
    (paying on a parent's behalf, e.g. over the phone) or a parent (paying
    for their own child) — but a parent must be linked to the student on
    this invoice via student_guardians, checked explicitly below rather
    than assumed from role alone.
    """
    invoice = db.execute(
        select(Invoice).where(Invoice.id == data.invoice_id, Invoice.school_id == school_id)
    ).scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Invoice not found")

    if user.role == "PARENT":
        link = db.execute(
            select(StudentGuardian).where(
                StudentGuardian.student_id == invoice.student_id,
                StudentGuardian.user_id == user.user_id,
            )
        ).scalar_one_or_none()
        if not link:
            raise HTTPException(403, "You can only pay fees for your own children")

    balance = invoice.total_amount - invoice.amount_paid
    if balance <= 0:
        raise HTTPException(422, "This invoice is already fully paid")

    student = db.get(Student, invoice.student_id)

    if not settings.mpesa_callback_url:
        raise HTTPException(503, "M-Pesa is not fully configured yet — missing callback URL")

    try:
        phone = normalize_phone_number(data.phone_number)
        result = await initiate_stk_push(
            phone_number=phone,
            amount=int(balance),
            account_reference=student.admission_number if student else "Ledgr",
            transaction_desc="School fees",
            callback_url=settings.mpesa_callback_url,
        )
    except MpesaConfigError as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:  # noqa: BLE001 — any Daraja/network failure should surface as a clean 502, not crash
        logger.exception("STK push failed")
        raise HTTPException(502, f"Could not reach M-Pesa: {exc}")

    checkout_request_id = result.get("CheckoutRequestID")
    if not checkout_request_id:
        raise HTTPException(502, "M-Pesa did not return a valid request ID")

    create_pending_mpesa_payment(
        db,
        school_id=school_id,
        student_id=invoice.student_id,
        invoice_id=invoice.id,
        amount=balance,
        checkout_request_id=checkout_request_id,
    )

    return StkPushResponse(
        checkout_request_id=checkout_request_id,
        message="Check your phone and enter your M-Pesa PIN to complete payment.",
    )


@router.post("/callback")
async def mpesa_callback(request: Request, db: Session = Depends(get_system_db)):
    """
    PUBLIC endpoint — Safaricom's servers call this directly, with no auth
    header we control, so it never runs get_school_scope and therefore never
    gets an RLS tenant context. It uses get_system_db (the unrestricted
    owner role) instead of get_db for exactly that reason — see the comment
    on SystemSessionLocal in database.py. Security here relies on the fact
    that a forged callback can only affect a PENDING payment that already
    exists with a matching CheckoutRequestID (created by our own /stk-push
    call) — it cannot create new payments or touch already-CONFIRMED ones.

    Only returns 200 for cases where a retry genuinely wouldn't help (a
    malformed/unrecognized payload — Safaricom won't send a different shape
    next time). A transient failure on our side (e.g. a DB hiccup) is
    allowed to propagate as a 500, since Safaricom's automatic retry is
    exactly the right recovery mechanism for that — swallowing it into a
    blanket 200 would risk silently losing a real payment confirmation.
    """
    raw_body = await request.json()

    try:
        payload = MpesaCallbackPayload.model_validate(raw_body)
    except Exception:
        logger.warning("Received malformed M-Pesa callback: %s", raw_body)
        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    callback = payload.Body.stkCallback

    mpesa_receipt = None
    if callback.CallbackMetadata:
        items = callback.CallbackMetadata.get("Item", [])
        for item in items:
            if item.get("Name") == "MpesaReceiptNumber":
                mpesa_receipt = item.get("Value")

    # Deliberately NOT wrapped in try/except — see docstring above.
    resolve_mpesa_callback(
        db,
        checkout_request_id=callback.CheckoutRequestID,
        result_code=callback.ResultCode,
        mpesa_receipt_number=str(mpesa_receipt) if mpesa_receipt else None,
    )

    return {"ResultCode": 0, "ResultDesc": "Accepted"}
