"""Social media asset library for admin dashboard (marketing team)."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy import func, select

from app.admin.roles import PROMO_MANAGER_ROLES, ROLE_OWNER
from app.api import supabase_repository as db
from app.db.engine import get_session_factory
from app.db.models.social_media import SocialMediaAsset
from app.services.social_hub_content import status_label

logger = logging.getLogger(__name__)

STORAGE_BUCKET = "social-media-assets"
MAX_FILE_BYTES = 100 * 1024 * 1024  # 100 MB per upload
STORAGE_QUOTA_BYTES = 10 * 1024 * 1024 * 1024  # 10 GB planning cap

ALLOWED_MIME_PREFIXES = ("image/", "video/")
ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
}


class SocialMediaError(Exception):
    """Social media library operation failed."""


def can_manage_social_media(role: str) -> bool:
    return role in PROMO_MANAGER_ROLES or role == ROLE_OWNER


def _safe_filename(name: str) -> str:
    base = re.sub(r"[^\w.\-]+", "_", (name or "file").strip())[:180]
    return base or "file"


def _size_label(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.2f} GB"


def storage_usage_bytes() -> int:
    factory = get_session_factory()
    if factory is None:
        return 0
    with factory() as session:
        total = session.scalar(
            select(func.coalesce(func.sum(SocialMediaAsset.file_size_bytes), 0)).where(
                SocialMediaAsset.deleted_at.is_(None)
            )
        )
        return int(total or 0)


def storage_usage_summary() -> Dict[str, Any]:
    used = storage_usage_bytes()
    remaining = max(0, STORAGE_QUOTA_BYTES - used)
    percent = min(100.0, (used / STORAGE_QUOTA_BYTES) * 100) if STORAGE_QUOTA_BYTES else 0.0
    return {
        "used_bytes": used,
        "quota_bytes": STORAGE_QUOTA_BYTES,
        "remaining_bytes": remaining,
        "used_label": _size_label(used),
        "quota_label": _size_label(STORAGE_QUOTA_BYTES),
        "remaining_label": _size_label(remaining),
        "percent": round(percent, 1),
    }


def list_assets(*, role: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    if not can_manage_social_media(role):
        raise SocialMediaError("You do not have access to the social media library.")

    factory = get_session_factory()
    if factory is None:
        raise SocialMediaError("DATABASE_URL is not configured.")

    with factory() as session:
        stmt = (
            select(SocialMediaAsset)
            .where(SocialMediaAsset.deleted_at.is_(None))
            .order_by(SocialMediaAsset.created_at.desc())
        )
        if status:
            stmt = stmt.where(SocialMediaAsset.status == status)
        rows = list(session.scalars(stmt.limit(200)).all())

    return [_serialize(row) for row in rows]


def get_asset(*, asset_id: str, role: str) -> SocialMediaAsset:
    if not can_manage_social_media(role):
        raise SocialMediaError("You do not have access to the social media library.")

    factory = get_session_factory()
    if factory is None:
        raise SocialMediaError("DATABASE_URL is not configured.")

    with factory() as session:
        row = session.get(SocialMediaAsset, asset_id)
        if row is None or row.deleted_at is not None:
            raise SocialMediaError("Asset not found.")
        session.expunge(row)
        return row


def upload_asset(
    *,
    filename: str,
    content_type: str,
    file_bytes: bytes,
    partner: str,
    caption: str,
    notes: str,
    uploaded_by: str,
    role: str,
) -> Dict[str, Any]:
    if not can_manage_social_media(role):
        raise SocialMediaError("You do not have permission to upload.")

    if not file_bytes:
        raise SocialMediaError("File is empty.")
    if len(file_bytes) > MAX_FILE_BYTES:
        raise SocialMediaError("File exceeds the 100 MB limit.")

    resolved_type = (content_type or "").strip().lower() or "application/octet-stream"
    if not resolved_type.startswith(ALLOWED_MIME_PREFIXES):
        if resolved_type not in ALLOWED_VIDEO_TYPES:
            raise SocialMediaError("Only image and video files are allowed.")

    used = storage_usage_bytes()
    if used + len(file_bytes) > STORAGE_QUOTA_BYTES:
        summary = storage_usage_summary()
        raise SocialMediaError(
            f"Storage limit reached ({summary['quota_label']}). "
            f"{summary['remaining_label']} left — delete posted assets first."
        )

    asset_id = uuid4()
    safe_name = _safe_filename(filename)
    storage_path = f"assets/{asset_id.hex}/{safe_name}"

    try:
        client = db.get_supabase_client()
        client.storage.from_(STORAGE_BUCKET).upload(
            storage_path,
            file_bytes,
            file_options={"content-type": resolved_type, "upsert": "false"},
        )
    except Exception as exc:
        logger.exception("Social media upload to storage failed")
        raise SocialMediaError(
            "Could not store file. Confirm the social-media-assets Storage bucket exists "
            f"and SUPABASE_SERVICE_KEY is set. ({exc})"
        ) from exc

    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    if factory is None:
        raise SocialMediaError("DATABASE_URL is not configured.")

    with factory() as session:
        row = SocialMediaAsset(
            id=asset_id,
            partner=(partner or "").strip(),
            caption=(caption or "").strip(),
            notes=(notes or "").strip(),
            status="new",
            original_filename=safe_name,
            content_type=resolved_type,
            file_size_bytes=len(file_bytes),
            storage_path=storage_path,
            uploaded_by=uploaded_by,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _serialize(row)


def update_asset(
    *,
    asset_id: str,
    role: str,
    status: Optional[str] = None,
    partner: Optional[str] = None,
    caption: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    if not can_manage_social_media(role):
        raise SocialMediaError("You do not have permission to update assets.")

    if status is not None and status not in {"new", "ready", "posted"}:
        raise SocialMediaError("Invalid status.")

    factory = get_session_factory()
    if factory is None:
        raise SocialMediaError("DATABASE_URL is not configured.")

    now = datetime.now(timezone.utc)
    with factory() as session:
        row = session.get(SocialMediaAsset, asset_id)
        if row is None or row.deleted_at is not None:
            raise SocialMediaError("Asset not found.")
        if status is not None:
            row.status = status
        if partner is not None:
            row.partner = partner.strip()
        if caption is not None:
            row.caption = caption.strip()
        if notes is not None:
            row.notes = notes.strip()
        row.updated_at = now
        session.commit()
        session.refresh(row)
        return _serialize(row)


def download_asset(*, asset_id: str, role: str) -> Tuple[bytes, str, str]:
    row = get_asset(asset_id=asset_id, role=role)
    try:
        client = db.get_supabase_client()
        data = client.storage.from_(STORAGE_BUCKET).download(row.storage_path)
    except Exception as exc:
        logger.exception("Social media download failed for %s", asset_id)
        raise SocialMediaError(f"Could not download file: {exc}") from exc
    return data, row.original_filename, row.content_type


def soft_delete_asset(*, asset_id: str, role: str, deleted_by: str) -> Dict[str, Any]:
    if not can_manage_social_media(role):
        raise SocialMediaError("You do not have permission to delete assets.")

    factory = get_session_factory()
    if factory is None:
        raise SocialMediaError("DATABASE_URL is not configured.")

    now = datetime.now(timezone.utc)
    with factory() as session:
        row = session.get(SocialMediaAsset, asset_id)
        if row is None or row.deleted_at is not None:
            raise SocialMediaError("Asset not found.")
        row.deleted_at = now
        row.deleted_by = deleted_by
        row.updated_at = now
        session.commit()
        return {"id": str(row.id), "filename": row.original_filename, "deleted": True}


def _serialize(row: SocialMediaAsset) -> Dict[str, Any]:
    return {
        "id": str(row.id),
        "partner": row.partner,
        "caption": row.caption,
        "notes": row.notes,
        "status": row.status,
        "status_label": status_label(row.status),
        "original_filename": row.original_filename,
        "content_type": row.content_type,
        "file_size_bytes": row.file_size_bytes,
        "file_size_label": _size_label(row.file_size_bytes),
        "is_image": row.content_type.startswith("image/"),
        "is_video": row.content_type.startswith("video/"),
        "uploaded_by": row.uploaded_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
