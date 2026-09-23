from app.models.school import School, User  # noqa: F401
from app.models.student import Term, SchoolClass, Student, StudentGuardian, GuardianInvite  # noqa: F401
from app.models.invoice import FeeStructure, Invoice, InvoiceItem  # noqa: F401
from app.models.payment import Payment, AuditLog  # noqa: F401
from app.models.mpesa_transaction import MpesaTransaction  # noqa: F401
from app.models.message import Message  # noqa: F401
from app.models.payment_plan import PaymentPlan, PaymentPlanInstallment  # noqa: F401
from app.models.teacher_class_assignment import TeacherClassAssignment  # noqa: F401
from app.models.class_group_message import ClassGroupMessage  # noqa: F401
from app.models.class_group_read_state import ClassGroupReadState  # noqa: F401
from app.models.webauthn import WebAuthnCredential, WebAuthnChallenge  # noqa: F401
from app.models.typing_status import TypingStatus  # noqa: F401
from app.models.class_group_message import ClassGroupMention  # noqa: F401
from app.models.direct_message import DirectConversation, DirectMessage, DirectBlock, DirectReport  # noqa: F401
from app.models.refresh_token import RefreshToken  # noqa: F401
from app.models.job import Job  # noqa: F401
from app.models.idempotency import IdempotencyKey  # noqa: F401
