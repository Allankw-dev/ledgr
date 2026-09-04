from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, require_roles
from app.schemas.fee_structure import CreateFeeStructureRequest, FeeStructureResponse
from app.models.invoice import FeeStructure

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
    _user=Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    fee_structure = FeeStructure(school_id=school_id, **data.model_dump())
    db.add(fee_structure)
    db.commit()
    db.refresh(fee_structure)
    return fee_structure
