"""Privacy controls: unsubscribe from optional email, and erase your own account.

Public (no sign-in): the unsubscribe endpoints, which are authorised by the signed token in the email link.
Signed in: reading your consent record and email choice, and deleting your account (parents only; staff accounts
are run by the school, so a staff member asks their school administrator).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_system_db
from app.core.deps import CurrentUser, get_current_user, invalidate_user_state, require_roles
from app.core.rate_limit import limiter
from app.core.security import verify_password
from app.core.unsubscribe import decode_unsubscribe_token
from app.models.school import User
from app.services.account_deletion import delete_files, erase_parent_account

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


class TokenBody(BaseModel):
    token: str = Field(min_length=10, max_length=2000)


class EmailPreferenceBody(BaseModel):
    email_opt_out: bool


class DeleteAccountBody(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    confirm: str = Field(max_length=20)  # the person must type DELETE


def _set_opt_out(db: Session, token: str, opt_out: bool) -> dict:
    try:
        user_id = decode_unsubscribe_token(token)
    except ValueError:
        raise HTTPException(400, "This link is invalid or has expired. Sign in to Ledgr to change your email settings.")
    user = db.get(User, user_id)
    if not user or user.deleted_at:
        raise HTTPException(400, "This link is invalid or has expired.")
    if user.email_opt_out != opt_out:
        user.email_opt_out = opt_out
        user.email_opt_out_at = datetime.now(timezone.utc) if opt_out else None
        db.commit()
    return {"email_opt_out": user.email_opt_out}


@router.post("/unsubscribe")
@limiter.limit("30/minute")
def unsubscribe(request: Request, data: TokenBody, db: Session = Depends(get_system_db)):
    """Used by the /unsubscribe page, which asks the person to confirm first (so a mail scanner that opens the link
    can't unsubscribe anyone)."""
    return _set_opt_out(db, data.token, True)


@router.post("/unsubscribe/one-click")
@limiter.limit("60/minute")
def unsubscribe_one_click(request: Request, token: str, db: Session = Depends(get_system_db)):
    """RFC 8058 one-click: mail apps POST here when the person taps their own "Unsubscribe" button."""
    return _set_opt_out(db, token, True)


@router.post("/resubscribe")
@limiter.limit("30/minute")
def resubscribe(request: Request, data: TokenBody, db: Session = Depends(get_system_db)):
    """The "I clicked that by mistake" button on the unsubscribe page."""
    return _set_opt_out(db, data.token, False)


@router.get("/me")
def my_privacy_settings(db: Session = Depends(get_system_db), user: CurrentUser = Depends(get_current_user)):
    db_user = db.get(User, user.user_id)
    if not db_user:
        raise HTTPException(404, "User not found")
    return {
        "email_opt_out": db_user.email_opt_out,
        "terms_accepted_at": db_user.terms_accepted_at,
        "terms_version": db_user.terms_version,
    }


@router.put("/me/email-preferences")
def set_email_preferences(
    data: EmailPreferenceBody,
    db: Session = Depends(get_system_db),
    user: CurrentUser = Depends(get_current_user),
):
    db_user = db.get(User, user.user_id)
    if not db_user:
        raise HTTPException(404, "User not found")
    db_user.email_opt_out = data.email_opt_out
    db_user.email_opt_out_at = datetime.now(timezone.utc) if data.email_opt_out else None
    db.commit()
    return {"email_opt_out": db_user.email_opt_out}


@router.post("/me/delete-account")
@limiter.limit("5/minute")
def delete_my_account(
    request: Request,
    data: DeleteAccountBody,
    db: Session = Depends(get_system_db),
    user: CurrentUser = Depends(require_roles("PARENT")),
):
    """Erases the signed-in parent's personal data (see services/account_deletion.py for exactly what goes and what
    stays). Needs the password as well as the typed word DELETE, so someone borrowing an unlocked phone can't do it."""
    if data.confirm.strip().upper() != "DELETE":
        raise HTTPException(400, "Type DELETE to confirm.")
    db_user = db.get(User, user.user_id)
    if not db_user or db_user.deleted_at:
        raise HTTPException(404, "User not found")
    if not verify_password(data.password, db_user.password_hash):
        raise HTTPException(401, "Incorrect password")

    files = erase_parent_account(db, db_user)
    db.commit()
    invalidate_user_state(user.user_id)
    delete_files(files)  # after the commit: a file can't be un-deleted
    return {"deleted": True}
