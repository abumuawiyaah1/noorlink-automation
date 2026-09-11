from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse
from sqladmin import BaseView, expose

from app.admin.nav_catalog import NOTIFICATIONS_CATEGORY
from app.admin.roles import ALL_ROLES, session_role
from app.services.admin_do_next import (
    notifications_with_soft_reminders,
    soft_reminders_for_role,
)
from app.services.admin_notifications import notification_badge_count


class NotificationsHubView(BaseView):
    name = "Notifications"
    icon = "fa-solid fa-bell"
    category = NOTIFICATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return session_role(request) in ALL_ROLES

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

    # Secondary route first — sqladmin sets view.identity from the *last* @expose
    @expose("/reminders.json", identity="reminders-json", methods=["GET"])
    async def reminders_json(self, request: Request):
        """Soft reminders for the sticky orange ack banner (all admin pages)."""
        if not self.is_accessible(request):
            return JSONResponse({"reminders": []}, status_code=401)
        role = session_role(request)
        items = soft_reminders_for_role(role)
        return JSONResponse(
            {
                "reminders": [
                    {
                        "key": item.key,
                        "title": item.title,
                        "detail": item.detail,
                        "count": item.count,
                        "link_path": item.link_path,
                    }
                    for item in items
                ]
            }
        )

    @expose("/notifications", identity="notifications-hub", methods=["GET"])
    async def hub(self, request: Request):
        role = session_role(request)
        items = notifications_with_soft_reminders(role)
        return await self.templates.TemplateResponse(
            request,
            "notifications_hub.html",
            {
                "notifications": items,
                "total_count": len(items),
                "badge_count": notification_badge_count(role),
            },
        )
