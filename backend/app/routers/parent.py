from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, CurrentUser
from app.schemas.parent import ParentStudentView, ParentInvoiceView
from app.models.student import Student, StudentGuardian
from app.models.invoice import Invoice

router = APIRouter(prefix="/api/parent", tags=["parent"], dependencies=[Depends(get_current_user)])


def _require_parent(user: CurrentUser) -> None:
    if user.role != "PARENT":
        raise HTTPException(403, "This endpoint is for parent accounts only")


@router.get("/students", response_model=list[ParentStudentView])
def list_my_children(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    _school_id: str = Depends(get_school_scope),
):
    """
    Returns only the students linked to the CURRENT parent via student_guardians.
    This is the single most important query in the whole parent portal: it must
    never be filterable by a client-supplied id, and it deliberately does not
    take a school_id or student_id parameter — the link table is the only
    source of truth for what this parent is allowed to see.

    Depending on get_school_scope (in addition to get_current_user) is what
    sets the Postgres session variable Row-Level Security checks — without
    it, RLS has no tenant context for this request and correctly returns
    nothing, since the policies default-deny when unset.
    """
    _require_parent(user)

    links = db.execute(
        select(StudentGuardian).where(StudentGuardian.user_id == user.user_id)
    ).scalars().all()
    student_ids = [link.student_id for link in links]
    if not student_ids:
        return []

    students = db.execute(
        select(Student).where(Student.id.in_(student_ids))
    ).scalars().all()

    results = []
    for student in students:
        invoices = db.execute(
            select(Invoice).where(Invoice.student_id == student.id).order_by(Invoice.due_date.desc())
        ).scalars().all()

        balance_due = sum((inv.total_amount - inv.amount_paid for inv in invoices), Decimal("0"))

        results.append(
            ParentStudentView(
                id=student.id,
                full_name=student.full_name,
                admission_number=student.admission_number,
                class_name=student.school_class.name if student.school_class else None,
                invoices=[
                    ParentInvoiceView(
                        id=inv.id,
                        total_amount=inv.total_amount,
                        amount_paid=inv.amount_paid,
                        due_date=inv.due_date,
                        status=inv.status.value,
                    )
                    for inv in invoices
                ],
                balance_due=balance_due,
            )
        )

    return results
