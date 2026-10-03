"""What a parent sees after a payment is reversed."""

from decimal import Decimal

from app.core.deps import CurrentUser
from app.models.enums import GuardianLinkStatus, PaymentMethod
from app.models.student import StudentGuardian
from app.routers import parent as parent_router
from app.services import payment_service as ps
from tests.conftest import needs_db

pytestmark = needs_db


def test_reversed_payment_does_not_show_as_negative_line_to_parent(db, world):
    db.add(StudentGuardian(student_id=world.student.id, user_id=world.parent.id, relationship_type="mother",
                           status=GuardianLinkStatus.APPROVED))
    db.commit()
    keep = ps.record_confirmed_payment(db, world.school.id, world.student.id, Decimal("2000"), PaymentMethod.CASH, invoice_id=world.invoice.id)
    bad = ps.record_confirmed_payment(db, world.school.id, world.student.id, Decimal("5000"), PaymentMethod.CASH, invoice_id=world.invoice.id)
    ps.reverse_payment(db, bad.id, "entered twice")

    user = CurrentUser(user_id=world.parent.id, school_id=world.school.id, role="PARENT")
    views = parent_router.list_my_children(db=db, user=user, _school_id=world.school.id)
    amounts = [p.amount for child in views for inv in child.invoices for p in inv.payments]
    assert amounts == [Decimal("2000.00")] and all(a > 0 for a in amounts)
    assert views[0].invoices[0].amount_paid == Decimal("2000.00")
