from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.nav_catalog import MARKETING_CATEGORY
from app.admin.roles import PROMO_MANAGER_ROLES, has_role, session_username
from app.admin.views.base import _client_ip
from app.db.engine import get_session_factory
from app.services.admin_social_media import (
    SocialMediaError,
    can_manage_social_media,
    download_asset,
    list_assets,
    soft_delete_asset,
    storage_usage_summary,
    update_asset,
    upload_asset,
)
from app.services.social_hub_content import (
    SITE_BASE,
    SOCIAL_BRAND_ASSETS,
    SOCIAL_CAPTION_TEMPLATES,
    SOCIAL_POST_WORKFLOW,
    SOCIAL_QUICK_LINKS,
    STATUSES,
)


class SocialMediaHubView(BaseView):
    name = "Social media"
    icon = "fa-solid fa-share-nodes"
    category = MARKETING_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, PROMO_MANAGER_ROLES)

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    @expose("/social-media", identity="social-media-hub", methods=["GET", "POST"])
    async def hub(self, request: Request):
        role = str(request.session.get("admin_role") or "")
        status_filter = (request.query_params.get("status") or "").strip().lower() or None

        download_id = (request.query_params.get("download") or "").strip()
        if request.method == "GET" and download_id:
            try:
                data, filename, content_type = download_asset(asset_id=download_id, role=role)
                _audit(
                    request,
                    action="social_media_download",
                    record_id=download_id,
                    new_values={"filename": filename},
                )
                disposition = "attachment"
                return Response(
                    content=data,
                    media_type=content_type,
                    headers={
                        "Content-Disposition": f'{disposition}; filename="{filename}"',
                        "Cache-Control": "no-store",
                    },
                )
            except SocialMediaError as exc:
                request.session["flash_error"] = str(exc)
                return RedirectResponse(request.url_for("admin:social-media-hub"), status_code=302)

        preview_id = (request.query_params.get("preview") or "").strip()
        if request.method == "GET" and preview_id:
            try:
                data, _filename, content_type = download_asset(asset_id=preview_id, role=role)
                return Response(
                    content=data,
                    media_type=content_type,
                    headers={"Cache-Control": "private, max-age=3600"},
                )
            except SocialMediaError as exc:
                request.session["flash_error"] = str(exc)
                return RedirectResponse(request.url_for("admin:social-media-hub"), status_code=302)

        if request.method == "POST":
            form = await request.form()
            action = str(form.get("action") or "upload").strip().lower()

            if action == "delete":
                try:
                    result = soft_delete_asset(
                        asset_id=str(form.get("asset_id") or ""),
                        role=role,
                        deleted_by=session_username(request),
                    )
                    _audit(
                        request,
                        action="social_media_delete",
                        record_id=result["id"],
                        new_values=result,
                    )
                    request.session["flash_success"] = f"Removed “{result['filename']}” from the library."
                except SocialMediaError as exc:
                    request.session["flash_error"] = str(exc)
                return RedirectResponse(request.url_for("admin:social-media-hub"), status_code=302)

            if action == "update":
                try:
                    result = update_asset(
                        asset_id=str(form.get("asset_id") or ""),
                        role=role,
                        status=str(form.get("status") or "") or None,
                        partner=str(form.get("partner") or ""),
                        caption=str(form.get("caption") or ""),
                        notes=str(form.get("notes") or ""),
                    )
                    _audit(
                        request,
                        action="social_media_update",
                        record_id=result["id"],
                        new_values={"status": result["status"]},
                    )
                    request.session["flash_success"] = "Asset updated."
                except SocialMediaError as exc:
                    request.session["flash_error"] = str(exc)
                return RedirectResponse(request.url_for("admin:social-media-hub"), status_code=302)

            upload = form.get("file")
            file_bytes = b""
            filename = ""
            content_type = "application/octet-stream"
            if upload is not None and hasattr(upload, "read"):
                file_bytes = await upload.read()
                filename = getattr(upload, "filename", "") or "file"
                content_type = getattr(upload, "content_type", None) or content_type

            try:
                result = upload_asset(
                    filename=filename,
                    content_type=content_type,
                    file_bytes=file_bytes,
                    partner=str(form.get("partner") or ""),
                    caption=str(form.get("caption") or ""),
                    notes=str(form.get("notes") or ""),
                    uploaded_by=session_username(request),
                    role=role,
                )
                _audit(
                    request,
                    action="social_media_upload",
                    record_id=result["id"],
                    new_values={"filename": result["original_filename"]},
                )
                request.session["flash_success"] = f"Uploaded “{result['original_filename']}”."
            except SocialMediaError as exc:
                request.session["flash_error"] = str(exc)
            return RedirectResponse(request.url_for("admin:social-media-hub"), status_code=302)

        try:
            assets = list_assets(role=role, status=status_filter)
        except SocialMediaError as exc:
            assets = []
            request.session["flash_error"] = str(exc)

        usage = storage_usage_summary()
        return await self.templates.TemplateResponse(
            request,
            "social_media_hub.html",
            {
                "assets": assets,
                "statuses": STATUSES,
                "filter_status": status_filter or "",
                "usage": usage,
                "quick_links": SOCIAL_QUICK_LINKS,
                "workflow_steps": SOCIAL_POST_WORKFLOW,
                "caption_templates": SOCIAL_CAPTION_TEMPLATES,
                "brand_assets": SOCIAL_BRAND_ASSETS,
                "site_base": SITE_BASE,
                "can_manage": can_manage_social_media(role),
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
            table_name="social_media_assets",
            record_id=record_id,
            new_values=new_values,
            ip_address=_client_ip(request),
        )
