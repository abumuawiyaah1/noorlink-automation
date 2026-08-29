"""Company legal + accounting document vault (admin / finance / legal)."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy import select

from app.admin.roles import (
    DOCUMENTS_DELETE_ROLES,
    DOCUMENTS_UPLOAD_ROLES,
    DOCUMENTS_VIEW_ROLES,
    ROLE_ADMIN,
    ROLE_OWNER,
)
from app.api import supabase_repository as db
from app.db.engine import get_session_factory
from app.db.models.documents import CompanyDocument

logger = logging.getLogger(__name__)

STORAGE_BUCKET = "company-documents"
MAX_FILE_BYTES = 20 * 1024 * 1024  # 20 MB

CATEGORIES = (
    ("legal", "Legal"),
    ("accounting", "Accounting"),
    ("tax", "Tax"),
    ("contracts", "Contracts"),
    ("compliance", "Compliance"),
    ("other", "Other"),
)

ACCESS_LEVELS = (
    ("vault", "Vault (admin + finance + legal)"),
    ("admin_only", "Admin only (highly sensitive)"),
)

ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    ".txt": "text/plain",
}


class DocumentVaultError(Exception):
    """Document vault operation failed."""


def category_label(code: str) -> str:
    for key, label in CATEGORIES:
        if key == code:
            return label
    return code


def can_view_documents(role: str) -> bool:
    return role in DOCUMENTS_VIEW_ROLES or role == ROLE_OWNER


def can_upload_documents(role: str) -> bool:
    return role in DOCUMENTS_UPLOAD_ROLES or role == ROLE_OWNER


def can_delete_documents(role: str) -> bool:
    return role in DOCUMENTS_DELETE_ROLES or role == ROLE_OWNER


def can_view_document_row(*, role: str, access_level: str) -> bool:
    if role in (ROLE_ADMIN, ROLE_OWNER):
        return True
    if access_level == "admin_only":
        return False
    return role in DOCUMENTS_VIEW_ROLES


def _safe_filename(name: str) -> str:
    base = re.sub(r"[^\w.\-]+", "_", (name or "file").strip())[:180]
    return base or "file"


def _extension(filename: str) -> str:
    lower = filename.lower()
    for ext in ALLOWED_EXTENSIONS:
        if lower.endswith(ext):
            return ext
    return ""


def list_documents(
    *,
    role: str,
    category: Optional[str] = None,
    year: Optional[int] = None,
    include_deleted: bool = False,
) -> List[Dict[str, Any]]:
    if not can_view_documents(role):
        raise DocumentVaultError("You do not have access to the document vault.")

    factory = get_session_factory()
    if factory is None:
        raise DocumentVaultError("DATABASE_URL is not configured.")

    with factory() as session:
        stmt = select(CompanyDocument).order_by(CompanyDocument.created_at.desc())
        if not include_deleted:
            stmt = stmt.where(CompanyDocument.deleted_at.is_(None))
        if category:
            stmt = stmt.where(CompanyDocument.category == category)
        if year:
            stmt = stmt.where(CompanyDocument.document_year == year)
        rows = list(session.scalars(stmt.limit(500)).all())

    results: List[Dict[str, Any]] = []
    for row in rows:
        if not can_view_document_row(role=role, access_level=row.access_level):
            continue
        results.append(_serialize(row))
    return results


def get_document(*, document_id: str, role: str) -> CompanyDocument:
    if not can_view_documents(role):
        raise DocumentVaultError("You do not have access to the document vault.")

    factory = get_session_factory()
    if factory is None:
        raise DocumentVaultError("DATABASE_URL is not configured.")

    with factory() as session:
        row = session.get(CompanyDocument, document_id)
        if row is None or row.deleted_at is not None:
            raise DocumentVaultError("Document not found.")
        if not can_view_document_row(role=role, access_level=row.access_level):
            raise DocumentVaultError("This document is restricted to admins.")
        session.expunge(row)
        return row


def upload_document(
    *,
    title: str,
    category: str,
    access_level: str,
    description: str,
    document_year: Optional[int],
    filename: str,
    content_type: str,
    file_bytes: bytes,
    uploaded_by: str,
    role: str,
) -> Dict[str, Any]:
    if not can_upload_documents(role):
        raise DocumentVaultError("You do not have permission to upload documents.")

    title_clean = (title or "").strip()
    if len(title_clean) < 2:
        raise DocumentVaultError("Title is required.")

    category_clean = (category or "").strip().lower()
    if category_clean not in {c[0] for c in CATEGORIES}:
        raise DocumentVaultError("Invalid category.")

    access_clean = (access_level or "vault").strip().lower()
    if access_clean not in {a[0] for a in ACCESS_LEVELS}:
        raise DocumentVaultError("Invalid access level.")
    if access_clean == "admin_only" and role != ROLE_ADMIN:
        raise DocumentVaultError("Only admins can mark documents as admin-only.")

    if not file_bytes:
        raise DocumentVaultError("File is empty.")
    if len(file_bytes) > MAX_FILE_BYTES:
        raise DocumentVaultError("File exceeds the 20 MB limit.")

    ext = _extension(filename)
    if not ext:
        raise DocumentVaultError(
            "Unsupported file type. Allowed: PDF, images, Word, Excel, CSV, TXT."
        )
    resolved_type = content_type or ALLOWED_EXTENSIONS[ext]
    if resolved_type not in ALLOWED_EXTENSIONS.values() and not resolved_type.startswith("image/"):
        resolved_type = ALLOWED_EXTENSIONS[ext]

    year_val = document_year
    if year_val is not None and (year_val < 1990 or year_val > 2100):
        raise DocumentVaultError("Document year looks invalid.")

    doc_id = uuid4()
    safe_name = _safe_filename(filename)
    storage_path = f"{category_clean}/{doc_id.hex}/{safe_name}"

    try:
        client = db.get_supabase_client()
        client.storage.from_(STORAGE_BUCKET).upload(
            storage_path,
            file_bytes,
            file_options={"content-type": resolved_type, "upsert": "false"},
        )
    except Exception as exc:
        logger.exception("Document upload to storage failed")
        raise DocumentVaultError(
            "Could not store file. Confirm the company-documents Storage bucket exists "
            f"and SUPABASE_SERVICE_KEY is set. ({exc})"
        ) from exc

    factory = get_session_factory()
    if factory is None:
        raise DocumentVaultError("DATABASE_URL is not configured.")

    now = datetime.now(timezone.utc)
    with factory() as session:
        row = CompanyDocument(
            id=doc_id,
            title=title_clean,
            category=category_clean,
            access_level=access_clean,
            description=(description or "").strip() or None,
            document_year=year_val,
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


def download_document(*, document_id: str, role: str) -> Tuple[bytes, str, str]:
    row = get_document(document_id=document_id, role=role)
    try:
        client = db.get_supabase_client()
        data = client.storage.from_(STORAGE_BUCKET).download(row.storage_path)
    except Exception as exc:
        logger.exception("Document download failed for %s", document_id)
        raise DocumentVaultError(f"Could not download file: {exc}") from exc
    return data, row.original_filename, row.content_type


def soft_delete_document(*, document_id: str, role: str, deleted_by: str) -> Dict[str, Any]:
    if not can_delete_documents(role):
        raise DocumentVaultError("Only admins can delete documents.")

    factory = get_session_factory()
    if factory is None:
        raise DocumentVaultError("DATABASE_URL is not configured.")

    now = datetime.now(timezone.utc)
    with factory() as session:
        row = session.get(CompanyDocument, document_id)
        if row is None or row.deleted_at is not None:
            raise DocumentVaultError("Document not found.")
        row.deleted_at = now
        row.deleted_by = deleted_by
        row.updated_at = now
        session.commit()
        return {"id": str(row.id), "title": row.title, "deleted": True}


def _serialize(row: CompanyDocument) -> Dict[str, Any]:
    return {
        "id": str(row.id),
        "title": row.title,
        "category": row.category,
        "category_label": category_label(row.category),
        "access_level": row.access_level,
        "description": row.description,
        "document_year": row.document_year,
        "original_filename": row.original_filename,
        "content_type": row.content_type,
        "file_size_bytes": row.file_size_bytes,
        "file_size_label": _size_label(row.file_size_bytes),
        "uploaded_by": row.uploaded_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None,
    }


def _size_label(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"
