"""Create staff admin users from the dashboard (with owner guards)."""

from __future__ import annotations

import html
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.services.admin_owner_guard import OwnerGuardError, create_staff_user_secure
from app.services.email_brand import cta_button, wrap_branded_email
from app.services.email_service import EmailDeliveryError, send_email


class AdminStaffUserError(Exception):
    """Staff user wizard failed."""


ROLE_BLURBS = {
    "owner": "Full access — business owner.",
    "admin": "Day-to-day full ops (almost everything).",
    "support": "Tickets, order lookup, fulfill stuck orders.",
    "marketing": "Promos, Insider, social media, creator outreach.",
    "catalog": "Travel plans, SKUs, catalog tools.",
    "finance": "Finance views and document vault.",
    "legal": "Company document vault.",
}


def admin_login_url() -> str:
    """Prefer public API admin URL; fall back to app_url/admin."""
    settings = get_settings()
    raw = (getattr(settings, "admin_public_url", None) or "").strip()
    if raw:
        return raw.rstrip("/")
    # Production API host used by Cloudflare Access
    env = (settings.environment or "").lower()
    if env in {"production", "prod"}:
        return "https://api.noorlink.co/admin"
    base = (settings.app_url or "").rstrip("/")
    if "api.noorlink" in base:
        return f"{base}/admin" if not base.endswith("/admin") else base
    return "https://api.noorlink.co/admin"


def send_staff_welcome_email(
    *,
    to_email: str,
    username: str,
    password: str,
    role: str,
    display_name: str,
    include_password: bool = True,
) -> str:
    """Send branded onboarding email with everything they need to sign in."""
    email = (to_email or "").strip().lower()
    if not email or "@" not in email:
        raise AdminStaffUserError("A valid work email is required to send the invite.")

    login_url = admin_login_url()
    role_blurb = ROLE_BLURBS.get(role, role)
    name = (display_name or username).strip()
    password_block = ""
    if include_password:
        password_block = f"""
        <p style="margin:16px 0 8px;"><strong>Temporary password</strong></p>
        <p style="margin:0 0 16px;padding:12px 14px;background:#F3F7F7;border-radius:8px;font-family:Menlo,Consolas,monospace;font-size:14px;color:#0F3D3E;">
          {html.escape(password)}
        </p>
        <p style="margin:0 0 16px;font-size:14px;color:#6B7280;">Change this after you sign in if your team asks you to.</p>
        """
    else:
        password_block = (
            "<p style=\"margin:0 0 16px;\">Your manager will share the password separately.</p>"
        )

    body_html = f"""
      <p style="margin:0 0 16px;">Hi {html.escape(name)},</p>
      <p style="margin:0 0 16px;">
        You have a NoorLink staff dashboard login. Use the details below to get started.
      </p>
      <p style="margin:0 0 8px;"><strong>Sign-in page</strong></p>
      <p style="margin:0 0 16px;"><a href="{html.escape(login_url)}" style="color:#0F3D3E;">{html.escape(login_url)}</a></p>
      <p style="margin:0 0 8px;"><strong>Username</strong></p>
      <p style="margin:0 0 16px;padding:12px 14px;background:#F3F7F7;border-radius:8px;font-family:Menlo,Consolas,monospace;color:#0F3D3E;">{html.escape(username)}</p>
      {password_block}
      <p style="margin:0 0 8px;"><strong>Your role</strong></p>
      <p style="margin:0 0 16px;">{html.escape(role)} — {html.escape(role_blurb)}</p>
      <p style="margin:8px 0 20px;">{cta_button(href=login_url, label="Open staff dashboard")}</p>
      <p style="margin:0 0 8px;font-size:14px;color:#6B7280;">
        After you sign in: open <strong>Help</strong> for how-tos, and check <strong>Notifications</strong> daily.
        Cloudflare Access may ask for your email once before the login form — that is normal.
      </p>
    """
    settings = get_settings()
    html_body = wrap_branded_email(
        eyebrow="Staff access",
        title="Your NoorLink dashboard login",
        body_html=body_html,
        app_url=settings.app_url.rstrip("/"),
        tip="Keep your password private. Ask your manager if anything looks wrong.",
    )
    text_body = (
        f"Hi {name},\n\n"
        f"Your NoorLink staff dashboard login:\n"
        f"Sign-in: {login_url}\n"
        f"Username: {username}\n"
        + (f"Password: {password}\n" if include_password else "Password: shared separately\n")
        + f"Role: {role} — {role_blurb}\n\n"
        "Open Help after you sign in for how-tos.\n"
    )
    try:
        return send_email(
            to_email=email,
            subject="Your NoorLink staff dashboard login",
            html_body=html_body,
            text_body=text_body,
        )
    except EmailDeliveryError as exc:
        raise AdminStaffUserError(f"Account created, but invite email failed: {exc}") from exc


def create_staff_user_from_wizard(
    *,
    form: Dict[str, Any],
    actor_role: str = "admin",
    actor_username: str = "system",
) -> Dict[str, Any]:
    try:
        result = create_staff_user_secure(
            form=form,
            actor_role=actor_role,
            actor_username=actor_username,
        )
    except OwnerGuardError as exc:
        raise AdminStaffUserError(str(exc)) from exc

    send_invite = str(form.get("send_invite_email") or "").lower() in {
        "1",
        "true",
        "on",
        "yes",
    }
    notify_email = str(form.get("notify_email") or "").strip().lower()
    password = str(form.get("password") or "")
    invite_sent = False
    invite_error: Optional[str] = None

    if send_invite:
        if not notify_email:
            invite_error = "Account created, but no email was sent — add their work email and resend, or share details yourself."
        else:
            try:
                send_staff_welcome_email(
                    to_email=notify_email,
                    username=result["username"],
                    password=password,
                    role=result["role"],
                    display_name=result.get("display_name") or result["username"],
                    include_password=True,
                )
                invite_sent = True
            except AdminStaffUserError as exc:
                invite_error = str(exc)

    result["notify_email"] = notify_email or None
    result["invite_sent"] = invite_sent
    result["invite_error"] = invite_error
    result["login_url"] = admin_login_url()
    return result
