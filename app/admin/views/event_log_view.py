from __future__ import annotations

from starlette.requests import Request
from sqladmin import BaseView, expose

from app.admin.nav_catalog import OPERATIONS_CATEGORY
from app.admin.roles import ROLE_ADMIN, ROLE_SUPPORT, has_role
from app.services.ops_event_log import list_ops_events


class EventLogView(BaseView):
    name = "Event log"
    icon = "fa-solid fa-list-check"
    category = OPERATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN, ROLE_SUPPORT))

    def is_visible(self, request: Request) -> bool:
        return False

    @expose("/event-log", identity="event-log", methods=["GET"])
    async def list_view(self, request: Request):
        event_type = request.query_params.get("type", "").strip() or None
        order_number = request.query_params.get("order", "").strip() or None
        if event_type and event_type.endswith("_"):
            events = list_ops_events(
                limit=150,
                event_type_prefix=event_type,
                order_number=order_number,
            )
        else:
            events = list_ops_events(
                limit=150,
                event_type=event_type,
                order_number=order_number,
            )
        return await self.templates.TemplateResponse(
            request,
            "event_log.html",
            {"events": events, "event_type": event_type or "", "order_number": order_number or ""},
        )
