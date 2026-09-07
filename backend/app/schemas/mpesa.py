from pydantic import BaseModel, Field


class StkPushRequest(BaseModel):
    invoice_id: str
    phone_number: str = Field(description="Any common format — 07XX, +2547XX, 2547XX")


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
