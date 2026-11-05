"""Erasing a parent's own account (the "delete my account" request in Privacy & data).

WHAT IS REMOVED: the sign-in identity (name, email, phone, password, 2FA, sessions), the links between the parent
and their children, the parent's messages to the school, their private chats (unless a safeguarding report was
filed on that chat), their posts in class group chats, and their opt-in/read state.

WHAT IS KEPT, and why: payments, invoices, receipts and the audit log. Schools must keep financial records for
tax and audit, and those rows point at the user id. The user row stays, stripped of every personal detail, so
those records remain internally consistent but no longer identify a person. This is the "legal obligation"
exception to erasure; the Privacy Policy says so in plain words. The child's own record belongs to the school
(the data controller): a parent who wants that changed asks the school.

The caller commits.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from sqlalchemy import delete, or_, select

from app.core.message_crypto import DecryptionError, decrypt_text
from app.core.phone import phone_key
from app.core.security import hash_password
from app.models.class_group_message import ClassGroupMention, ClassGroupMessage
from app.models.class_group_read_state import ClassGroupReadState
from app.models.direct_message import DirectBlock, DirectConversation, DirectMessage, DirectReport
from app.models.message import Message
from app.models.refresh_token import RefreshToken
from app.models.school import User
from app.models.student import GuardianInvite, StudentGuardian
from app.models.typing_status import TypingStatus
from app.models.webauthn import WebAuthnChallenge, WebAuthnCredential
from app.services import storage_service
from app.services.audit_service import log_audit

logger = logging.getLogger(__name__)


def _direct_attachment_key(msg: DirectMessage) -> str | None:
    if not msg.attachment_enc:
        return None
    try:
        import json

        meta = json.loads(decrypt_text(msg.attachment_enc, msg.conversation_id, msg.id + "#att", msg.sender_user_id))
        return meta.get("key")
    except (DecryptionError, ValueError):
        return None


def erase_parent_account(db, user: User) -> list[str]:
    """Removes the parent's personal data as described above. Returns the storage keys of files to delete AFTER
    the caller commits (deleting a file is not undoable, so it must not happen if the transaction fails)."""
    uid = user.id
    old_email, old_phone = user.email, user.phone
    files: list[str] = []

    # Private chats: delete the whole conversation, except one a safeguarding report was filed on.
    conv_ids = db.execute(
        select(DirectConversation.id).where(DirectConversation.parent_user_id == uid)
    ).scalars().all()
    if conv_ids:
        reported = set(
            db.execute(select(DirectReport.conversation_id).where(DirectReport.conversation_id.in_(conv_ids))).scalars()
        )
        doomed = [c for c in conv_ids if c not in reported]
        if doomed:
            for msg in db.execute(select(DirectMessage).where(DirectMessage.conversation_id.in_(doomed))).scalars():
                key = _direct_attachment_key(msg)
                if key:
                    files.append(key)
            db.execute(delete(DirectMessage).where(DirectMessage.conversation_id.in_(doomed)))
            db.execute(delete(DirectConversation).where(DirectConversation.id.in_(doomed)))
    db.execute(delete(DirectBlock).where(or_(DirectBlock.blocker_user_id == uid, DirectBlock.blocked_user_id == uid)))

    # Class group chat: remove what the parent posted (and the files), and their read/mention state.
    posts = db.execute(select(ClassGroupMessage).where(ClassGroupMessage.sender_user_id == uid)).scalars().all()
    post_ids = [p.id for p in posts]
    files.extend(p.attachment_key for p in posts if p.attachment_key)
    if post_ids:
        db.execute(delete(ClassGroupMention).where(ClassGroupMention.message_id.in_(post_ids)))
        db.execute(delete(ClassGroupMessage).where(ClassGroupMessage.id.in_(post_ids)))
    db.execute(delete(ClassGroupMention).where(ClassGroupMention.mentioned_user_id == uid))
    db.execute(delete(ClassGroupReadState).where(ClassGroupReadState.user_id == uid))

    # Messages to the school, typing state, children links, sign-in material.
    db.execute(delete(Message).where(Message.parent_user_id == uid))
    db.execute(delete(TypingStatus).where(TypingStatus.parent_user_id == uid))
    db.execute(delete(StudentGuardian).where(StudentGuardian.user_id == uid))
    db.execute(delete(WebAuthnCredential).where(WebAuthnCredential.user_id == uid))
    db.execute(delete(WebAuthnChallenge).where(WebAuthnChallenge.user_id == uid))
    db.execute(delete(RefreshToken).where(RefreshToken.user_id == uid))

    # Contact details the school typed in for this parent, so a later sign-up can't be pre-approved from them.
    invite_filter = []
    if old_email and not old_email.lower().endswith("@phone.ledgr.invalid"):
        invite_filter.append(GuardianInvite.email == old_email.lower())
    key = phone_key(old_phone)
    if key:
        invite_filter.append(GuardianInvite.phone.in_([old_phone, key]))
    if invite_filter:
        db.execute(delete(GuardianInvite).where(or_(*invite_filter)))

    # Strip the identity. The row stays so payments and audit entries keep a valid pointer.
    user.email = f"deleted-{uid}@deleted.ledgr.invalid"
    user.full_name = "Deleted user"
    user.phone = None
    user.password_hash = hash_password(secrets.token_urlsafe(32))
    user.is_active = False
    user.totp_enabled = False
    user.totp_secret = None
    user.token_version = (user.token_version or 0) + 1
    user.email_opt_out = True
    user.deleted_at = datetime.now(timezone.utc)

    if user.school_id:
        # No personal details in the audit entry: just the fact, so the school can show the request was honoured.
        log_audit(db, user.school_id, "ACCOUNT_ERASED", "user", uid, user_id=None)
    return files


def delete_files(keys: list[str]) -> None:
    for key in keys:
        storage_service.delete_object(key)
