"""Private one-to-one chats between a teacher and a parent.

Rules:
  * A teacher can chat with parents whose (approved) child is in a grade the
    teacher is assigned to; a parent can chat with their child's teachers.
  * Only the two participants can read a conversation. Other staff and the
    school admin cannot; someone else's conversation id looks like it doesn't exist.
  * Message text is stored encrypted (AES-256-GCM, see core/message_crypto.py).
  * Sending re-checks the relationship every time, so a teacher who is
    unassigned from a grade can't keep messaging that grade's parents.
"""

import json
import logging
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import select, update, func, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, require_roles, CurrentUser
from app.core.message_crypto import encrypt_text, decrypt_text, encrypt_bytes, decrypt_bytes, DecryptionError
from app.core.rate_limit import limiter
from app.models.direct_message import DirectConversation, DirectMessage, DirectBlock, DirectReport
from app.models.enums import GuardianLinkStatus, UserRole
from app.models.school import User, gen_uuid
from app.models.student import SchoolClass, Student, StudentGuardian
from app.models.teacher_class_assignment import TeacherClassAssignment
from app.services import storage_service
from app.services.audit_service import log_audit
from app.schemas.direct import (
    BlockRequest,
    DirectAttachmentInfo,
    ReportDetail,
    ReportEvidenceMessage,
    ReportPerson,
    ReportRequest,
    ReportSummary,
    UpdateReportRequest,
    DirectContact,
    DirectConversationOut,
    DirectMessageOut,
    SendDirectMessageRequest,
    StartConversationRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/direct", tags=["direct-messages"], dependencies=[Depends(get_current_user)])

MESSAGE_WINDOW = 300


def _require_chat_role(user: CurrentUser) -> None:
    if user.role not in ("TEACHER", "PARENT"):
        raise HTTPException(403, "Private chats are between teachers and parents")


def _eligible_contacts(db: Session, user: CurrentUser, school_id: str) -> dict[str, dict]:
    """user_id -> {name, role, subtitle} for everyone this person may chat with."""
    contacts: dict[str, dict] = {}

    if user.role == "TEACHER":
        rows = db.execute(
            select(User.id, User.full_name, Student.full_name, SchoolClass.name)
            .select_from(StudentGuardian)
            .join(Student, Student.id == StudentGuardian.student_id)
            .join(User, User.id == StudentGuardian.user_id)
            .join(SchoolClass, SchoolClass.id == Student.class_id)
            .join(
                TeacherClassAssignment,
                (TeacherClassAssignment.class_id == Student.class_id) & (TeacherClassAssignment.teacher_user_id == user.user_id),
            )
            .where(
                StudentGuardian.status == GuardianLinkStatus.APPROVED,
                User.is_active.is_(True),
                User.role == UserRole.PARENT,
                Student.school_id == school_id,
            )
            .order_by(Student.full_name)
        ).all()
        kids: dict[str, list[str]] = {}
        for uid, name, child, cls in rows:
            contacts.setdefault(uid, {"name": name, "role": "PARENT"})
            kids.setdefault(uid, []).append(f"{child.split(' ')[0]} ({cls})")
        for uid, k in kids.items():
            contacts[uid]["subtitle"] = "Parent of " + ", ".join(dict.fromkeys(k))
    else:
        rows = db.execute(
            select(User.id, User.full_name, SchoolClass.name)
            .select_from(StudentGuardian)
            .join(Student, Student.id == StudentGuardian.student_id)
            .join(SchoolClass, SchoolClass.id == Student.class_id)
            .join(TeacherClassAssignment, TeacherClassAssignment.class_id == Student.class_id)
            .join(User, User.id == TeacherClassAssignment.teacher_user_id)
            .where(
                StudentGuardian.user_id == user.user_id,
                StudentGuardian.status == GuardianLinkStatus.APPROVED,
                User.is_active.is_(True),
                Student.school_id == school_id,
            )
        ).all()
        classes: dict[str, list[str]] = {}
        for uid, name, cls in rows:
            contacts.setdefault(uid, {"name": name, "role": "TEACHER"})
            classes.setdefault(uid, []).append(cls)
        for uid, c in classes.items():
            contacts[uid]["subtitle"] = "Teacher · " + ", ".join(dict.fromkeys(c))
    return contacts


def _get_conversation(db: Session, user: CurrentUser, conversation_id: str) -> DirectConversation:
    """404 (not 403) for someone else's conversation: don't confirm it exists."""
    conv = db.execute(
        select(DirectConversation).where(
            DirectConversation.id == conversation_id,
            (DirectConversation.teacher_user_id == user.user_id) | (DirectConversation.parent_user_id == user.user_id),
        )
    ).scalar_one_or_none()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return conv


def _other_id(conv: DirectConversation, me: str) -> str:
    return conv.parent_user_id if conv.teacher_user_id == me else conv.teacher_user_id


def _read_text(msg: DirectMessage) -> str:
    try:
        return decrypt_text(msg.body_enc, msg.conversation_id, msg.id, msg.sender_user_id)
    except DecryptionError:
        logger.error("Could not decrypt direct message %s (key missing/rotated out, or the row was tampered with)", msg.id)
        return "⚠️ This message can't be displayed."


def _attachment_meta(msg: DirectMessage) -> dict | None:
    if not msg.attachment_enc:
        return None
    try:
        return json.loads(decrypt_text(msg.attachment_enc, msg.conversation_id, msg.id + "#att", msg.sender_user_id))
    except (DecryptionError, ValueError):
        logger.error("Could not decrypt attachment metadata for direct message %s", msg.id)
        return {"key": None, "name": "file", "mime": "application/octet-stream", "size": 0}


def _read_message(msg: DirectMessage) -> tuple[str, DirectAttachmentInfo | None, bool]:
    """(text, attachment info, deleted). Deleted messages expose nothing."""
    if msg.deleted_at:
        return "", None, True
    meta = _attachment_meta(msg)
    att = (
        DirectAttachmentInfo(
            name=meta["name"], mime=meta["mime"], size=meta["size"], is_image=meta["mime"] in storage_service.IMAGE_MIMES
        )
        if meta
        else None
    )
    return _read_text(msg), att, False


def _preview(msg: DirectMessage) -> str:
    body, att, deleted = _read_message(msg)
    if deleted:
        return "This message was deleted"
    if body:
        return body[:80]
    if att:
        return "📷 Photo" if att.is_image else f"📎 {att.name}"[:80]
    return ""


def _block_sets(db: Session, me: str) -> tuple[set[str], set[str]]:
    """(people I've blocked, people who've blocked me)."""
    rows = db.execute(
        select(DirectBlock.blocker_user_id, DirectBlock.blocked_user_id).where(
            (DirectBlock.blocker_user_id == me) | (DirectBlock.blocked_user_id == me)
        )
    ).all()
    by_me = {blocked for blocker, blocked in rows if blocker == me}
    blocked_me = {blocker for blocker, blocked in rows if blocked == me}
    return by_me, blocked_me


def _assert_can_send(db: Session, user: CurrentUser, school_id: str, conv: DirectConversation) -> None:
    other = _other_id(conv, user.user_id)
    if other not in _eligible_contacts(db, user, school_id):
        raise HTTPException(403, "You can no longer message this person (they're no longer linked to your grade or child)")
    by_me, blocked_me = _block_sets(db, user.user_id)
    if other in by_me:
        raise HTTPException(403, "You've blocked this person. Unblock them to send messages.")
    if other in blocked_me:
        raise HTTPException(403, "You can't send messages in this chat right now.")


def _build_conversations(db: Session, user: CurrentUser, school_id: str, convs: list[DirectConversation]) -> list[DirectConversationOut]:
    if not convs:
        return []
    contacts = _eligible_contacts(db, user, school_id)
    by_me, blocked_me = _block_sets(db, user.user_id)
    ids = [c.id for c in convs]
    other_ids = [_other_id(c, user.user_id) for c in convs]
    people = {uid: (name, role) for uid, name, role in db.execute(select(User.id, User.full_name, User.role).where(User.id.in_(other_ids))).all()}

    last = {
        m.conversation_id: m
        for m in db.execute(
            select(DirectMessage)
            .where(DirectMessage.conversation_id.in_(ids))
            .order_by(DirectMessage.conversation_id, DirectMessage.created_at.desc())
            .distinct(DirectMessage.conversation_id)
        ).scalars().all()
    }
    unread = dict(
        db.execute(
            select(DirectMessage.conversation_id, func.count())
            .where(
                DirectMessage.conversation_id.in_(ids),
                DirectMessage.sender_user_id != user.user_id,
                DirectMessage.read_at.is_(None),
                DirectMessage.deleted_at.is_(None),
            )
            .group_by(DirectMessage.conversation_id)
        ).all()
    )

    out = []
    for c in convs:
        oid = _other_id(c, user.user_id)
        name, role = people.get(oid, ("Unknown", "PARENT"))
        m = last.get(c.id)
        out.append(
            DirectConversationOut(
                id=c.id,
                other_user_id=oid,
                other_name=name,
                other_role=role.value if hasattr(role, "value") else str(role),
                other_subtitle=contacts.get(oid, {}).get("subtitle", "Teacher" if user.role == "PARENT" else "Parent"),
                last_message_preview=(_preview(m) if m else None),
                last_message_at=m.created_at if m else None,
                unread_count=unread.get(c.id, 0),
                can_send=oid in contacts and oid not in by_me and oid not in blocked_me,
                blocked_by_me=oid in by_me,
            )
        )
    out.sort(key=lambda x: x.last_message_at.timestamp() if x.last_message_at else 0, reverse=True)
    return out


@router.get("/contacts", response_model=list[DirectContact])
def list_contacts(
    q: str = "",
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """The people you can start a private chat with (a teacher's list is the
    parents of their grades; a parent's list is their children's teachers)."""
    _require_chat_role(user)
    contacts = _eligible_contacts(db, user, school_id)
    by_me, blocked_me = _block_sets(db, user.user_id)
    for hidden in blocked_me:  # someone who blocked you silently drops out of your list
        contacts.pop(hidden, None)
    needle = q.strip().lower()

    convs = db.execute(
        select(DirectConversation).where(
            (DirectConversation.teacher_user_id == user.user_id) | (DirectConversation.parent_user_id == user.user_id)
        )
    ).scalars().all()
    by_other = {_other_id(c, user.user_id): c.id for c in convs}
    unread = dict(
        db.execute(
            select(DirectMessage.conversation_id, func.count())
            .where(
                DirectMessage.conversation_id.in_([c.id for c in convs] or [""]),
                DirectMessage.sender_user_id != user.user_id,
                DirectMessage.read_at.is_(None),
                DirectMessage.deleted_at.is_(None),
            )
            .group_by(DirectMessage.conversation_id)
        ).all()
    )

    result = [
        DirectContact(
            user_id=uid,
            name=c["name"],
            subtitle=c["subtitle"],
            conversation_id=by_other.get(uid),
            unread_count=unread.get(by_other.get(uid, ""), 0),
            blocked=uid in by_me,
        )
        for uid, c in contacts.items()
        if not needle or needle in c["name"].lower() or needle in c["subtitle"].lower()
    ]
    result.sort(key=lambda r: r.name.lower())
    return result[:200]


@router.get("/conversations", response_model=list[DirectConversationOut])
def list_conversations(
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _require_chat_role(user)
    convs = db.execute(
        select(DirectConversation).where(
            (DirectConversation.teacher_user_id == user.user_id) | (DirectConversation.parent_user_id == user.user_id)
        )
    ).scalars().all()
    return _build_conversations(db, user, school_id, list(convs))


@router.post("/conversations", response_model=DirectConversationOut)
def start_conversation(
    data: StartConversationRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Start (or reopen) a private chat with someone from your list."""
    _require_chat_role(user)
    if data.user_id not in _eligible_contacts(db, user, school_id):
        raise HTTPException(403, "You can only start a private chat with the parents of your grades (or your child's teachers)")

    if data.user_id in _block_sets(db, user.user_id)[1]:
        raise HTTPException(403, "You can't start a chat with this person right now")

    teacher_id, parent_id = (user.user_id, data.user_id) if user.role == "TEACHER" else (data.user_id, user.user_id)
    conv = db.execute(
        select(DirectConversation).where(
            DirectConversation.teacher_user_id == teacher_id, DirectConversation.parent_user_id == parent_id
        )
    ).scalar_one_or_none()
    if not conv:
        try:
            with db.begin_nested():
                conv = DirectConversation(school_id=school_id, teacher_user_id=teacher_id, parent_user_id=parent_id)
                db.add(conv)
                db.flush()
        except IntegrityError:  # created a moment ago by the other person
            conv = db.execute(
                select(DirectConversation).where(
                    DirectConversation.teacher_user_id == teacher_id, DirectConversation.parent_user_id == parent_id
                )
            ).scalar_one()
        db.commit()
    return _build_conversations(db, user, school_id, [conv])[0]


def _message_out(msg: DirectMessage, viewer_id: str) -> DirectMessageOut:
    body, att, deleted = _read_message(msg)
    status = None
    if msg.sender_user_id == viewer_id and not deleted:
        status = "read" if msg.read_at else "delivered" if msg.delivered_at else "sent"
    return DirectMessageOut(
        id=msg.id, conversation_id=msg.conversation_id, sender_user_id=msg.sender_user_id,
        body=body, created_at=msg.created_at, attachment=att, deleted=deleted, status=status,
    )


@router.get("/conversations/{conversation_id}/messages", response_model=list[DirectMessageOut])
def get_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    _school_id: str = Depends(get_school_scope),
):
    _require_chat_role(user)
    conv = _get_conversation(db, user, conversation_id)

    rows = db.execute(
        select(DirectMessage)
        .where(DirectMessage.conversation_id == conv.id)
        .order_by(DirectMessage.created_at.desc())
        .limit(MESSAGE_WINDOW)
    ).scalars().all()
    rows.reverse()
    result = [_message_out(m, user.user_id) for m in rows]

    # Opening the conversation = reading it (and it obviously reached this device).
    db.execute(
        update(DirectMessage)
        .where(
            DirectMessage.conversation_id == conv.id,
            DirectMessage.sender_user_id != user.user_id,
            DirectMessage.read_at.is_(None),
        )
        .values(read_at=func.clock_timestamp(), delivered_at=func.coalesce(DirectMessage.delivered_at, func.clock_timestamp()))
    )
    db.commit()
    return result


@router.post("/conversations/{conversation_id}/messages", response_model=DirectMessageOut, status_code=201)
@limiter.limit("60/minute")
def send_message(
    request: Request,
    conversation_id: str,
    data: SendDirectMessageRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _require_chat_role(user)
    conv = _get_conversation(db, user, conversation_id)
    _assert_can_send(db, user, school_id, conv)

    body = data.body.strip()
    if not body:
        raise HTTPException(422, "Write a message first")

    message_id = gen_uuid()
    token, version = encrypt_text(body, conv.id, message_id, user.user_id)
    msg = DirectMessage(
        id=message_id, school_id=school_id, conversation_id=conv.id, sender_user_id=user.user_id,
        body_enc=token, key_version=version,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return _message_out(msg, user.user_id)


@router.post("/conversations/{conversation_id}/messages/upload", response_model=DirectMessageOut, status_code=201)
@limiter.limit("12/minute")
def send_file(
    request: Request,
    conversation_id: str,
    file: UploadFile = File(...),
    body: str = Form(""),
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Send a photo or document. The file is validated (type allow-list, magic
    bytes, size cap), then ENCRYPTED before it is stored; even its name is
    kept encrypted. Nobody gets a link to the stored object — the API decrypts
    it for the two people in the conversation."""
    _require_chat_role(user)
    conv = _get_conversation(db, user, conversation_id)
    _assert_can_send(db, user, school_id, conv)

    caption = (body or "").strip()
    if len(caption) > 4000:
        raise HTTPException(422, "Caption is too long (max 4000 characters)")

    max_bytes = storage_service.settings.max_upload_mb * 1024 * 1024
    upload = storage_service.validate_upload(file.filename, file.file.read(max_bytes + 1))

    message_id = gen_uuid()
    storage_key = f"dm/{school_id}/{conv.id}/{uuid.uuid4().hex}.enc"
    storage_service.put_object(storage_key, encrypt_bytes(upload.content, conv.id, message_id, user.user_id))

    meta = json.dumps({"key": storage_key, "name": upload.filename, "mime": upload.mime, "size": upload.size})
    attachment_token, _ = encrypt_text(meta, conv.id, message_id + "#att", user.user_id)
    body_token, version = encrypt_text(caption, conv.id, message_id, user.user_id)
    msg = DirectMessage(
        id=message_id, school_id=school_id, conversation_id=conv.id, sender_user_id=user.user_id,
        body_enc=body_token, key_version=version, attachment_enc=attachment_token,
    )
    db.add(msg)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage_service.delete_object(storage_key)  # don't leave an orphaned file behind
        raise
    db.refresh(msg)
    return _message_out(msg, user.user_id)


@router.get("/conversations/{conversation_id}/messages/{message_id}/attachment")
def download_attachment(
    conversation_id: str,
    message_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    _school_id: str = Depends(get_school_scope),
):
    _require_chat_role(user)
    conv = _get_conversation(db, user, conversation_id)
    msg = db.execute(
        select(DirectMessage).where(DirectMessage.id == message_id, DirectMessage.conversation_id == conv.id)
    ).scalar_one_or_none()
    if not msg or msg.deleted_at or not msg.attachment_enc:
        raise HTTPException(404, "Attachment not found")
    meta = _attachment_meta(msg)
    if not meta or not meta.get("key"):
        raise HTTPException(404, "Attachment not found")
    try:
        data = decrypt_bytes(storage_service.get_object(meta["key"]), conv.id, msg.id, msg.sender_user_id)
    except DecryptionError:
        logger.error("Could not decrypt file for direct message %s", msg.id)
        raise HTTPException(500, "This file can't be opened")
    inline = meta["mime"] in storage_service.IMAGE_MIMES
    return Response(
        content=data,
        media_type=meta["mime"],
        headers={
            "Content-Disposition": f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(meta['name'])}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/conversations/{conversation_id}/messages/{message_id}", status_code=204)
def delete_message(
    conversation_id: str,
    message_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    _school_id: str = Depends(get_school_scope),
):
    """Delete for everyone. Only the sender can. The text is overwritten and the
    stored file removed — the chat shows "This message was deleted"."""
    _require_chat_role(user)
    conv = _get_conversation(db, user, conversation_id)
    msg = db.execute(
        select(DirectMessage).where(DirectMessage.id == message_id, DirectMessage.conversation_id == conv.id)
    ).scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "Message not found")
    if msg.sender_user_id != user.user_id:
        raise HTTPException(403, "You can only delete your own messages")
    if msg.deleted_at:
        return Response(status_code=204)

    meta = _attachment_meta(msg)
    msg.body_enc, msg.key_version = encrypt_text("", conv.id, msg.id, msg.sender_user_id)
    msg.attachment_enc = None
    msg.deleted_at = datetime.now(timezone.utc)
    db.commit()
    if meta and meta.get("key"):
        storage_service.delete_object(meta["key"])
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Blocking
# ---------------------------------------------------------------------------
@router.get("/blocks", response_model=list[DirectContact])
def list_blocks(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    _school_id: str = Depends(get_school_scope),
):
    _require_chat_role(user)
    by_me, _ = _block_sets(db, user.user_id)
    if not by_me:
        return []
    rows = db.execute(select(User.id, User.full_name).where(User.id.in_(by_me))).all()
    return [DirectContact(user_id=uid, name=name, subtitle="Blocked", blocked=True) for uid, name in rows]


@router.post("/blocks", status_code=204)
def block_user(
    data: BlockRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Stops both of you sending in your private chat. They aren't told."""
    _require_chat_role(user)
    has_chat = db.execute(
        select(DirectConversation.id).where(
            (
                (DirectConversation.teacher_user_id == user.user_id) & (DirectConversation.parent_user_id == data.user_id)
            )
            | ((DirectConversation.parent_user_id == user.user_id) & (DirectConversation.teacher_user_id == data.user_id))
        )
    ).first()
    if not has_chat and data.user_id not in _eligible_contacts(db, user, school_id):
        raise HTTPException(404, "Person not found")
    db.execute(
        pg_insert(DirectBlock)
        .values(id=gen_uuid(), school_id=school_id, blocker_user_id=user.user_id, blocked_user_id=data.user_id)
        .on_conflict_do_nothing(index_elements=["blocker_user_id", "blocked_user_id"])
    )
    db.commit()
    return Response(status_code=204)


@router.delete("/blocks/{blocked_user_id}", status_code=204)
def unblock_user(
    blocked_user_id: str,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    _school_id: str = Depends(get_school_scope),
):
    _require_chat_role(user)
    db.execute(
        delete(DirectBlock).where(DirectBlock.blocker_user_id == user.user_id, DirectBlock.blocked_user_id == blocked_user_id)
    )
    db.commit()
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Reporting  (participants report; the school admin reviews)
# ---------------------------------------------------------------------------
REPORT_SNAPSHOT_MESSAGES = 30


@router.post("/conversations/{conversation_id}/report", status_code=201)
@limiter.limit("5/hour")
def report_conversation(
    request: Request,
    conversation_id: str,
    data: ReportRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Reports this chat to the school admin. A snapshot of the last messages
    is stored encrypted with the report, so the admin sees what was reported
    even if the sender deletes those messages afterwards. The admin sees only
    that snapshot — never the rest of the conversation."""
    _require_chat_role(user)
    conv = _get_conversation(db, user, conversation_id)
    other_id = _other_id(conv, user.user_id)

    recent = db.execute(
        select(DirectMessage)
        .where(DirectMessage.conversation_id == conv.id)
        .order_by(DirectMessage.created_at.desc())
        .limit(REPORT_SNAPSHOT_MESSAGES)
    ).scalars().all()
    recent.reverse()
    names = {uid: n for uid, n in db.execute(select(User.id, User.full_name).where(User.id.in_([user.user_id, other_id]))).all()}

    evidence = []
    for m in recent:
        body, att, deleted = _read_message(m)
        evidence.append(
            {
                "sender_name": names.get(m.sender_user_id, "Unknown"),
                "sender_is_reported": m.sender_user_id == other_id,
                "sent_at": m.created_at.isoformat(),
                "body": body,
                "attachment_name": att.name if att else None,
                "deleted_before_report": deleted,
            }
        )

    report_id = gen_uuid()
    ctx = f"report:{report_id}"
    evidence_token, _ = encrypt_text(json.dumps(evidence), ctx, report_id, user.user_id)
    details = (data.details or "").strip()
    details_token = encrypt_text(details, ctx, report_id + "#details", user.user_id)[0] if details else None

    db.add(
        DirectReport(
            id=report_id, school_id=school_id, conversation_id=conv.id, reporter_user_id=user.user_id,
            reported_user_id=other_id, category=data.category, details_enc=details_token, evidence_enc=evidence_token,
        )
    )
    log_audit(
        db, school_id=school_id, user_id=user.user_id, action="DIRECT_CHAT_REPORTED",
        entity_type="DirectReport", entity_id=report_id, metadata={"category": data.category},
    )
    db.commit()
    return {"id": report_id, "ok": True}


def _person(people: dict, uid: str) -> ReportPerson:
    name, role = people.get(uid, ("Unknown", "PARENT"))
    return ReportPerson(id=uid, name=name, role=role.value if hasattr(role, "value") else str(role))


def _report_summary(r: DirectReport, people: dict) -> ReportSummary:
    return ReportSummary(
        id=r.id, created_at=r.created_at, status=r.status, category=r.category,
        reporter=_person(people, r.reporter_user_id), reported=_person(people, r.reported_user_id), resolved_at=r.resolved_at,
    )


@router.get("/reports", response_model=list[ReportSummary])
def list_reports(
    status: str | None = None,
    db: Session = Depends(get_db),
    _admin: CurrentUser = Depends(require_roles("SCHOOL_ADMIN")),
    _school_id: str = Depends(get_school_scope),
):
    stmt = select(DirectReport).order_by(DirectReport.created_at.desc()).limit(200)
    if status:
        stmt = stmt.where(DirectReport.status == status.upper())
    rows = db.execute(stmt).scalars().all()
    ids = {r.reporter_user_id for r in rows} | {r.reported_user_id for r in rows}
    people = {uid: (n, ro) for uid, n, ro in db.execute(select(User.id, User.full_name, User.role).where(User.id.in_(ids or {""}))).all()}
    return [_report_summary(r, people) for r in rows]


def _get_report(db: Session, report_id: str) -> DirectReport:
    r = db.execute(select(DirectReport).where(DirectReport.id == report_id)).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Report not found")
    return r


@router.get("/reports/{report_id}", response_model=ReportDetail)
def get_report(
    report_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    admin: CurrentUser = Depends(require_roles("SCHOOL_ADMIN")),
):
    r = _get_report(db, report_id)
    ctx = f"report:{r.id}"
    try:
        evidence = json.loads(decrypt_text(r.evidence_enc, ctx, r.id, r.reporter_user_id))
        details = decrypt_text(r.details_enc, ctx, r.id + "#details", r.reporter_user_id) if r.details_enc else None
    except DecryptionError:
        logger.error("Could not decrypt chat report %s", r.id)
        raise HTTPException(500, "This report can't be opened")
    people = {uid: (n, ro) for uid, n, ro in db.execute(select(User.id, User.full_name, User.role).where(User.id.in_([r.reporter_user_id, r.reported_user_id]))).all()}
    log_audit(
        db, school_id=school_id, user_id=admin.user_id, action="DIRECT_REPORT_VIEWED",
        entity_type="DirectReport", entity_id=r.id,
    )
    db.commit()
    base = _report_summary(r, people)
    return ReportDetail(
        **base.model_dump(), details=details, resolution_note=r.resolution_note,
        evidence=[ReportEvidenceMessage(**e) for e in evidence],
    )


@router.patch("/reports/{report_id}", response_model=ReportSummary)
def update_report(
    report_id: str,
    data: UpdateReportRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    admin: CurrentUser = Depends(require_roles("SCHOOL_ADMIN")),
):
    r = _get_report(db, report_id)
    r.status = data.status
    r.resolution_note = data.resolution_note
    if data.status in ("RESOLVED", "DISMISSED"):
        r.resolved_at, r.resolved_by = datetime.now(timezone.utc), admin.user_id
    else:
        r.resolved_at = r.resolved_by = None
    log_audit(
        db, school_id=school_id, user_id=admin.user_id, action="DIRECT_REPORT_UPDATED",
        entity_type="DirectReport", entity_id=r.id, metadata={"status": data.status},
    )
    db.commit()
    people = {uid: (n, ro) for uid, n, ro in db.execute(select(User.id, User.full_name, User.role).where(User.id.in_([r.reporter_user_id, r.reported_user_id]))).all()}
    return _report_summary(r, people)
