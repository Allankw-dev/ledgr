from app.models.school import School, User  # noqa: F401
from app.models.student import Term, SchoolClass, Student, StudentGuardian  # noqa: F401
from app.models.invoice import FeeStructure, Invoice, InvoiceItem  # noqa: F401
from app.models.payment import Payment, AuditLog  # noqa: F401
from app.models.mpesa_transaction import MpesaTransaction  # noqa: F401
from app.models.message import Message  # noqa: F401
from app.models.payment_plan import PaymentPlan, PaymentPlanInstallment  # noqa: F401
from app.models.teacher_class_assignment import TeacherClassAssignment  # noqa: F401
from app.models.class_group_message import ClassGroupMessage  # noqa: F401
from app.models.class_group_read_state import ClassGroupReadState  # noqa: F401
