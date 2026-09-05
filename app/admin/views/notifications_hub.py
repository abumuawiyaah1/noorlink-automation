from __future__ import annotations

from starlette.requests import Request
from sqladmin import BaseView, expose

from app.admin.nav_catalog import NOTIFICATIONS_CATEGORY
from app.admin.roles import ALL_ROLES, session_role
from app.services.admin_do_next import notifications_with_soft_reminders
from app.services.admin_notifications import notification_badge_count


class NotificationsHubView(BaseView):
    name = "Notifications"
    icon = "fa-solid fa-bell"
    category = NOTIFICATIONS_CATEGORY

    def is_accessible(self, request: Request) -> bool:
        return session_role(request) in ALL_ROLES

    def is_visible(self, request: Request) -> bool:
        return self.is_accessible(request)

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
