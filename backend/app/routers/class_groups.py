import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy import select, func, or_, case
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_school_scope, CurrentUser
from app.core.rate_limit import limiter
from app.schemas.class_group import (
    ClassGroupSummary,
    ClassGroupMessageResponse,
    SendClassGroupMessageRequest,
    AttachmentInfo,
    AttachmentUrlResponse,
    GroupMember,
    MentionInfo,
    MessageReceipt,
)
from app.models.school import User
from app.models.enums import UserRole, GuardianLinkStatus
from app.models.student import SchoolClass, Student, StudentGuardian
from app.models.teacher_class_assignment import TeacherClassAssignment
from app.models.class_group_message import ClassGroupMessage, ClassGroupMention
from app.models.class_group_read_state import ClassGroupReadState
from app.models.school import gen_uuid
from app.services import storage_service

router = APIRouter(prefix="/api/class-groups", tags=["class-groups"], dependencies=[Depends(get_current_user)])

STAFF_ROLES = ("SCHOOL_ADMIN", "BURSAR")

# How many messages a thread loads at once. This is a broadcast group, not
# a paginated table — like any chat app, what matters is a recent window
# to scroll from, not the full history up front.
MESSAGE_WINDOW = 200


def _accessible_class_ids(db: Session, user: CurrentUser, school_id: str) -> set[str]:
    """The set of grades this user is allowed to see/post in. Staff get
    every grade in the school — bursar's office is a member of every
    class group by design, same as it would be in a real WhatsApp group
    for each class. Teachers get only their assigned grades. Parents get
    only the grade(s) their own children are actually in."""
    if user.role in STAFF_ROLES:
        rows = db.execute(select(SchoolClass.id).where(SchoolClass.school_id == school_id)).scalars().all()
        return set(rows)

    if user.role == "TEACHER":
        rows = db.execute(
            select(TeacherClassAssignment.class_id).where(TeacherClassAssignment.teacher_user_id == user.user_id)
        ).scalars().all()
        return set(rows)

    if user.role == "PARENT":
        rows = db.execute(
            select(Student.class_id)
            .join(StudentGuardian, StudentGuardian.student_id == Student.id)
            .where(
                StudentGuardian.user_id == user.user_id,
                StudentGuardian.status == GuardianLinkStatus.APPROVED,  # pending/rejected links are not members
                Student.class_id.is_not(None),
            )
        ).scalars().all()
        return set(rows)

    return set()


def _require_class_access(db: Session, user: CurrentUser, school_id: str, class_id: str) -> None:
    if class_id not in _accessible_class_ids(db, user, school_id):
        raise HTTPException(403, "You don't have access to this class group")


EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _mark_class_group_read(db: Session, user_id: str, class_id: str) -> None:
    """Upsert — viewing the thread IS marking it read (and delivered), there's
    no separate action. Uses the database's clock (clock_timestamp, which
    unlike now() isn't frozen at transaction start) so it compares correctly
    with messages' server-side created_at."""
    stmt = pg_insert(ClassGroupReadState).values(
        id=gen_uuid(),
        user_id=user_id,
        class_id=class_id,
        last_read_at=func.clock_timestamp(),
        last_delivered_at=func.clock_timestamp(),
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "class_id"],
        set_={"last_read_at": func.clock_timestamp(), "last_delivered_at": func.clock_timestamp()},
    )
    db.execute(stmt)
    db.commit()


def mark_class_groups_delivered(db: Session, user: CurrentUser, school_id: str) -> None:
    """Records that this person's app just reached the server (their periodic
    notification poll, or opening the chat list) — so messages sent before now
    count as *delivered* to them, even if they haven't opened the chat yet.
    Writes only when a newer message exists, so frequent polling stays cheap."""
    class_ids = _accessible_class_ids(db, user, school_id)
    if not class_ids:
        return
    stmt = pg_insert(ClassGroupReadState).values(
        [
            {
                "id": gen_uuid(),
                "user_id": user.user_id,
                "class_id": cid,
                "last_read_at": EPOCH,  # "never read" placeholder for delivery-only rows
                "last_delivered_at": func.clock_timestamp(),
            }
            for cid in class_ids
        ]
    )
    # Only write when there's actually a newer message than the last delivery
    # we recorded — exact (a message is never missed) and, when nothing is new,
    # a poll costs no write at all.
    newer_message = (
        select(1)
        .where(
            ClassGroupMessage.class_id == ClassGroupReadState.class_id,
            ClassGroupMessage.created_at > ClassGroupReadState.last_delivered_at,
        )
        .correlate_except(ClassGroupMessage)
        .exists()
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["user_id", "class_id"],
        set_={"last_delivered_at": func.clock_timestamp()},
        where=or_(ClassGroupReadState.last_delivered_at.is_(None), newer_message),
    )
    db.execute(stmt)
    db.commit()


def _member_directory(db: Session, school_id: str, class_id: str) -> dict[str, dict]:
    """Everyone in this class group: user_id -> {name, role, subtitle}.
    Parents with an APPROVED link to a child in the grade, teachers assigned
    to it, and the school office (admin + bursar). Inactive accounts are
    excluded — they can't read, so they must not hold a message's ticks grey."""
    members: dict[str, dict] = {}

    parent_rows = db.execute(
        select(User.id, User.full_name, Student.full_name)
        .select_from(StudentGuardian)
        .join(Student, Student.id == StudentGuardian.student_id)
        .join(User, User.id == StudentGuardian.user_id)
        .where(
            Student.class_id == class_id,
            Student.school_id == school_id,
            StudentGuardian.status == GuardianLinkStatus.APPROVED,
            User.is_active.is_(True),
        )
        .order_by(Student.full_name)
    ).all()
    kids: dict[str, list[str]] = {}
    names: dict[str, str] = {}
    for uid, full_name, child in parent_rows:
        names[uid] = full_name
        kids.setdefault(uid, []).append(child.split(" ")[0])
    for uid, full_name in names.items():
        members[uid] = {"name": full_name, "role": "PARENT", "subtitle": "Parent of " + ", ".join(kids[uid])}

    teacher_rows = db.execute(
        select(User.id, User.full_name)
        .join(TeacherClassAssignment, TeacherClassAssignment.teacher_user_id == User.id)
        .where(TeacherClassAssignment.class_id == class_id, User.is_active.is_(True))
    ).all()
    for uid, full_name in teacher_rows:
        members[uid] = {"name": full_name, "role": "TEACHER", "subtitle": "Teacher"}

    staff_rows = db.execute(
        select(User.id, User.full_name, User.role).where(
            User.school_id == school_id,
            User.role.in_([UserRole.SCHOOL_ADMIN, UserRole.BURSAR]),
            User.is_active.is_(True),
        )
    ).all()
    for uid, full_name, role in staff_rows:
        members[uid] = {
            "name": full_name,
            "role": role.value,
            "subtitle": "School office" if role == UserRole.SCHOOL_ADMIN else "Bursar's office",
        }
    return members


def unread_class_group_count_for_user(db: Session, user: CurrentUser, school_id: str) -> int:
    """Read-only — used by the notifications summary endpoint, safe to
    poll frequently since it never marks anything as read itself.

    Two queries total regardless of how many grades the user belongs to —
    originally this ran one COUNT query per class in a loop, which is fine
    for a parent with one or two children but turns into real N+1 load at
    poll-every-25-seconds scale once a school has staff or teachers who
    are in a dozen+ groups. Fetching the (lightweight) candidate rows once
    and counting in Python is one round-trip either way."""
    class_ids = _accessible_class_ids(db, user, school_id)
    if not class_ids:
        return 0

    read_states = {
        rs.class_id: rs.last_read_at
        for rs in db.execute(
            select(ClassGroupReadState).where(
                ClassGroupReadState.user_id == user.user_id, ClassGroupReadState.class_id.in_(class_ids)
            )
        ).scalars().all()
    }

    # Bounded to a rolling 90-day window — unread counts don't need to
    # scan a full school year of history as classes accumulate messages,
    # and this keeps the query cost flat over time rather than growing
    # with the group's total lifetime message volume.
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    rows = db.execute(
        select(ClassGroupMessage.class_id, ClassGroupMessage.created_at).where(
            ClassGroupMessage.class_id.in_(class_ids),
            ClassGroupMessage.sender_user_id != user.user_id,
            ClassGroupMessage.created_at >= cutoff,
        )
    ).all()

    total = 0
    for class_id, created_at in rows:
        last_read = read_states.get(class_id)
        if last_read is None or created_at > last_read:
            total += 1
    return total


def _preview(msg: ClassGroupMessage) -> str:
    if msg.body:
        return msg.body[:120]
    if msg.attachment_mime and msg.attachment_mime in storage_service.IMAGE_MIMES:
        return "📷 Photo"
    return f"📎 {msg.attachment_name or 'File'}"[:120]


@router.get("", response_model=list[ClassGroupSummary])
def list_class_groups(
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    class_ids = _accessible_class_ids(db, user, school_id)
    if not class_ids:
        return []

    # Opening the chat list means the app just reached the server.
    mark_class_groups_delivered(db, user, school_id)

    classes = db.execute(
        select(SchoolClass).where(SchoolClass.id.in_(class_ids)).order_by(SchoolClass.name)
    ).scalars().all()

    # Latest message per class in one query (not N+1).
    latest_per_class: dict[str, ClassGroupMessage] = {}
    rows = db.execute(
        select(ClassGroupMessage)
        .where(ClassGroupMessage.class_id.in_(class_ids))
        .order_by(ClassGroupMessage.created_at.desc())
    ).scalars().all()
    for msg in rows:
        if msg.class_id not in latest_per_class:
            latest_per_class[msg.class_id] = msg

    # Unread count per class in one grouped query.
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    unread_rows = db.execute(
        select(ClassGroupMessage.class_id, func.count())
        .outerjoin(
            ClassGroupReadState,
            (ClassGroupReadState.class_id == ClassGroupMessage.class_id) & (ClassGroupReadState.user_id == user.user_id),
        )
        .where(
            ClassGroupMessage.class_id.in_(class_ids),
            ClassGroupMessage.sender_user_id != user.user_id,
            ClassGroupMessage.created_at >= cutoff,
            or_(ClassGroupReadState.last_read_at.is_(None), ClassGroupMessage.created_at > ClassGroupReadState.last_read_at),
        )
        .group_by(ClassGroupMessage.class_id)
    ).all()
    unread = {cid: n for cid, n in unread_rows}

    mention_rows = db.execute(
        select(ClassGroupMention.class_id, func.count()).where(
            ClassGroupMention.mentioned_user_id == user.user_id, ClassGroupMention.seen_at.is_(None)
        ).group_by(ClassGroupMention.class_id)
    ).all()
    mentions = {cid: n for cid, n in mention_rows}

    return [
        ClassGroupSummary(
            class_id=sc.id,
            class_name=sc.name,
            last_message_preview=_preview(latest_per_class[sc.id]) if sc.id in latest_per_class else None,
            last_message_at=latest_per_class[sc.id].created_at if sc.id in latest_per_class else None,
            unread_count=unread.get(sc.id, 0),
            unread_mentions=mentions.get(sc.id, 0),
        )
        for sc in classes
    ]


@router.get("/{class_id}/members", response_model=list[GroupMember])
def list_class_group_members(
    class_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Everyone in the group, for the @mention picker."""
    _require_class_access(db, user, school_id, class_id)
    directory = _member_directory(db, school_id, class_id)
    order = {"TEACHER": 0, "SCHOOL_ADMIN": 1, "BURSAR": 1, "PARENT": 2}
    people = [
        GroupMember(user_id=uid, name=m["name"], role=m["role"], subtitle=m["subtitle"])
        for uid, m in directory.items()
        if uid != user.user_id
    ]
    people.sort(key=lambda p: (order.get(p.role, 3), p.name.lower()))
    return people


def _serialize_messages(
    db: Session, school_id: str, class_id: str, viewer_id: str, messages: list[ClassGroupMessage]
) -> list[ClassGroupMessageResponse]:
    if not messages:
        return []

    directory = _member_directory(db, school_id, class_id)

    # Senders who are no longer members (role changed, deactivated…) still need a name.
    missing = {m.sender_user_id for m in messages if m.sender_user_id not in directory}
    extra: dict[str, dict] = {}
    if missing:
        for uid, name, role in db.execute(select(User.id, User.full_name, User.role).where(User.id.in_(missing))).all():
            extra[uid] = {"name": name, "role": role.value, "subtitle": None}

    read_states = {
        rs.user_id: rs
        for rs in db.execute(select(ClassGroupReadState).where(ClassGroupReadState.class_id == class_id)).scalars().all()
    }

    ids = [m.id for m in messages]
    mention_rows = db.execute(
        select(ClassGroupMention.message_id, ClassGroupMention.mentioned_user_id).where(ClassGroupMention.message_id.in_(ids))
    ).all()
    mentions_by_msg: dict[str, list[str]] = {}
    for mid, uid in mention_rows:
        mentions_by_msg.setdefault(mid, []).append(uid)

    out: list[ClassGroupMessageResponse] = []
    for m in messages:
        sender = directory.get(m.sender_user_id) or extra.get(m.sender_user_id) or {"name": "Unknown", "role": "PARENT", "subtitle": None}

        status = read_count = delivered_count = recipient_count = None
        if m.sender_user_id == viewer_id:
            recipients = [uid for uid in directory if uid != m.sender_user_id]
            recipient_count = len(recipients)
            read_count = delivered_count = 0
            for uid in recipients:
                rs = read_states.get(uid)
                if rs and rs.last_read_at and rs.last_read_at >= m.created_at:
                    read_count += 1
                    delivered_count += 1
                elif rs and rs.last_delivered_at and rs.last_delivered_at >= m.created_at:
                    delivered_count += 1
            if recipient_count and read_count == recipient_count:
                status = "read"
            elif recipient_count and delivered_count == recipient_count:
                status = "delivered"
            else:
                status = "sent"

        mentioned = mentions_by_msg.get(m.id, [])
        out.append(
            ClassGroupMessageResponse(
                id=m.id,
                class_id=m.class_id,
                sender_user_id=m.sender_user_id,
                sender_name=sender["name"],
                sender_role=sender["role"],
                sender_subtitle=sender["subtitle"],
                body=m.body,
                created_at=m.created_at,
                attachment=(
                    AttachmentInfo(
                        name=m.attachment_name or "file",
                        mime=m.attachment_mime or "application/octet-stream",
                        size=m.attachment_size or 0,
                        is_image=(m.attachment_mime in storage_service.IMAGE_MIMES),
                    )
                    if m.attachment_key
                    else None
                ),
                mentions=[
                    MentionInfo(user_id=uid, name=(directory.get(uid) or extra.get(uid) or {"name": "Member"})["name"])
                    for uid in mentioned
                    if uid in directory or uid in extra
                ],
                mentions_me=viewer_id in mentioned,
                status=status,
                read_count=read_count,
                delivered_count=delivered_count,
                recipient_count=recipient_count,
            )
        )
    return out


@router.get("/{class_id}/messages", response_model=list[ClassGroupMessageResponse])
def list_class_group_messages(
    class_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _require_class_access(db, user, school_id, class_id)

    rows = db.execute(
        select(ClassGroupMessage)
        .where(ClassGroupMessage.class_id == class_id)
        .order_by(ClassGroupMessage.created_at.desc())
        .limit(MESSAGE_WINDOW)
    ).scalars().all()
    rows.reverse()

    result = _serialize_messages(db, school_id, class_id, user.user_id, rows)

    # Viewing IS reading: mark the thread read/delivered, and this person's
    # unseen @mentions in it as seen.
    db.execute(
        ClassGroupMention.__table__.update()
        .where(
            ClassGroupMention.class_id == class_id,
            ClassGroupMention.mentioned_user_id == user.user_id,
            ClassGroupMention.seen_at.is_(None),
        )
        .values(seen_at=func.clock_timestamp())
    )
    _mark_class_group_read(db, user.user_id, class_id)

    return result


def _create_message(
    db: Session,
    school_id: str,
    class_id: str,
    user: CurrentUser,
    body: str,
    mention_user_ids: list[str],
    mention_all: bool,
    upload: "storage_service.ValidatedUpload | None" = None,
) -> ClassGroupMessageResponse:
    body = (body or "").strip()
    if not body and upload is None:
        raise HTTPException(422, "Write a message or attach a file")
    if len(body) > 4000:
        raise HTTPException(422, "Message is too long (max 4000 characters)")

    directory = _member_directory(db, school_id, class_id)

    if mention_all:
        if user.role == "PARENT":
            raise HTTPException(403, "Only teachers and the school office can mention everyone")
        targets = {uid for uid in directory if uid != user.user_id}
    else:
        targets = {uid for uid in mention_user_ids if uid != user.user_id}
        if not targets <= set(directory):
            raise HTTPException(422, "You can only mention people who are in this group")

    attachment_key = storage_service.store_file(school_id, class_id, upload) if upload else None

    message = ClassGroupMessage(
        school_id=school_id,
        class_id=class_id,
        sender_user_id=user.user_id,
        body=body,
        attachment_key=attachment_key,
        attachment_name=upload.filename if upload else None,
        attachment_mime=upload.mime if upload else None,
        attachment_size=upload.size if upload else None,
    )
    db.add(message)
    db.flush()
    for uid in targets:
        db.add(ClassGroupMention(school_id=school_id, class_id=class_id, message_id=message.id, mentioned_user_id=uid))
    db.commit()
    db.refresh(message)

    return _serialize_messages(db, school_id, class_id, user.user_id, [message])[0]


@router.post("/{class_id}/messages", response_model=ClassGroupMessageResponse, status_code=201)
@limiter.limit("30/minute")
def send_class_group_message(
    request: Request,
    class_id: str,
    data: SendClassGroupMessageRequest,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _require_class_access(db, user, school_id, class_id)
    return _create_message(db, school_id, class_id, user, data.body, data.mention_user_ids, data.mention_all)


@router.post("/{class_id}/messages/upload", response_model=ClassGroupMessageResponse, status_code=201)
@limiter.limit("12/minute")
def send_class_group_message_with_file(
    request: Request,
    class_id: str,
    file: UploadFile = File(...),
    body: str = Form(""),
    mention_user_ids: str = Form(""),
    mention_all: bool = Form(False),
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Send a photo or file (optionally with a caption and @mentions)."""
    _require_class_access(db, user, school_id, class_id)

    max_bytes = storage_service.settings.max_upload_mb * 1024 * 1024
    content = file.file.read(max_bytes + 1)  # never buffer more than the cap
    upload = storage_service.validate_upload(file.filename, content)

    ids = [i.strip() for i in mention_user_ids.split(",") if i.strip()][:50]
    return _create_message(db, school_id, class_id, user, body, ids, mention_all, upload)


@router.get("/{class_id}/messages/{message_id}/attachment-url", response_model=AttachmentUrlResponse)
def get_attachment_url(
    class_id: str,
    message_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Membership is checked HERE; the URL returned is short-lived and is
    what the browser uses to actually fetch the bytes."""
    _require_class_access(db, user, school_id, class_id)
    msg = db.execute(
        select(ClassGroupMessage).where(ClassGroupMessage.id == message_id, ClassGroupMessage.class_id == class_id)
    ).scalar_one_or_none()
    if not msg or not msg.attachment_key:
        raise HTTPException(404, "Attachment not found")
    return AttachmentUrlResponse(
        url=storage_service.signed_download_url(msg.attachment_key, msg.attachment_name or "file", msg.attachment_mime or ""),
        name=msg.attachment_name or "file",
        mime=msg.attachment_mime or "application/octet-stream",
        size=msg.attachment_size or 0,
        is_image=msg.attachment_mime in storage_service.IMAGE_MIMES,
        expires_in=storage_service.settings.attachment_url_ttl_seconds,
    )


@router.get("/{class_id}/messages/{message_id}/receipts", response_model=list[MessageReceipt])
def get_message_receipts(
    class_id: str,
    message_id: str,
    school_id: str = Depends(get_school_scope),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """"Message info" — who has read / received a message. Visible to the
    sender and to the school office only (a parent can't see who else read
    another parent's message)."""
    _require_class_access(db, user, school_id, class_id)
    msg = db.execute(
        select(ClassGroupMessage).where(ClassGroupMessage.id == message_id, ClassGroupMessage.class_id == class_id)
    ).scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "Message not found")
    if msg.sender_user_id != user.user_id and user.role not in STAFF_ROLES:
        raise HTTPException(403, "Only the sender or the school office can see who read a message")

    directory = _member_directory(db, school_id, class_id)
    states = {
        rs.user_id: rs
        for rs in db.execute(select(ClassGroupReadState).where(ClassGroupReadState.class_id == class_id)).scalars().all()
    }
    receipts = []
    for uid, m in directory.items():
        if uid == msg.sender_user_id:
            continue
        rs = states.get(uid)
        read = bool(rs and rs.last_read_at and rs.last_read_at >= msg.created_at)
        delivered = read or bool(rs and rs.last_delivered_at and rs.last_delivered_at >= msg.created_at)
        receipts.append(
            MessageReceipt(user_id=uid, name=m["name"], role=m["role"], subtitle=m["subtitle"], read=read, delivered=delivered)
        )
    receipts.sort(key=lambda r: (not r.read, not r.delivered, r.name.lower()))
    return receipts
