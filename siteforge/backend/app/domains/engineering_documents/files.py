import hashlib
from pathlib import Path

from fastapi import HTTPException

from app.config import settings
from .models import StoredFile

ALLOWED = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "text/plain": ".txt",
}


def root() -> Path:
    path = Path(settings.file_root).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def store_file(db, user, filename: str, content_type: str, data: bytes) -> StoredFile:
    if content_type not in ALLOWED:
        raise HTTPException(422, "File type is not allowed")
    if not data or len(data) > settings.max_upload_bytes:
        raise HTTPException(422, "File is empty or larger than the limit")
    safe_name = Path(filename or "file").name[:200] or "file"
    digest = hashlib.sha256(data).hexdigest()
    base = root()
    destination = (base / str(user.organization_id) / digest[:2] / digest).resolve()
    if not destination.is_relative_to(base):
        raise HTTPException(422, "Invalid storage path")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    row = StoredFile(
        organization_id=user.organization_id,
        sha256=digest,
        size=len(data),
        content_type=content_type,
        original_name=safe_name,
        storage_name=digest,
        created_by=user.id,
        scan_status="available",
    )
    db.add(row)
    db.flush()
    return row


def read_file(row: StoredFile) -> bytes:
    base = root()
    path = (base / str(row.organization_id) / row.sha256[:2] / row.storage_name).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise HTTPException(404, "File not found")
    return path.read_bytes()
