"""Ready-to-share promo links + WhatsApp / email helpers for staff."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from urllib.parse import quote

from app.core.config import get_settings
from app.services.promo_codes import normalize_code


def build_promo_share_links(*, code: str, app_url: Optional[str] = None) -> List[Dict[str, str]]:
    """Useful customer URLs that already include ?promo=CODE."""
    settings = get_settings()
    base = (app_url or settings.app_url or "https://noorlink.co").rstrip("/")
    normalized = normalize_code(code)
    if not normalized:
        return []
    q = f"promo={quote(normalized)}"
    return [
        {
            "key": "destinations",
            "label": "Destinations",
            "url": f"{base}/destinations?{q}",
            "hint": "Best default — pick any country",
        },
        {
            "key": "home",
            "label": "Homepage",
            "url": f"{base}/?{q}",
            "hint": "Home page with code attached",
        },
        {
            "key": "hajj_umrah",
            "label": "Hajj & Umrah",
            "url": f"{base}/hajj-umrah?{q}",
            "hint": "Pilgrimage plans",
        },
        {
            "key": "usa",
            "label": "United States plans",
            "url": f"{base}/plans/usa?{q}",
            "hint": "Example country page",
        },
    ]


def discount_phrase(*, percent_off: Optional[int], amount_off_cents: Optional[int]) -> str:
    if percent_off:
        return f"{int(percent_off)}% off"
    if amount_off_cents:
        dollars = int(amount_off_cents) / 100.0
        if dollars == int(dollars):
            return f"${int(dollars)} off"
        return f"${dollars:.2f} off"
    return "a discount"


def build_promo_share_message(
    *,
    code: str,
    share_url: str,
    percent_off: Optional[int] = None,
    amount_off_cents: Optional[int] = None,
) -> str:
    phrase = discount_phrase(percent_off=percent_off, amount_off_cents=amount_off_cents)
    return (
        f"Hi — here’s {phrase} on NoorLink travel eSIM.\n\n"
        f"Open this link and checkout: {share_url}\n\n"
        f"Or enter code {normalize_code(code)} at checkout on noorlink.co."
    )


def whatsapp_share_url(*, message: str, phone: str = "") -> str:
    """Open WhatsApp with a prefilled message (optional recipient digits)."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    text = quote(message)
    if digits:
        return f"https://wa.me/{digits}?text={text}"
    return f"https://wa.me/?text={text}"


def share_context_for_code(
    *,
    code: str,
    percent_off: Optional[int] = None,
    amount_off_cents: Optional[int] = None,
    admin_approved: bool = True,
) -> Dict[str, Any]:
    links = build_promo_share_links(code=code)
    primary = links[0]["url"] if links else ""
    message = build_promo_share_message(
        code=code,
        share_url=primary,
        percent_off=percent_off,
        amount_off_cents=amount_off_cents,
    )
    return {
        "code": normalize_code(code),
        "percent_off": percent_off,
        "amount_off_cents": amount_off_cents,
        "admin_approved": admin_approved,
        "discount_phrase": discount_phrase(
            percent_off=percent_off,
            amount_off_cents=amount_off_cents,
        ),
        "links": links,
        "primary_url": primary,
        "message": message,
        "whatsapp_url": whatsapp_share_url(message=message),
    }
