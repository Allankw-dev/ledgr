import logging

from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db, get_system_db
from app.core.webhook_auth import verify_mpesa_webhook
from app.core.deps import get_current_user, get_school_scope, require_roles, CurrentUser
from app.core.config import settings
from app.core.idempotency import reserve_key, release_key, store_result
from app.core.rate_limit import limiter
from app.schemas.mpesa import (
    StkPushRequest,
    StkPushResponse,
    MpesaCallbackPayload,
    MpesaTransactionLookup,
    MatchTransactionRequest,
)
from app.services.mpesa_service import initiate_stk_push, normalize_phone_number, MpesaConfigError
from app.services.payment_service import create_pending_mpesa_payment, resolve_mpesa_callback
from app.services.mpesa_reconciliation_service import (
    find_unmatched_transaction,
    match_transaction_to_invoice,
)
from app.models.invoice import Invoice
from app.models.student import Student, StudentGuardian

logger = logging.getLogger("ledgr.mpesa")

router = APIRouter(prefix="/api/payments/mpesa", tags=["mpesa"])


def _prepare_stk_push(db: Session, data: StkPushRequest, user: CurrentUser, school_id: str):
    """All the synchronous DB work for an STK push, kept in a plain function
    so the async route can run it in the threadpool. Calling blocking
    SQLAlchemy directly inside an `async def` handler freezes the whole event
    loop (every other request on that worker) while the query runs."""
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
    return invoice, balance, student


@router.post("/stk-push", response_model=StkPushResponse, status_code=201)
async def request_stk_push(
    data: StkPushRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    school_id: str = Depends(get_school_scope),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """
    Triggers an M-Pesa prompt on the payer's phone. Callable by a bursar
    (paying on a parent's behalf, e.g. over the phone) or a parent (paying
    for their own child) — but a parent must be linked to the student on
    this invoice via student_guardians, checked explicitly below rather
    than assumed from role alone.

    Idempotency-Key: without it, a double-tap on "Pay now" — or a client
    retrying because the response was slow or dropped — fires a SECOND STK
    prompt to the parent's phone and a second PENDING payment. The actual
    Daraja call can't be wrapped in a DB transaction (it's an irreversible
    external side effect), so this uses the lower-level reserve/store pair
    instead of run_idempotent: reserve the key BEFORE calling Daraja (so a
    concurrent duplicate request waits instead of also calling Daraja), then
    store the result after. If Daraja itself fails, the reservation is
    released so a genuine retry isn't stuck behind a dead key.
    """
    invoice, balance, student = await run_in_threadpool(_prepare_stk_push, db, data, user, school_id)

    if not settings.mpesa_callback_url:
        raise HTTPException(503, "M-Pesa is not fully configured yet — missing callback URL")

    request_body = data.model_dump(mode="json")

    if idempotency_key:
        reservation = await run_in_threadpool(
            reserve_key,
            db,
            school_id=school_id,
            user_id=user.user_id,
            scope="mpesa.stk_push",
            key=idempotency_key,
            request_body=request_body,
        )
        if reservation is not None:
            _, stored_response = reservation
            return StkPushResponse.model_validate(stored_response)

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
        if idempotency_key:
            await run_in_threadpool(release_key, db, school_id=school_id, user_id=user.user_id, scope="mpesa.stk_push", key=idempotency_key)
        raise HTTPException(503, str(exc))
    except Exception as exc:  # noqa: BLE001 — any Daraja/network failure should surface as a clean 502, not crash
        logger.exception("STK push failed")
        if idempotency_key:
            await run_in_threadpool(release_key, db, school_id=school_id, user_id=user.user_id, scope="mpesa.stk_push", key=idempotency_key)
        raise HTTPException(502, f"Could not reach M-Pesa: {exc}")

    checkout_request_id = result.get("CheckoutRequestID")
    if not checkout_request_id:
        if idempotency_key:
            await run_in_threadpool(release_key, db, school_id=school_id, user_id=user.user_id, scope="mpesa.stk_push", key=idempotency_key)
        raise HTTPException(502, "M-Pesa did not return a valid request ID")

    await run_in_threadpool(
        create_pending_mpesa_payment,
        db,
        school_id=school_id,
        student_id=invoice.student_id,
        invoice_id=invoice.id,
        amount=balance,
        checkout_request_id=checkout_request_id,
    )

    response = StkPushResponse(
        checkout_request_id=checkout_request_id,
        message="Check your phone and enter your M-Pesa PIN to complete payment.",
    )
    if idempotency_key:
        await run_in_threadpool(
            store_result,
            db,
            school_id=school_id,
            user_id=user.user_id,
            scope="mpesa.stk_push",
            key=idempotency_key,
            status_code=201,
            response=response.model_dump(mode="json"),
        )
    return response

@router.post("/callback", dependencies=[Depends(verify_mpesa_webhook)])
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
    paid_amount = None
    if callback.CallbackMetadata:
        items = callback.CallbackMetadata.get("Item", [])
        for item in items:
            if item.get("Name") == "MpesaReceiptNumber":
                mpesa_receipt = item.get("Value")
            elif item.get("Name") == "Amount":
                paid_amount = item.get("Value")

    # Deliberately NOT wrapped in try/except — see docstring above.
    await run_in_threadpool(
        resolve_mpesa_callback,
        db,
        checkout_request_id=callback.CheckoutRequestID,
        paid_amount=paid_amount,
        result_code=callback.ResultCode,
        mpesa_receipt_number=str(mpesa_receipt) if mpesa_receipt else None,
    )

    return {"ResultCode": 0, "ResultDesc": "Accepted"}


@router.get("/reconciliation/lookup", response_model=MpesaTransactionLookup)
@limiter.limit("20/hour")
def lookup_c2b_transaction(
    request: Request,  # required by @limiter.limit — unused otherwise
    trans_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    """
    A bursar enters the M-Pesa code a parent read out to them over the
    phone to find a stray paybill payment that didn't auto-match — a
    targeted lookup by an ID they already possess, not a browsable list, so
    it can't be used to enumerate other schools' transactions. Rate-limited
    to make brute-forcing the (already hard-to-guess) receipt code
    impractical.
    """
    txn = find_unmatched_transaction(db, trans_id)
    return MpesaTransactionLookup(
        id=txn.id,
        trans_id=txn.trans_id,
        trans_time=txn.trans_time.isoformat() if txn.trans_time else None,
        amount=str(txn.amount),
        bill_ref_number=txn.bill_ref_number,
        msisdn=txn.msisdn,
        payer_name=txn.payer_name,
        status=txn.status.value,
    )


@router.post("/reconciliation/{transaction_id}/match")
def match_c2b_transaction(
    transaction_id: str,
    data: MatchTransactionRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
    school_id: str = Depends(get_school_scope),
):
    """Attaches a stray, unmatched C2B transaction to a specific invoice in
    the caller's own school, recording it as a confirmed payment."""
    txn = match_transaction_to_invoice(
        db,
        transaction_id=transaction_id,
        invoice_id=data.invoice_id,
        school_id=school_id,
        actor_user_id=user.user_id,
    )
    return {"status": txn.status.value, "matched_payment_id": txn.matched_payment_id}
