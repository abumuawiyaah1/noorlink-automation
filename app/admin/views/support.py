from __future__ import annotations

from app.admin.roles import ROLE_ADMIN, ROLE_SUPPORT
from app.admin.views.base import AuditedModelView
from app.db.models import SupportTicket


class SupportTicketAdmin(AuditedModelView, model=SupportTicket):
    name = "Support Ticket"
    name_plural = "Support Tickets"
    icon = "fa-solid fa-life-ring"
    allowed_roles = (ROLE_ADMIN, ROLE_SUPPORT)

    can_create = False
    can_delete = False

    column_list = [
        SupportTicket.ticket_number,
        SupportTicket.order_number,
        SupportTicket.name,
        SupportTicket.email,
        SupportTicket.subject,
        SupportTicket.category,
        SupportTicket.language,
        SupportTicket.assigned_to,
        SupportTicket.status,
        SupportTicket.last_message_at,
        SupportTicket.created_at,
    ]
    column_searchable_list = [
        SupportTicket.ticket_number,
        SupportTicket.order_number,
        SupportTicket.email,
        SupportTicket.name,
        SupportTicket.subject,
    ]
    column_filters = [SupportTicket.status]
    column_default_sort = [(SupportTicket.created_at, True)]

    form_columns = [SupportTicket.status]
