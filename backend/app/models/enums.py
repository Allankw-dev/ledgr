import enum


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    SCHOOL_ADMIN = "SCHOOL_ADMIN"
    BURSAR = "BURSAR"
    PARENT = "PARENT"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"


class PaymentMethod(str, enum.Enum):
    MPESA = "MPESA"
    BANK_TRANSFER = "BANK_TRANSFER"
    CASH = "CASH"
    CARD = "CARD"
    CHEQUE = "CHEQUE"
    OTHER = "OTHER"


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    REVERSED = "REVERSED"


class MpesaTransactionStatus(str, enum.Enum):
    UNMATCHED = "UNMATCHED"  # no student found for the BillRefNumber the payer typed, or more than one
    MATCHED = "MATCHED"      # auto-matched (exactly one student) or manually matched by a bursar
    IGNORED = "IGNORED"      # bursar reviewed it and decided it isn't a real fee payment (e.g. wrong paybill)


class MessageSenderRole(str, enum.Enum):
    PARENT = "PARENT"
    STAFF = "STAFF"


class GuardianLinkStatus(str, enum.Enum):
    PENDING = "PENDING"    # parent self-requested, awaiting bursar review
    APPROVED = "APPROVED"  # bursar confirmed — full portal access
    REJECTED = "REJECTED"  # bursar declined — kept for audit, no access


class FeeCategory(str, enum.Enum):
    TUITION = "TUITION"
    TRANSPORT = "TRANSPORT"
    BOARDING = "BOARDING"
    MEALS = "MEALS"
    ACTIVITY = "ACTIVITY"
    EXAM = "EXAM"
    UNIFORM = "UNIFORM"
    OTHER = "OTHER"
