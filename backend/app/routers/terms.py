from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, require_roles
from app.schemas.term import CreateTermRequest, TermResponse, CreateClassRequest, ClassResponse
from app.models.student import Term, SchoolClass

router = APIRouter(prefix="/api/terms", tags=["terms"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[TermResponse])
def list_terms(school_id: str = Depends(get_school_scope), db: Session = Depends(get_db)):
    return db.execute(
        select(Term).where(Term.school_id == school_id).order_by(Term.start_date.desc())
    ).scalars().all()


@router.post("", response_model=TermResponse, status_code=201)
def create_term(
    data: CreateTermRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user=Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    term = Term(school_id=school_id, **data.model_dump())
    db.add(term)
    db.commit()
    db.refresh(term)
    return term


classes_router = APIRouter(prefix="/api/classes", tags=["classes"], dependencies=[Depends(get_current_user)])


@classes_router.get("", response_model=list[ClassResponse])
def list_classes(school_id: str = Depends(get_school_scope), db: Session = Depends(get_db)):
    return db.execute(
        select(SchoolClass).where(SchoolClass.school_id == school_id).order_by(SchoolClass.name)
    ).scalars().all()


@classes_router.post("", response_model=ClassResponse, status_code=201)
def create_class(
    data: CreateClassRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    _user=Depends(require_roles("SCHOOL_ADMIN", "BURSAR")),
):
    school_class = SchoolClass(school_id=school_id, **data.model_dump())
    db.add(school_class)
    db.commit()
    db.refresh(school_class)
    return school_class
