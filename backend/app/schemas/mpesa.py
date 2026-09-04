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
