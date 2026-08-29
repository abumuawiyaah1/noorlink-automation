from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.nav_catalog import FINANCE_CATEGORY
from app.admin.roles import (
    DOCUMENTS_VIEW_ROLES,
    ROLE_ADMIN,
    has_role,
    session_role,
    session_username,
)
from app.admin.views.base import _client_ip
from app.db.engine import get_session_factory
from app.services.admin_document_vault import (
    ACCESS_LEVELS,
    CATEGORIES,
    DocumentVaultError,
    can_delete_documents,
    can_upload_documents,
    download_document,
    list_documents,
    soft_delete_document,
    upload_document,
)


class DocumentVaultView(BaseView):
    name = "Documents"
    icon = "fa-solid fa-folder-open"
    category = FINANCE_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, DOCUMENTS_VIEW_ROLES)

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    @expose("/documents", identity="document-vault", methods=["GET", "POST"])
    async def vault(self, request: Request):
        role = session_role(request)
        category = (request.query_params.get("category") or "").strip().lower() or None
        year_raw = (request.query_params.get("year") or "").strip()
        year = int(year_raw) if year_raw.isdigit() else None

        # Download via ?download=<id> so we don't register a second menu route
        # (SQLAdmin menu calls url_for on every @expose identity without path params).
        download_id = (request.query_params.get("download") or "").strip()
        if request.method == "GET" and download_id:
            try:
                data, filename, content_type = download_document(
                    document_id=download_id, role=role
                )
                _audit(
                    request,
                    action="document_download",
                    record_id=download_id,
                    new_values={"filename": filename},
                )
                return Response(
                    content=data,
                    media_type=content_type,
                    headers={
                        "Content-Disposition": f'attachment; filename="{filename}"',
                        "Cache-Control": "no-store",
                    },
                )
            except DocumentVaultError as exc:
                request.session["flash_error"] = str(exc)
                return RedirectResponse(request.url_for("admin:document-vault"), status_code=302)

        if request.method == "POST":
            form = await request.form()
            action = str(form.get("action") or "upload").strip().lower()

            if action == "delete":
                if not can_delete_documents(role):
                    request.session["flash_error"] = "Only admins can delete documents."
                    return RedirectResponse(request.url_for("admin:document-vault"), status_code=302)
                try:
                    result = soft_delete_document(
                        document_id=str(form.get("document_id") or ""),
                        role=role,
                        deleted_by=session_username(request),
                    )
                    _audit(
                        request,
                        action="document_soft_delete",
                        record_id=result["id"],
                        new_values=result,
                    )
                    request.session["flash_success"] = f"Archived “{result['title']}” (soft delete)."
                except DocumentVaultError as exc:
                    request.session["flash_error"] = str(exc)
                return RedirectResponse(request.url_for("admin:document-vault"), status_code=302)

            if not can_upload_documents(role):
                request.session["flash_error"] = "You do not have permission to upload."
                return RedirectResponse(request.url_for("admin:document-vault"), status_code=302)

            upload = form.get("file")
            file_bytes = b""
            filename = ""
            content_type = "application/octet-stream"
            if upload is not None and hasattr(upload, "read"):
                file_bytes = await upload.read()
                filename = getattr(upload, "filename", "") or "file"
                content_type = getattr(upload, "content_type", None) or content_type

            year_form = str(form.get("document_year") or "").strip()
            document_year = int(year_form) if year_form.isdigit() else None

            try:
                result = upload_document(
                    title=str(form.get("title") or ""),
                    category=str(form.get("category") or ""),
                    access_level=str(form.get("access_level") or "vault"),
                    description=str(form.get("description") or ""),
                    document_year=document_year,
                    filename=filename,
                    content_type=content_type,
                    file_bytes=file_bytes,
                    uploaded_by=session_username(request),
                    role=role,
                )
                _audit(
                    request,
                    action="document_upload",
                    record_id=result["id"],
                    new_values={
                        "title": result["title"],
                        "category": result["category"],
                        "access_level": result["access_level"],
                        "filename": result["original_filename"],
                    },
                )
                request.session["flash_success"] = f"Uploaded “{result['title']}”."
            except DocumentVaultError as exc:
                request.session["flash_error"] = str(exc)
            return RedirectResponse(request.url_for("admin:document-vault"), status_code=302)

        try:
            documents = list_documents(role=role, category=category, year=year)
        except DocumentVaultError as exc:
            documents = []
            request.session["flash_error"] = str(exc)

        return await self.templates.TemplateResponse(
            request,
            "document_vault.html",
            {
                "documents": documents,
                "categories": CATEGORIES,
                "access_levels": ACCESS_LEVELS,
                "filter_category": category or "",
                "filter_year": year_raw,
                "can_upload": can_upload_documents(role),
                "can_delete": can_delete_documents(role),
                "is_admin": role == ROLE_ADMIN,
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )


def _audit(request: Request, *, action: str, record_id: str, new_values: dict) -> None:
    session_factory = get_session_factory()
    if session_factory is None:
        return
    with session_factory() as session:
        write_audit_log(
            session,
            admin_user_id=request.session.get("admin_user_id"),
            admin_username=session_username(request),
            action=action,
            table_name="company_documents",
            record_id=record_id,
            new_values=new_values,
            ip_address=_client_ip(request),
        )
