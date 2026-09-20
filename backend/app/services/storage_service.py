"""File storage for chat attachments.

Two backends behind one interface, chosen by config:
  * Supabase Storage (production): SUPABASE_URL + SUPABASE_SERVICE_KEY set.
    The bucket stays PRIVATE; every download is a short-lived signed URL that
    our API only hands out after checking the caller is in the class group.
  * Local disk (development): files under UPLOAD_DIR, downloaded through
    /api/attachments/download using our own short-lived signed token.

Uploads are validated before anything is stored: size cap, an allow-list of
file types, and a magic-byte check so a renamed executable can't pass as a
photo. The stored MIME type is derived from the validated type — never taken
from the client — and non-images are always served as forced downloads.
"""

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"

# extension -> (mime, kind).  kind: image | pdf | office | ole | text
ALLOWED_TYPES: dict[str, tuple[str, str]] = {
    "jpg": ("image/jpeg", "image"),
    "jpeg": ("image/jpeg", "image"),
    "png": ("image/png", "image"),
    "gif": ("image/gif", "image"),
    "webp": ("image/webp", "image"),
    "pdf": ("application/pdf", "pdf"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "office"),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "office"),
    "pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", "office"),
    "doc": ("application/msword", "ole"),
    "xls": ("application/vnd.ms-excel", "ole"),
    "ppt": ("application/vnd.ms-powerpoint", "ole"),
    "txt": ("text/plain", "text"),
    "csv": ("text/csv", "text"),
}
IMAGE_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


@dataclass
class ValidatedUpload:
    filename: str
    mime: str
    size: int
    content: bytes


def _magic_ok(kind: str, ext: str, head: bytes, content: bytes) -> bool:
    if kind == "image":
        if ext in ("jpg", "jpeg"):
            return head.startswith(b"\xff\xd8\xff")
        if ext == "png":
            return head.startswith(b"\x89PNG\r\n\x1a\n")
        if ext == "gif":
            return head.startswith((b"GIF87a", b"GIF89a"))
        if ext == "webp":
            return head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    if kind == "pdf":
        return head.startswith(b"%PDF-")
    if kind == "office":
        return head.startswith(b"PK\x03\x04")
    if kind == "ole":
        return head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    if kind == "text":
        if b"\x00" in content[:4096]:
            return False
        try:
            content[:65536].decode("utf-8")
        except UnicodeDecodeError:
            return False
        return True
    return False


def clean_filename(name: str) -> str:
    base = Path(name.replace("\\", "/")).name
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip().strip(".")
    return (base or "file")[:120]


def validate_upload(filename: str | None, content: bytes) -> ValidatedUpload:
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) == 0:
        raise HTTPException(400, "That file is empty")
    if len(content) > max_bytes:
        raise HTTPException(413, f"File is too large (max {settings.max_upload_mb} MB)")

    safe_name = clean_filename(filename or "file")
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    if ext not in ALLOWED_TYPES:
        raise HTTPException(415, "This file type isn't allowed. Send photos, PDFs, Office documents, or text files.")

    mime, kind = ALLOWED_TYPES[ext]
    if not _magic_ok(kind, ext, content[:16], content):
        raise HTTPException(415, "That file doesn't look like a valid " + ext.upper() + " file")
    return ValidatedUpload(filename=safe_name, mime=mime, size=len(content), content=content)


def _use_supabase() -> bool:
    return bool(settings.supabase_url and settings.supabase_service_key)


def _new_key(school_id: str, class_id: str, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"{school_id}/{class_id}/{uuid.uuid4().hex}.{ext}"


def _local_path(key: str) -> Path:
    root = Path(settings.upload_dir).resolve()
    path = (root / key).resolve()
    if root not in path.parents:  # path-traversal guard
        raise HTTPException(400, "Invalid file reference")
    return path


def store_file(school_id: str, class_id: str, upload: ValidatedUpload) -> str:
    key = _new_key(school_id, class_id, upload.filename)
    if _use_supabase():
        url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{settings.supabase_storage_bucket}/{key}"
        try:
            resp = httpx.post(
                url,
                content=upload.content,
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                    "apikey": settings.supabase_service_key,
                    "Content-Type": upload.mime,
                    "x-upsert": "false",
                },
                timeout=30,
            )
        except httpx.HTTPError:
            logger.exception("Supabase Storage upload failed")
            raise HTTPException(503, "File storage is unavailable right now. Please try again.")
        if resp.status_code >= 300:
            logger.error("Supabase Storage upload rejected: %s %s", resp.status_code, resp.text[:200])
            raise HTTPException(503, "File storage is unavailable right now. Please try again.")
    else:
        path = _local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(upload.content)
    return key


def _download_token(key: str, name: str, mime: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(seconds=settings.attachment_url_ttl_seconds)
    return jwt.encode(
        {"purpose": "attachment", "key": key, "name": name, "mime": mime, "exp": exp},
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


def decode_download_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(403, "This download link is invalid or has expired")
    if payload.get("purpose") != "attachment":
        raise HTTPException(403, "This download link is invalid or has expired")
    return payload


def signed_download_url(key: str, name: str, mime: str) -> str:
    """Short-lived URL the browser can use directly in <img src> / <a href>."""
    ttl = settings.attachment_url_ttl_seconds
    if _use_supabase():
        sign_url = (
            f"{settings.supabase_url.rstrip('/')}/storage/v1/object/sign/{settings.supabase_storage_bucket}/{key}"
        )
        try:
            resp = httpx.post(
                sign_url,
                json={"expiresIn": ttl},
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                    "apikey": settings.supabase_service_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            signed = resp.json()["signedURL"]
        except (httpx.HTTPError, KeyError, ValueError):
            logger.exception("Supabase Storage signing failed")
            raise HTTPException(503, "File storage is unavailable right now. Please try again.")
        full = f"{settings.supabase_url.rstrip('/')}/storage/v1{signed}"
        if mime not in IMAGE_MIMES:
            full += ("&" if "?" in full else "?") + "download=" + quote(name)
        return full
    return f"/api/attachments/download?token={_download_token(key, name, mime)}"


def read_local_file(key: str) -> Path:
    path = _local_path(key)
    if not path.is_file():
        raise HTTPException(404, "File not found")
    return path
