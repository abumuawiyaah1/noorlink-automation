"""Premade creator outreach email/DM templates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class OutreachTemplate:
    id: str
    label: str
    description: str
    subject: str
    eyebrow: str
    title: str
    body: str
    cta_label: str = "See NoorLink plans"
    cta_href: str = "https://noorlink.co/hajj-umrah"


OUTREACH_TEMPLATES: List[OutreachTemplate] = [
    OutreachTemplate(
        id="gifted_collab",
        label="Gifted eSIM + affiliate code",
        description="First outreach — free KSA pass + commission.",
        subject="Gifted KSA eSIM + custom code for your followers",
        eyebrow="Creator partnership",
        title="A free Saudi eSIM for your next trip",
        body=(
            "Hi {{name}},\n\n"
            "I love your content{{content_ref}}!\n\n"
            "I'm Jorge, Founder of NoorLink (noorlink.co). We built a travel eSIM for "
            "Umrah and Hajj pilgrims — instant data on Saudi networks as soon as they land, "
            "so they don't wait in airport SIM lines or pay roaming fees.\n\n"
            "We'd love to gift you a free high-speed Saudi data pass to try, plus a custom "
            "promo code for your followers (10–15% on sales).\n\n"
            "If that sounds useful, reply with the best email for the gift QR and the code "
            "name you'd like (e.g. {{code_hint}}).\n\n"
            "Warm regards,\nJorge\nFounder, NoorLink"
        ),
    ),
    OutreachTemplate(
        id="follow_up",
        label="Friendly follow-up",
        description="Short bump if they didn't reply.",
        subject="Quick follow-up — gifted Saudi eSIM from NoorLink",
        eyebrow="Friendly follow-up",
        title="Just checking in",
        body=(
            "Hi {{name}},\n\n"
            "Following up on my note about a gifted Saudi eSIM + affiliate code for your audience.\n\n"
            "Happy to keep it simple: free pass for you to test, and a code your followers can use. "
            "No pressure either way — just reply yes if you'd like me to set it up.\n\n"
            "Jorge\nNoorLink"
        ),
    ),
    OutreachTemplate(
        id="group_trip_code",
        label="Group / trip leader code",
        description="For communities and retreat organizers.",
        subject="Group promo code for your next trip travelers",
        eyebrow="Group partnership",
        title="A code your travelers can use",
        body=(
            "Hi {{name}},\n\n"
            "I'm Jorge from NoorLink. We help pilgrims get Saudi eSIM data before they fly — "
            "install once, connect on landing.\n\n"
            "If you lead group trips or retreats, we can set up a dedicated promo code for your "
            "attendees (and a commission share for you). Travelers skip airport SIM queues; "
            "you share one simple link.\n\n"
            "Reply with your preferred code name and the trip date if you have one, "
            "and I'll set it up.\n\n"
            "Jorge\nNoorLink · noorlink.co"
        ),
    ),
    OutreachTemplate(
        id="thank_you_posted",
        label="Thanks after they post",
        description="After a Story/Reel goes live.",
        subject="Thank you — your NoorLink mention means a lot",
        eyebrow="Thank you",
        title="Appreciate you",
        cta_label="Visit NoorLink",
        cta_href="https://noorlink.co",
        body=(
            "Hi {{name}},\n\n"
            "Thank you for sharing NoorLink with your community. It means a lot coming from "
            "someone people trust for real travel advice.\n\n"
            "Your code {{code}} is live — we'll keep an eye on it and are happy to top up your "
            "gifted plan or adjust the offer anytime.\n\n"
            "If you ever need anything for an upcoming Umrah or trip video, just reply here.\n\n"
            "Jorge\nNoorLink"
        ),
    ),
]


def get_template(template_id: str) -> OutreachTemplate | None:
    for item in OUTREACH_TEMPLATES:
        if item.id == template_id:
            return item
    return None


def fill_template(text: str, *, name: str, handle: str, code: str, content_url: str) -> str:
    first = (name or "").strip().split()[0] if (name or "").strip() else "there"
    handle_clean = (handle or "").strip() or first
    code_clean = (code or "").strip()
    if not code_clean:
        base = "".join(ch for ch in first if ch.isalnum()).upper()[:10] or "CREATOR"
        code_clean = f"{base}10"
    content_ref = " — especially the piece I linked in our notes" if (content_url or "").strip() else ""
    return (
        text.replace("{{name}}", first)
        .replace("{{handle}}", handle_clean)
        .replace("{{code}}", code_clean)
        .replace("{{code_hint}}", code_clean)
        .replace("{{content}}", (content_url or "").strip())
        .replace("{{content_ref}}", content_ref)
    )


def templates_as_dicts() -> List[Dict[str, str]]:
    return [
        {
            "id": t.id,
            "label": t.label,
            "description": t.description,
            "subject": t.subject,
            "eyebrow": t.eyebrow,
            "title": t.title,
            "body": t.body,
            "cta_label": t.cta_label,
            "cta_href": t.cta_href,
        }
        for t in OUTREACH_TEMPLATES
    ]
