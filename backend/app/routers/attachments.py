from urllib.parse import quote  # noqa: F401

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.services import storage_service

# No login header here on purpose: <img src> and <a href> can't send one. The
# URL itself is the credential — a short-lived token minted by
# /api/class-groups/.../attachment-url only AFTER checking group membership.
router = APIRouter(prefix="/api/attachments", tags=["attachments"])


@router.get("/download")
def download_attachment(token: str):
    payload = storage_service.decode_download_token(token)
    path = storage_service.read_local_file(payload["key"])
    mime = payload["mime"]
    inline = mime in storage_service.IMAGE_MIMES
    return FileResponse(
        path,
        media_type=mime,
        filename=payload["name"],
        content_disposition_type="inline" if inline else "attachment",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=300",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )
