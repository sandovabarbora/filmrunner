"""Crew photo upload to Supabase Storage (FR-18).

Reference: https://supabase.com/docs/guides/storage/uploads/standard-uploads
(direct-to-bucket upload via the Storage REST API, service-role key).
"""

import uuid

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.production import ContactPhoto

# 256px, resized client-side before upload; this cap just guards the request itself.
MAX_PHOTO_BYTES = 300_000
ALLOWED_CONTENT_TYPES = {"image/jpeg": "jpg", "image/png": "png"}


class PhotoUploadNotConfigured(Exception):
    """Raised when no Supabase Storage credentials are set (INBOX item pending)."""


class PhotoUploadFailed(Exception):
    """Raised when Supabase Storage rejects or cannot be reached for the upload."""


def upload_contact_photo(contact_id: str, data: bytes, content_type: str) -> str:
    """Upload `data` as the given contact's avatar and return its public URL.

    Raises PhotoUploadNotConfigured if the bucket credentials are not set, or
    PhotoUploadFailed if Supabase Storage rejects the request or is unreachable.
    Overwrites any existing photo at the same path (`x-upsert`), so a re-upload
    needs no cleanup of the old file.
    """
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise PhotoUploadNotConfigured(
            "Photo upload is not configured yet; ask the founder to create the "
            "Supabase Storage 'avatars' bucket and set the service-role key (INBOX item)."
        )
    ext = ALLOWED_CONTENT_TYPES[content_type]
    path = f"{contact_id}.{ext}"
    base = settings.supabase_url.rstrip("/")
    upload_url = f"{base}/storage/v1/object/{settings.avatar_bucket}/{path}"
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
        "content-type": content_type,
        "x-upsert": "true",
    }
    try:
        resp = httpx.put(upload_url, content=data, headers=headers, timeout=10.0)
    except httpx.HTTPError as exc:
        raise PhotoUploadFailed(f"could not reach Supabase Storage: {exc}") from exc
    if resp.status_code >= 300:
        raise PhotoUploadFailed(f"Supabase Storage returned {resp.status_code}: {resp.text[:200]}")
    # Cache-bust: the storage path is stable (contact id + ext), so a re-upload
    # needs a new URL or the browser/CDN would keep showing the old image.
    version = uuid.uuid4().hex[:8]
    return f"{base}/storage/v1/object/public/{settings.avatar_bucket}/{path}?v={version}"


def store_contact_photo(db: Session, contact_id: str, data: bytes, content_type: str) -> str:
    """Store the avatar and return its public URL.

    Postgres is the default (nothing to configure); Supabase Storage is used
    only when its credentials are set. Either way the URL carries a version so
    a re-upload is never served from a stale cache.
    """
    settings = get_settings()
    if settings.supabase_url and settings.supabase_service_role_key:
        return upload_contact_photo(contact_id, data, content_type)
    version = uuid.uuid4().hex[:8]
    row = db.get(ContactPhoto, uuid.UUID(contact_id))
    if row is None:
        db.add(ContactPhoto(contact_id=uuid.UUID(contact_id), content_type=content_type, data=data, version=version))
    else:
        row.content_type, row.data, row.version = content_type, data, version
    db.flush()
    return f"{settings.public_base_url.rstrip('/')}/api/v1/public/contacts/{contact_id}/photo?v={version}"


def delete_contact_photo(db: Session, contact_id: uuid.UUID) -> None:
    row = db.get(ContactPhoto, contact_id)
    if row is not None:
        db.delete(row)
