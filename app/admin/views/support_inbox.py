from __future__ import annotations

from starlette.requests import Request
from starlette.responses import RedirectResponse
from sqladmin import BaseView, expose

from app.admin.roles import ROLE_ADMIN, ROLE_SUPPORT, has_role, session_username
from app.services.support_categories import category_label, list_all_reply_templates
from app.services.support_messaging import (
    SupportMessagingError,
    assign_support_ticket,
    get_ticket_by_number,
    list_assignable_admins,
    list_messages_for_ticket,
    list_tickets_for_inbox,
    send_staff_reply,
    update_ticket_status,
)


class SupportInboxView(BaseView):
    name = "Support Inbox"
    icon = "fa-solid fa-inbox"
    category = "Support"

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN, ROLE_SUPPORT))

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    # Secondary route first — sqladmin sets view.identity from the *last* @expose
    @expose("/support-inbox/{ticket_number}", identity="support-inbox-ticket", methods=["GET", "POST"])
    async def ticket_thread(self, request: Request):
        ticket_number = request.path_params.get("ticket_number", "").strip().upper()
        ticket = get_ticket_by_number(ticket_number)
        if ticket is None:
            request.session["flash_error"] = f"Ticket {ticket_number} not found."
            return RedirectResponse(request.url_for("admin:support-inbox"), status_code=302)

        if request.method == "POST":
            form = await request.form()
            action = str(form.get("action") or "reply").strip().lower()
            flash_set = False

            if action == "assign":
                assignee = str(form.get("assign_to") or "").strip()
                if assignee:
                    try:
                        assign_support_ticket(
                            ticket_number=ticket_number,
                            assignee_username=assignee,
                        )
                        request.session["flash_success"] = f"Ticket assigned to {assignee} — notifications sent."
                        flash_set = True
                        ticket = get_ticket_by_number(ticket_number) or ticket
                    except SupportMessagingError as exc:
                        request.session["flash_error"] = str(exc)
            else:
                reply_body = str(form.get("reply_body") or "").strip()
                template_key = str(form.get("template_key") or "").strip() or None
                new_status = str(form.get("ticket_status") or ticket.status).strip().lower()

                if reply_body or template_key:
                    try:
                        send_staff_reply(
                            ticket_number=ticket_number,
                            body=reply_body,
                            admin_username=session_username(request),
                            template_key=template_key,
                        )
                        request.session["flash_success"] = "Branded reply sent to customer."
                        flash_set = True
                        ticket = get_ticket_by_number(ticket_number) or ticket
                    except SupportMessagingError as exc:
                        request.session["flash_error"] = str(exc)

                if new_status != ticket.status:
                    try:
                        update_ticket_status(ticket_number, new_status)
                        if not flash_set:
                            request.session["flash_success"] = "Ticket status updated."
                    except SupportMessagingError as exc:
                        request.session["flash_error"] = str(exc)

            return RedirectResponse(
                request.url_for("admin:support-inbox-ticket", ticket_number=ticket_number),
                status_code=302,
            )

        try:
            admins = list_assignable_admins()
            reply_templates = list_all_reply_templates(ticket.category)
        except SupportMessagingError:
            admins = []
            reply_templates = []

        messages = list_messages_for_ticket(str(ticket.id))
        category_templates = [t for t in reply_templates if not t["key"].startswith("common_")]
        common_templates = [t for t in reply_templates if t["key"].startswith("common_")]
        return await self.templates.TemplateResponse(
            request,
            "support_ticket_thread.html",
            {
                "ticket": ticket,
                "messages": messages,
                "admins": admins,
                "reply_templates": reply_templates,
                "category_templates": category_templates,
                "common_templates": common_templates,
                "category_label": category_label(ticket.category),
                "flash_success": request.session.pop("flash_success", None),
                "flash_error": request.session.pop("flash_error", None),
            },
        )

    @expose("/support-inbox", identity="support-inbox", methods=["GET"])
    async def inbox(self, request: Request):
        try:
            tickets = list_tickets_for_inbox(limit=200)
        except SupportMessagingError:
            tickets = []
        return await self.templates.TemplateResponse(
            request,
            "support_inbox.html",
            {"tickets": tickets},
        )
