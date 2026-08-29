"""Optional IP allowlist for /admin routes."""

from __future__ import annotations

from typing import Callable, Iterable, Optional, Set

from starlette.requests import Request
from starlette.responses import HTMLResponse, Response


def _client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def parse_allowed_ips(raw: str) -> Set[str]:
    return {part.strip() for part in (raw or "").split(",") if part.strip()}


class AdminIPGuardMiddleware:
    """Block /admin when ADMIN_ALLOWED_IPS is set and client IP is not listed."""

    def __init__(self, app: Callable, allowed_ips: Iterable[str]):
        self.app = app
        self.allowed_ips = set(allowed_ips)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self.allowed_ips:
            await self.app(scope, receive, send)
            return

        path = scope.get("path") or ""
        if not path.startswith("/admin"):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        ip = _client_ip(request)
        if ip and ip in self.allowed_ips:
            await self.app(scope, receive, send)
            return

        from app.services.security_threats import log_security_event

        log_security_event(
            threat_type="admin_ip_blocked",
            source="admin_ip_guard",
            message=f"Blocked admin access from {ip or 'unknown'}",
            severity="warning",
            ip_address=ip,
            details={"path": path},
        )
        response = HTMLResponse(
            content=(
                "<h1>Admin access restricted</h1>"
                "<p>Your IP is not on the allowlist. Use VPN or ask an admin to add your IP to "
                "<code>ADMIN_ALLOWED_IPS</code> (or configure Cloudflare Access).</p>"
            ),
            status_code=403,
        )
        await response(scope, receive, send)
