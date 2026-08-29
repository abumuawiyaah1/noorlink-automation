"""Create and test Insider newsletter issues from admin."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.api import supabase_repository as db
from app.services.email_service import EmailDeliveryError, send_insider_issue_email
from app.services.promo_codes import PromoCodeError, validate_promo_row


class AdminInsiderError(Exception):
    """Insider wizard failed."""


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:80] or "insider-issue"


def _parse_send_at(value: str) -> datetime:
    text = (value or "").strip()
    if not text:
        raise AdminInsiderError("Send date and time are required.")
    if len(text) == 10:
        text = f"{text}T09:00:00+00:00"
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def parse_insider_wizard_form(form: Dict[str, Any]) -> Dict[str, Any]:
    slug = _slugify(str(form.get("slug") or form.get("subject") or ""))
    subject = str(form.get("subject") or "").strip()
    preview = str(form.get("preview") or "").strip()
    if not subject:
        raise AdminInsiderError("Email subject is required.")
    if not preview:
        raise AdminInsiderError("Preview text is required for the email.")

    audience = str(form.get("audience") or "all").strip().lower()
    if audience not in {"all", "pilgrimage"}:
        raise AdminInsiderError("Audience must be 'all' or 'pilgrimage'.")

    publish_now = str(form.get("publish_now") or "").lower() in {"1", "true", "on", "yes"}
    send_at = _parse_send_at(str(form.get("send_at") or ""))
    if publish_now:
        send_at = datetime.now(timezone.utc)

    return {
        "slug": slug,
        "subject": subject,
        "preview": preview,
        "hero_image_url": str(form.get("hero_image_url") or "").strip(),
        "web_path": str(form.get("web_path") or f"/newsletter/{slug}").strip(),
        "promo_code": str(form.get("promo_code") or "").strip().upper() or None,
        "send_at": send_at.isoformat(),
        "status": "scheduled",
        "audience": audience,
        "email_highlight": str(form.get("email_highlight") or "").strip() or None,
        "email_highlight_ref": str(form.get("email_highlight_ref") or "").strip() or None,
        "email_note": str(form.get("email_note") or "").strip() or None,
        "email_giving_note": str(form.get("email_giving_note") or "").strip() or None,
    }


def create_insider_issue_from_wizard(*, form: Dict[str, Any]) -> Dict[str, Any]:
    payload = parse_insider_wizard_form(form)
    client = db.get_supabase_client()

    existing = (
        client.table("insider_issues")
        .select("slug")
        .eq("slug", payload["slug"])
        .limit(1)
        .execute()
    )
    if existing.data:
        raise AdminInsiderError(f"An issue with slug '{payload['slug']}' already exists.")

    try:
        client.table("insider_issues").insert(payload).execute()
    except db.SupabaseRepositoryError as exc:
        raise AdminInsiderError(str(exc)) from exc
    except Exception as exc:
        raise AdminInsiderError(str(exc)) from exc

    return {"slug": payload["slug"], "status": payload["status"], "send_at": payload["send_at"]}


def send_insider_test_email(*, form: Dict[str, Any], to_email: str) -> str:
    parsed = parse_insider_wizard_form(form)
    recipient = to_email.strip().lower()
    if not recipient or "@" not in recipient:
        raise AdminInsiderError("A valid test email address is required.")

    promo_row = None
    promo_code = parsed.get("promo_code")
    if promo_code:
        promo_row = db.get_promo_code(str(promo_code))

    promo_percent = promo_row.get("percent_off") if promo_row else None
    promo_ends = None
    if promo_row:
        try:
            promo_ends = validate_promo_row(promo_row, subtotal_cents=1000).ends_at
        except PromoCodeError:
            promo_ends = str(promo_row.get("ends_at") or "")

    try:
        return send_insider_issue_email(
            to_email=recipient,
            subject=f"[TEST] {parsed['subject']}",
            preview=parsed["preview"],
            hero_image_url=parsed.get("hero_image_url") or "",
            web_path=parsed.get("web_path") or f"/newsletter/{parsed['slug']}",
            promo_code=promo_code,
            promo_percent=int(promo_percent) if promo_percent else None,
            promo_ends=promo_ends,
            email_highlight=parsed.get("email_highlight"),
            email_highlight_ref=parsed.get("email_highlight_ref"),
            email_note=parsed.get("email_note"),
            email_giving_note=parsed.get("email_giving_note"),
        )
    except EmailDeliveryError as exc:
        raise AdminInsiderError(str(exc)) from exc
