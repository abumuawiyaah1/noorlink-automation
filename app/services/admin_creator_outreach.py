"""Creator outreach CRM for admin marketing dashboard."""

from __future__ import annotations

import html
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from app.core.config import get_settings
from app.db.engine import get_session_factory
from app.db.models.creator_outreach import CreatorOutreachContact
from app.services.creator_outreach_templates import (
    OUTREACH_TEMPLATES,
    fill_template,
    get_template,
    templates_as_dicts,
)
from app.services.email_brand import PRIMARY, TEXT, cta_button, wrap_branded_email
from app.services.email_service import EmailDeliveryError, send_email

logger = logging.getLogger(__name__)

STATUSES = [
    ("to_contact", "To contact"),
    ("messaged", "Messaged"),
    ("replied", "Replied"),
    ("gifted", "Gifted"),
    ("posted", "Posted"),
    ("closed", "Closed"),
]

PLATFORMS = [
    ("instagram", "Instagram"),
    ("tiktok", "TikTok"),
    ("youtube", "YouTube"),
    ("email", "Email"),
    ("other", "Other"),
]

WAVES = [
    ("1", "Wave 1"),
    ("2", "Wave 2"),
    ("3", "Wave 3"),
    ("search", "Search find"),
]

STATUS_LABELS = dict(STATUSES)
PLATFORM_LABELS = dict(PLATFORMS)
WAVE_LABELS = dict(WAVES)

SEED_CONTACTS: List[Dict[str, str]] = [
    {
        "name": "Saffiyah",
        "handle": "@saffiyah.travels",
        "platform": "instagram",
        "profile_url": "https://www.instagram.com/saffiyah.travels/",
        "wave": "1",
        "notes": "Solo Muslim travel + Umrah tips; nano-tier.",
    },
    {
        "name": "Naima Begum",
        "handle": "@muslimsgotravel",
        "platform": "instagram",
        "profile_url": "https://www.instagram.com/muslimsgotravel/",
        "content_url": "https://muslimsgotravel.com/",
        "wave": "1",
        "notes": "Budget/halal travel; group trips = possible group codes.",
    },
    {
        "name": "Hadia",
        "handle": "@lifewithhadz",
        "platform": "instagram",
        "profile_url": "https://www.instagram.com/lifewithhadz/",
        "content_url": "https://www.instagram.com/lifewithhadz/reel/C04jtLqgHJB/",
        "wave": "1",
        "notes": "Umrah packing reel — practical logistics.",
    },
    {
        "name": "Tasneem Sayanvala",
        "platform": "instagram",
        "profile_url": "https://www.instagram.com/reel/DJCCexSTJlo/",
        "content_url": "https://www.instagram.com/reel/DJCCexSTJlo/",
        "wave": "1",
        "notes": "DIY Umrah UAE→Jeddah; confirm IG handle from reel profile.",
    },
    {
        "name": "Pakladies",
        "handle": "Pakladies",
        "platform": "youtube",
        "profile_url": "https://www.youtube.com/watch?v=b_3yPHikEmQ",
        "content_url": "https://www.youtube.com/watch?v=b_3yPHikEmQ",
        "wave": "1",
        "notes": "Umrah packing tips — first Umrah Spain to Jeddah.",
    },
    {
        "name": "Usman Tahir Jappa",
        "handle": "Usman Tahir Jappa",
        "platform": "youtube",
        "profile_url": "https://www.youtube.com/watch?v=7eBSiqgD9Qk",
        "content_url": "https://www.youtube.com/watch?v=7eBSiqgD9Qk",
        "wave": "1",
        "notes": "Jeddah airport → Makkah arrival vlog — strong eSIM angle.",
    },
    {
        "name": "Aleeza Siddika",
        "handle": "@aleezasiddika",
        "platform": "tiktok",
        "profile_url": "https://www.tiktok.com/@aleezasiddika",
        "wave": "1",
        "notes": "UK Muslim family travel (TikTok).",
    },
    {
        "name": "Farzana / Herquesting",
        "handle": "@herquesting",
        "email": "farzana.s.sultana@gmail.com",
        "platform": "instagram",
        "profile_url": "https://www.instagram.com/herquesting/",
        "wave": "1",
        "notes": "UK lifestyle/travel nano. Confirm email before send.",
    },
    {
        "name": "Ellie Quinn Belhaj",
        "handle": "@thewanderingquinn",
        "platform": "instagram",
        "profile_url": "https://www.instagram.com/thewanderingquinn/",
        "content_url": "https://www.thewanderingquinn.com/",
        "wave": "2",
        "notes": "UK revert travel; also @_equinn. Group trips = codes.",
    },
    {
        "name": "Amira Patel / Wanderlust Women",
        "handle": "@the.wanderlust.women",
        "platform": "instagram",
        "profile_url": "https://www.instagram.com/the.wanderlust.women/",
        "content_url": "https://www.thewanderlustwomen.co.uk/",
        "wave": "2",
        "notes": "Also @amira_thewanderlust. Community / retreat group codes.",
    },
    {
        "name": "Elena / Muslim Travel Girl",
        "handle": "@muslimtravelgirl",
        "platform": "instagram",
        "profile_url": "https://www.instagram.com/muslimtravelgirl/",
        "content_url": "https://muslimtravelgirl.com/",
        "wave": "3",
        "notes": "DIY Umrah authority — contact after early Wave 1 wins.",
    },
]


class CreatorOutreachError(Exception):
    """Creator outreach operation failed."""


def _session_factory():
    factory = get_session_factory()
    if factory is None:
        raise CreatorOutreachError("Database is not configured.")
    return factory


def _parse_date(value: str | None) -> Optional[date]:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise CreatorOutreachError(f"Invalid date: {raw}") from exc


def _contact_dict(row: CreatorOutreachContact) -> Dict[str, Any]:
    return {
        "id": str(row.id),
        "name": row.name,
        "handle": row.handle or "",
        "email": row.email or "",
        "platform": row.platform,
        "platform_label": PLATFORM_LABELS.get(row.platform, row.platform),
        "profile_url": row.profile_url or "",
        "content_url": row.content_url or "",
        "wave": row.wave,
        "wave_label": WAVE_LABELS.get(row.wave, row.wave),
        "status": row.status,
        "status_label": STATUS_LABELS.get(row.status, row.status),
        "message_sent": row.message_sent or "",
        "promo_code": row.promo_code or "",
        "notes": row.notes or "",
        "contacted_at": row.contacted_at.isoformat() if row.contacted_at else "",
        "replied_at": row.replied_at.isoformat() if row.replied_at else "",
        "last_email_at": row.last_email_at.isoformat() if row.last_email_at else "",
        "last_email_subject": row.last_email_subject or "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


def list_contacts(*, status: str | None = None, q: str | None = None) -> List[Dict[str, Any]]:
    factory = _session_factory()
    with factory() as session:
        stmt = select(CreatorOutreachContact).order_by(CreatorOutreachContact.updated_at.desc())
        if status:
            stmt = stmt.where(CreatorOutreachContact.status == status)
        rows = list(session.scalars(stmt).all())
        items = [_contact_dict(row) for row in rows]
    needle = (q or "").strip().lower()
    if not needle:
        return items
    return [
        item
        for item in items
        if needle in item["name"].lower()
        or needle in item["handle"].lower()
        or needle in item["email"].lower()
        or needle in item["notes"].lower()
        or needle in item["promo_code"].lower()
    ]


def get_contact(contact_id: str) -> Dict[str, Any]:
    factory = _session_factory()
    try:
        cid = uuid.UUID(contact_id)
    except ValueError as exc:
        raise CreatorOutreachError("Invalid contact id.") from exc
    with factory() as session:
        row = session.get(CreatorOutreachContact, cid)
        if row is None:
            raise CreatorOutreachError("Contact not found.")
        return _contact_dict(row)


def create_contact(data: Dict[str, Any], *, actor: str) -> Dict[str, Any]:
    name = str(data.get("name") or "").strip()
    if not name:
        raise CreatorOutreachError("Name is required.")
    factory = _session_factory()
    with factory() as session:
        row = CreatorOutreachContact(
            name=name,
            handle=str(data.get("handle") or "").strip(),
            email=str(data.get("email") or "").strip().lower(),
            platform=str(data.get("platform") or "instagram").strip() or "instagram",
            profile_url=str(data.get("profile_url") or "").strip(),
            content_url=str(data.get("content_url") or "").strip(),
            wave=str(data.get("wave") or "search").strip() or "search",
            status=str(data.get("status") or "to_contact").strip() or "to_contact",
            message_sent=str(data.get("message_sent") or ""),
            promo_code=str(data.get("promo_code") or "").strip(),
            notes=str(data.get("notes") or ""),
            contacted_at=_parse_date(str(data.get("contacted_at") or "")),
            replied_at=_parse_date(str(data.get("replied_at") or "")),
            created_by=actor or "",
            updated_by=actor or "",
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _contact_dict(row)


def update_contact(contact_id: str, data: Dict[str, Any], *, actor: str) -> Dict[str, Any]:
    factory = _session_factory()
    try:
        cid = uuid.UUID(contact_id)
    except ValueError as exc:
        raise CreatorOutreachError("Invalid contact id.") from exc
    with factory() as session:
        row = session.get(CreatorOutreachContact, cid)
        if row is None:
            raise CreatorOutreachError("Contact not found.")
        if "name" in data:
            name = str(data.get("name") or "").strip()
            if not name:
                raise CreatorOutreachError("Name is required.")
            row.name = name
        for field in (
            "handle",
            "email",
            "platform",
            "profile_url",
            "content_url",
            "wave",
            "status",
            "message_sent",
            "promo_code",
            "notes",
        ):
            if field in data:
                value = data.get(field)
                if field == "email":
                    setattr(row, field, str(value or "").strip().lower())
                elif field in {"message_sent", "notes"}:
                    setattr(row, field, str(value or ""))
                else:
                    setattr(row, field, str(value or "").strip())
        if "contacted_at" in data:
            row.contacted_at = _parse_date(str(data.get("contacted_at") or ""))
        if "replied_at" in data:
            row.replied_at = _parse_date(str(data.get("replied_at") or ""))
        row.updated_by = actor or ""
        row.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(row)
        return _contact_dict(row)


def delete_contact(contact_id: str) -> None:
    factory = _session_factory()
    try:
        cid = uuid.UUID(contact_id)
    except ValueError as exc:
        raise CreatorOutreachError("Invalid contact id.") from exc
    with factory() as session:
        row = session.get(CreatorOutreachContact, cid)
        if row is None:
            raise CreatorOutreachError("Contact not found.")
        session.delete(row)
        session.commit()


def seed_contacts_if_empty(*, actor: str = "system") -> Dict[str, Any]:
    factory = _session_factory()
    with factory() as session:
        count = session.scalar(select(CreatorOutreachContact.id).limit(1))
        if count is not None:
            total = len(list(session.scalars(select(CreatorOutreachContact)).all()))
            return {"seeded": False, "count": total}
        for item in SEED_CONTACTS:
            session.add(
                CreatorOutreachContact(
                    name=item["name"],
                    handle=item.get("handle", ""),
                    email=item.get("email", ""),
                    platform=item.get("platform", "instagram"),
                    profile_url=item.get("profile_url", ""),
                    content_url=item.get("content_url", ""),
                    wave=item.get("wave", "search"),
                    notes=item.get("notes", ""),
                    created_by=actor,
                    updated_by=actor,
                )
            )
        session.commit()
        return {"seeded": True, "count": len(SEED_CONTACTS)}


def _paragraphs_to_html(body_text: str) -> str:
    blocks = [b.strip() for b in body_text.split("\n\n") if b.strip()]
    if not blocks:
        return "<p></p>"
    parts = []
    for block in blocks:
        escaped = html.escape(block).replace("\n", "<br/>")
        parts.append(
            f'<p style="margin:0 0 16px;color:{TEXT};font-size:15px;line-height:1.65;">{escaped}</p>'
        )
    return "\n".join(parts)


def send_branded_outreach_email(
    *,
    contact_id: str,
    to_email: str,
    subject: str,
    body_text: str,
    eyebrow: str,
    title: str,
    cta_href: str = "",
    cta_label: str = "",
    actor: str,
    mark_messaged: bool = True,
) -> Dict[str, Any]:
    email = (to_email or "").strip().lower()
    if not email or "@" not in email:
        raise CreatorOutreachError("A valid recipient email is required.")
    subject_clean = (subject or "").strip()
    body_clean = (body_text or "").strip()
    if not subject_clean or not body_clean:
        raise CreatorOutreachError("Subject and message body are required.")

    settings = get_settings()
    cta = ""
    if cta_href and cta_label:
        cta = f'<p style="margin:8px 0 20px;">{cta_button(href=cta_href, label=cta_label)}</p>'
    body_html = _paragraphs_to_html(body_clean) + cta
    html_body = wrap_branded_email(
        eyebrow=(eyebrow or "Creator partnership").strip(),
        title=(title or "A note from NoorLink").strip(),
        body_html=body_html,
        app_url=settings.app_url.rstrip("/"),
        tip="Install before you fly — calm, practical travel data for pilgrims and travelers.",
    )

    try:
        message_id = send_email(
            to_email=email,
            subject=subject_clean,
            html_body=html_body,
            text_body=body_clean,
        )
    except EmailDeliveryError as exc:
        raise CreatorOutreachError(str(exc)) from exc

    factory = _session_factory()
    try:
        cid = uuid.UUID(contact_id)
    except ValueError as exc:
        raise CreatorOutreachError("Invalid contact id.") from exc

    with factory() as session:
        row = session.get(CreatorOutreachContact, cid)
        if row is None:
            raise CreatorOutreachError("Contact not found.")
        row.email = email
        row.message_sent = body_clean
        row.last_email_at = datetime.now(timezone.utc)
        row.last_email_subject = subject_clean
        if mark_messaged:
            row.status = "messaged"
            if row.contacted_at is None:
                row.contacted_at = date.today()
        row.updated_by = actor or ""
        row.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(row)
        contact = _contact_dict(row)

    logger.info(
        "Creator outreach email sent contact=%s to=%s resend_id=%s",
        contact_id,
        email,
        message_id,
    )
    return {"message_id": message_id, "contact": contact}


def prepare_template_preview(
    *,
    template_id: str,
    name: str,
    handle: str,
    promo_code: str,
    content_url: str,
) -> Dict[str, str]:
    template = get_template(template_id) or OUTREACH_TEMPLATES[0]
    vars_kwargs = {
        "name": name,
        "handle": handle,
        "code": promo_code,
        "content_url": content_url,
    }
    return {
        "template_id": template.id,
        "subject": fill_template(template.subject, **vars_kwargs),
        "body": fill_template(template.body, **vars_kwargs),
        "eyebrow": template.eyebrow,
        "title": fill_template(template.title, **vars_kwargs),
        "cta_label": template.cta_label,
        "cta_href": template.cta_href,
    }


def hub_context() -> Dict[str, Any]:
    return {
        "statuses": STATUSES,
        "platforms": PLATFORMS,
        "waves": WAVES,
        "templates": templates_as_dicts(),
    }
