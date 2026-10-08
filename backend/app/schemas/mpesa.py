from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class StkPushRequest(BaseModel):
    # Exactly one of these: pay toward ONE invoice, or toward a student's whole
    # outstanding balance (the money is then applied to their oldest open
    # invoice first — see payment_service.resolve_mpesa_callback).
    invoice_id: str | None = None
    student_id: str | None = None
    phone_number: str = Field(description="Any common format — 07XX, +2547XX, 2547XX")
    amount: Decimal | None = Field(
        default=None,
        gt=0,
        description="How much to pay now, in whole shillings. Omit to pay the full remaining balance.",
    )

    @model_validator(mode="after")
    def _exactly_one_target(self):
        if bool(self.invoice_id) == bool(self.student_id):
            raise ValueError("Send either invoice_id or student_id (not both, not neither)")
        return self


class StkPushResponse(BaseModel):
    checkout_request_id: str
    message: str


# Shape of the payload Safaricom POSTs to our callback URL. Documented at
# https://developer.safaricom.co.ke/APIs/MpesaExpressSimulate — deliberately
# permissive (most fields optional) since we only strictly need a few of
# them, and Safaricom's own docs note the exact shape has changed before.
class StkCallback(BaseModel):
    MerchantRequestID: str
    CheckoutRequestID: str
    ResultCode: int
    ResultDesc: str
    CallbackMetadata: dict | None = None


class StkCallbackBody(BaseModel):
    stkCallback: StkCallback


class MpesaCallbackPayload(BaseModel):
    Body: StkCallbackBody


# Shape of the payload Safaricom POSTs to our C2B validation/confirmation
# URLs when someone pays the paybill directly (not via our STK push) —
# documented at https://developer.safaricom.co.ke/APIs/CustomerToBusiness.
# Deliberately permissive here too, for the same reason as MpesaCallbackPayload.
class C2BPayload(BaseModel):
    TransID: str
    TransTime: str | None = None
    TransAmount: str
    BusinessShortCode: str | None = None
    BillRefNumber: str | None = None
    MSISDN: str | None = None
    FirstName: str | None = None
    MiddleName: str | None = None
    LastName: str | None = None


class MpesaTransactionLookup(BaseModel):
    id: str
    trans_id: str
    trans_time: str | None
    amount: str
    bill_ref_number: str | None
    msisdn: str | None
    payer_name: str | None
    status: str


class MatchTransactionRequest(BaseModel):
    invoice_id: str
