from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from sqladmin import BaseView, expose

from app.admin.nav_catalog import OPERATIONS_CATEGORY
from app.admin.roles import ROLE_ADMIN, ROLE_SUPPORT, has_role
from app.services.critical_ops import list_critical_events
from app.services.ops_event_log import list_ops_events


class EventLogView(BaseView):
    name = "Critical logs"
    icon = "fa-solid fa-bolt"
    category = OPERATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return has_role(request, (ROLE_ADMIN, ROLE_SUPPORT))

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    # JSON first — sqladmin sets view.identity from the *last* @expose
    @expose("/critical-logs.json", identity="critical-logs-json", methods=["GET"])
    async def critical_json(self, request: Request):
        if not self.is_accessible(request):
            return JSONResponse({"events": [], "count": 0}, status_code=401)
        events = list_critical_events(limit=40)
        return JSONResponse({"events": events, "count": len(events)})

    @expose("/event-log", identity="event-log", methods=["GET"])
    async def list_view(self, request: Request):
        event_type = request.query_params.get("type", "").strip() or None
        order_number = request.query_params.get("order", "").strip() or None
        severity = request.query_params.get("severity", "").strip() or None
        critical_only = severity in {"critical", "error"} or request.query_params.get("view") == "critical"

        if critical_only and not event_type:
            events = list_critical_events(limit=150)
        elif event_type and event_type.endswith("_"):
            events = list_ops_events(
                limit=150,
                event_type_prefix=event_type,
                order_number=order_number,
                severity=severity if severity and severity != "critical" else None,
            )
            if critical_only:
                from app.services.critical_ops import is_critical_row

                events = [row for row in events if is_critical_row(row)]
        else:
            events = list_ops_events(
                limit=150,
                event_type=event_type,
                order_number=order_number,
                severity=None if critical_only else severity,
            )
            if critical_only and not severity:
                from app.services.critical_ops import is_critical_row

                events = [row for row in events if is_critical_row(row)]

        return await self.templates.TemplateResponse(
            request,
            "event_log.html",
            {
                "events": events,
                "event_type": event_type or "",
                "order_number": order_number or "",
                "severity": severity or ("critical" if critical_only else ""),
                "live": True,
            },
        )
