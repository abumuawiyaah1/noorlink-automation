from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin import BaseView, expose

from app.admin.audit import write_audit_log
from app.admin.nav_catalog import MARKETING_CATEGORY
from app.admin.roles import PROMO_MANAGER_ROLES, has_role, session_username
from app.admin.views.base import _client_ip
from app.db.engine import get_session_factory
from app.services.admin_creator_outreach import (
    CreatorOutreachError,
    create_contact,
    delete_contact,
    get_contact,
    hub_context,
    list_contacts,
    prepare_template_preview,
    seed_contacts_if_empty,
    send_branded_outreach_email,
    update_contact,
)


class CreatorOutreachHubView(BaseView):
    name = "Creator outreach"
    icon = "fa-solid fa-envelope-open-text"
    category = MARKETING_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, PROMO_MANAGER_ROLES)

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    @expose("/creator-outreach", identity="creator-outreach-hub", methods=["GET", "POST"])
    async def hub(self, request: Request):
        actor = session_username(request)

        try:
            seed_contacts_if_empty(actor=actor or "system")
        except CreatorOutreachError:
            pass

        if request.method == "POST":
            form = await request.form()
            action = str(form.get("action") or "").strip().lower()
            selected_id = str(form.get("contact_id") or "").strip()

            try:
                if action == "create":
                    contact = create_contact(_form_contact_payload(form), actor=actor)
                    _audit(
                        request,
                        action="creator_outreach_create",
                        record_id=contact["id"],
                        new_values={"name": contact["name"]},
                    )
                    request.session["flash_success"] = f"Added “{contact['name']}”."
                    return RedirectResponse(
                        f"{request.url_for('admin:creator-outreach-hub')}?id={contact['id']}",
                        status_code=302,
                    )

                if action == "update":
                    if not selected_id:
                        raise CreatorOutreachError("Select a contact to update.")
                    contact = update_contact(
                        selected_id, _form_contact_payload(form), actor=actor
                    )
                    _audit(
                        request,
                        action="creator_outreach_update",
                        record_id=contact["id"],
                        new_values={"status": contact["status"]},
                    )
                    request.session["flash_success"] = "Contact saved."
                    return RedirectResponse(
                        f"{request.url_for('admin:creator-outreach-hub')}?id={contact['id']}",
                        status_code=302,
                    )

                if action == "delete":
                    if not selected_id:
                        raise CreatorOutreachError("Select a contact to delete.")
                    delete_contact(selected_id)
                    _audit(
                        request,
                        action="creator_outreach_delete",
                        record_id=selected_id,
                        new_values={},
                    )
                    request.session["flash_success"] = "Contact deleted."
                    return RedirectResponse(
                        request.url_for("admin:creator-outreach-hub"), status_code=302
                    )

                if action == "send":
                    if not selected_id:
                        raise CreatorOutreachError("Select a contact before sending.")
                    # Persist latest form fields first
                    contact = update_contact(
                        selected_id, _form_contact_payload(form), actor=actor
                    )
                    template_id = str(form.get("template_id") or "gifted_collab").strip()
                    preview = prepare_template_preview(
                        template_id=template_id,
                        name=str(form.get("name") or contact["name"]),
                        handle=str(form.get("handle") or contact["handle"]),
                        promo_code=str(form.get("promo_code") or contact["promo_code"]),
                        content_url=str(form.get("content_url") or contact["content_url"]),
                    )
                    subject = str(form.get("email_subject") or preview["subject"]).strip()
                    body = str(form.get("email_body") or preview["body"]).strip()
                    result = send_branded_outreach_email(
                        contact_id=selected_id,
                        to_email=str(form.get("email") or contact["email"]),
                        subject=subject,
                        body_text=body,
                        eyebrow=preview["eyebrow"],
                        title=preview["title"],
                        cta_href=preview["cta_href"],
                        cta_label=preview["cta_label"],
                        actor=actor,
                        mark_messaged=True,
                    )
                    _audit(
                        request,
                        action="creator_outreach_send",
                        record_id=selected_id,
                        new_values={
                            "to": result["contact"]["email"],
                            "subject": subject,
                            "message_id": result["message_id"],
                        },
                    )
                    request.session["flash_success"] = (
                        f"Branded email sent to {result['contact']['email']}."
                    )
                    return RedirectResponse(
                        f"{request.url_for('admin:creator-outreach-hub')}?id={selected_id}",
                        status_code=302,
                    )

                raise CreatorOutreachError("Unknown action.")
            except CreatorOutreachError as exc:
                request.session["flash_error"] = str(exc)
                if selected_id:
                    return RedirectResponse(
                        f"{request.url_for('admin:creator-outreach-hub')}?id={selected_id}",
                        status_code=302,
                    )
                return RedirectResponse(
                    request.url_for("admin:creator-outreach-hub"), status_code=302
                )

        status_filter = (request.query_params.get("status") or "").strip()
        query = (request.query_params.get("q") or "").strip()
        selected_id = (request.query_params.get("id") or "").strip()
        template_id = (request.query_params.get("template") or "gifted_collab").strip()
        is_new = (request.query_params.get("new") or "").strip() == "1"

        try:
            contacts = list_contacts(status=status_filter or None, q=query or None)
        except CreatorOutreachError as exc:
            contacts = []
            request.session["flash_error"] = str(exc)

        selected = None
        if selected_id and not is_new:
            try:
                selected = get_contact(selected_id)
            except CreatorOutreachError:
                selected = None

        if selected is None and contacts and not is_new and not selected_id:
            selected = contacts[0]
            selected_id = selected["id"]

        preview_source = selected or {
            "name": "",
            "handle": "",
            "promo_code": "",
            "content_url": "",
            "email": "",
        }
        preview = prepare_template_preview(
            template_id=template_id,
            name=preview_source.get("name", ""),
            handle=preview_source.get("handle", ""),
            promo_code=preview_source.get("promo_code", ""),
            content_url=preview_source.get("content_url", ""),
        )

        ctx = hub_context()
        return await self.templates.TemplateResponse(
            request,
            "creator_outreach_hub.html",
            {
                **ctx,
                "contacts": contacts,
                "selected": selected,
                "selected_id": selected_id,
                "is_new": is_new,
                "filter_status": status_filter,
                "query": query,
                "template_id": preview["template_id"],
                "email_subject": preview["subject"],
                "email_body": preview["body"],
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )


def _form_contact_payload(form) -> dict:
    return {
        "name": str(form.get("name") or ""),
        "handle": str(form.get("handle") or ""),
        "email": str(form.get("email") or ""),
        "platform": str(form.get("platform") or "instagram"),
        "profile_url": str(form.get("profile_url") or ""),
        "content_url": str(form.get("content_url") or ""),
        "wave": str(form.get("wave") or "search"),
        "status": str(form.get("status") or "to_contact"),
        "message_sent": str(form.get("message_sent") or ""),
        "promo_code": str(form.get("promo_code") or ""),
        "notes": str(form.get("notes") or ""),
        "contacted_at": str(form.get("contacted_at") or ""),
        "replied_at": str(form.get("replied_at") or ""),
    }


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
            table_name="creator_outreach_contacts",
            record_id=record_id,
            new_values=new_values,
            ip_address=_client_ip(request),
        )
