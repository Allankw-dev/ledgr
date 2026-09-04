from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, CurrentUser
from app.schemas.user import UpdateMyProfileRequest, MyProfileResponse
from app.models.school import User

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(get_current_user)])


@router.get("/me", response_model=MyProfileResponse)
def get_my_profile(db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    db_user = db.get(User, user.user_id)
    if not db_user:
        raise HTTPException(404, "User not found")
    return MyProfileResponse(
        id=db_user.id, email=db_user.email, full_name=db_user.full_name, phone=db_user.phone, role=db_user.role.value
    )


@router.patch("/me", response_model=MyProfileResponse)
def update_my_profile(
    data: UpdateMyProfileRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Self-service profile update — deliberately scoped to only ever touch the
    CALLER's own row (looked up by the JWT's user_id, never a client-supplied
    id), so there's no path for one user to edit another's contact details.
    Covers the "parent lost their phone / changed lines" case without needing
    a bursar to intervene.
    """
    db_user = db.get(User, user.user_id)
    if not db_user:
        raise HTTPException(404, "User not found")

    if data.phone is not None:
        db_user.phone = data.phone
    if data.full_name is not None:
        db_user.full_name = data.full_name

    db.commit()
    db.refresh(db_user)

    return MyProfileResponse(
        id=db_user.id, email=db_user.email, full_name=db_user.full_name, phone=db_user.phone, role=db_user.role.value
    )
