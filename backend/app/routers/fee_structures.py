from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, require_roles
from app.schemas.fee_structure import CreateFeeStructureRequest, FeeStructureResponse, UpdateFeeStructureRequest
from app.models.invoice import FeeStructure, InvoiceItem
from app.services.audit_service import log_audit


def _fee_snapshot(fs: FeeStructure) -> dict:
    """The parts of a fee structure worth recording, as plain JSON."""
    return {
        "name": fs.name,
        "category": fs.category.value if hasattr(fs.category, "value") else str(fs.category),
        "amount": f"{Decimal(str(fs.amount)):.2f}",
        "term_id": fs.term_id,
        "class_id": fs.class_id,
        "is_mandatory": fs.is_mandatory,
    }


router = APIRouter(
    prefix="/api/fee-structures",
    tags=["fee-structures"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[FeeStructureResponse])
def list_fee_structures(
    term_id: str | None = None,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
):
    query = select(FeeStructure).where(FeeStructure.school_id == school_id)
    if term_id:
        query = query.where(FeeStructure.term_id == term_id)
    return db.execute(query).scalars().all()


@router.post("", response_model=FeeStructureResponse, status_code=201)
def create_fee_structure(
    data: CreateFeeStructureRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    actor=Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    fee_structure = FeeStructure(school_id=school_id, **data.model_dump())
    db.add(fee_structure)
    db.flush()  # need the id for the audit entry; still the same transaction
    log_audit(
        db,
        school_id=school_id,
        action="FEE_STRUCTURE_CREATED",
        entity_type="FeeStructure",
        entity_id=fee_structure.id,
        user_id=actor.user_id,
        metadata=_fee_snapshot(fee_structure),
    )
    db.commit()
    db.refresh(fee_structure)
    return fee_structure


@router.patch("/{fee_structure_id}", response_model=FeeStructureResponse)
def update_fee_structure(
    fee_structure_id: str,
    data: UpdateFeeStructureRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    actor=Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    """Safe to edit freely, even for a fee structure already used to
    generate invoices — InvoiceItem snapshots the amount at generation
    time (see invoice_service.py), so changing a fee structure here never
    retroactively alters an invoice that already went out. Only affects
    invoices generated AFTER this edit."""
    fee_structure = db.execute(
        select(FeeStructure).where(FeeStructure.id == fee_structure_id, FeeStructure.school_id == school_id)
    ).scalar_one_or_none()
    if not fee_structure:
        raise HTTPException(404, "Fee structure not found")

    # exclude_unset so an explicit class_id: null (meaning "all classes")
    # is distinguishable from the field simply not being sent at all.
    before = _fee_snapshot(fee_structure)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(fee_structure, field, value)
    after = _fee_snapshot(fee_structure)
    changes = {k: {"from": before[k], "to": after[k]} for k in after if before[k] != after[k]}
    if changes:
        log_audit(
            db,
            school_id=school_id,
            action="FEE_STRUCTURE_UPDATED",
            entity_type="FeeStructure",
            entity_id=fee_structure.id,
            user_id=actor.user_id,
            metadata={"name": after["name"], "changes": changes},
        )
    db.commit()
    db.refresh(fee_structure)
    return fee_structure


@router.delete("/{fee_structure_id}", status_code=204)
def delete_fee_structure(
    fee_structure_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    actor=Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    """Only deletable while nothing references it yet — once an invoice has
    been generated against a fee structure, InvoiceItem holds a foreign key
    to it, so deleting it would either fail on the DB constraint or orphan
    that invoice's breakdown. Deactivate by editing amount/is_mandatory
    instead once it's in use."""
    fee_structure = db.execute(
        select(FeeStructure).where(FeeStructure.id == fee_structure_id, FeeStructure.school_id == school_id)
    ).scalar_one_or_none()
    if not fee_structure:
        raise HTTPException(404, "Fee structure not found")

    in_use = db.execute(
        select(func.count()).select_from(InvoiceItem).where(InvoiceItem.fee_structure_id == fee_structure_id)
    ).scalar_one()
    if in_use:
        raise HTTPException(409, "This fee structure has already been used on invoices and can't be deleted")

    # Log first, with a snapshot — once the row is gone this is the only record it existed.
    log_audit(
        db,
        school_id=school_id,
        action="FEE_STRUCTURE_DELETED",
        entity_type="FeeStructure",
        entity_id=fee_structure.id,
        user_id=actor.user_id,
        metadata=_fee_snapshot(fee_structure),
    )
    db.delete(fee_structure)
    db.commit()
