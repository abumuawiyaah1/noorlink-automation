"""Support ticket categories and reply templates."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class ReplyTemplate(TypedDict):
    key: str
    label: str
    body: str


class CategoryConfig(TypedDict):
    slug: str
    label: str
    received_title: str
    received_intro: str
    received_tip: str
    assigned_customer_intro: str
    reply_eyebrow: str
    reply_title: str
    reply_tip: str
    templates: List[ReplyTemplate]


_CATEGORY_BY_SLUG: Dict[str, CategoryConfig] = {
    "order_help": {
        "slug": "order_help",
        "label": "Order help",
        "received_title": "We received your order question",
        "received_intro": (
            "Thanks for reaching out about your order. Our team typically replies within 24 hours."
        ),
        "received_tip": "Include your order ID in any follow-up — it helps us find your case faster.",
        "assigned_customer_intro": (
            "A member of our team is now looking into your order question."
        ),
        "reply_eyebrow": "Order support",
        "reply_title": "Update on your order",
        "reply_tip": "Reply to this email if anything still looks off — we are here to help.",
        "templates": [
            {
                "key": "checking_order",
                "label": "Checking your order",
                "body": (
                    "Thanks for your patience. I am checking your order now and will follow up "
                    "shortly with a clear update on delivery and next steps."
                ),
            },
            {
                "key": "qr_on_way",
                "label": "QR email on the way",
                "body": (
                    "Your payment is confirmed. The QR code email usually arrives within a few "
                    "minutes — please check spam and promotions folders. If it has been longer than "
                    "15 minutes, reply here and we will resend it."
                ),
            },
        ],
    },
    "install_qr": {
        "slug": "install_qr",
        "label": "Install / QR code",
        "received_title": "We received your install request",
        "received_intro": (
            "Thanks for contacting us about install or QR delivery. We will walk you through "
            "the steps or resend your code if needed."
        ),
        "received_tip": "Install on Wi‑Fi before you fly — then turn on Data Roaming when you land.",
        "assigned_customer_intro": (
            "Someone from our install team is now helping with your QR code or setup."
        ),
        "reply_eyebrow": "Install help",
        "reply_title": "Help with your eSIM install",
        "reply_tip": "Install on Wi‑Fi before you fly — maps and messages stay calm when you land.",
        "templates": [
            {
                "key": "install_steps",
                "label": "Install steps",
                "body": (
                    "Here is a quick install checklist:\n"
                    "1. Connect to Wi‑Fi.\n"
                    "2. Open Settings → Cellular → Add eSIM (or scan the QR from your email).\n"
                    "3. Label the line (e.g. Travel) and set it for mobile data when you arrive.\n"
                    "4. Turn on Data Roaming for that line after landing.\n\n"
                    "If a step fails, tell us your phone model and we will tailor the steps."
                ),
            },
            {
                "key": "qr_resent",
                "label": "QR resent",
                "body": (
                    "I have resent your QR code email. Please check inbox, spam, and promotions. "
                    "Open it on the phone that will use the eSIM — forwarding QR codes often breaks install."
                ),
            },
            {
                "key": "device_not_compatible",
                "label": "Device compatibility",
                "body": (
                    "Some phones are carrier-locked or do not support eSIM. If install fails, tell us "
                    "your exact phone model and carrier. You can also check noorlink.co for device tips. "
                    "We will help you find the next best step."
                ),
            },
        ],
    },
    "checkout_payment": {
        "slug": "checkout_payment",
        "label": "Checkout / payment",
        "received_title": "We received your payment question",
        "received_intro": (
            "Thanks for reaching out about checkout or payment. We will review what happened "
            "and reply with clear next steps."
        ),
        "received_tip": "If your bank shows a pending charge, it often clears within a few minutes after payment succeeds.",
        "assigned_customer_intro": (
            "Our team is reviewing your checkout or payment question now."
        ),
        "reply_eyebrow": "Payment support",
        "reply_title": "Update on your payment",
        "reply_tip": "Never share full card numbers by email — we only need your order ID.",
        "templates": [
            {
                "key": "payment_pending",
                "label": "Payment still processing",
                "body": (
                    "Stripe may show a brief pending state while payment confirms. If it has been "
                    "more than 10 minutes and you still have no confirmation email, reply here and "
                    "we will check the payment status on our side."
                ),
            },
            {
                "key": "retry_checkout",
                "label": "Retry checkout link",
                "body": (
                    "It looks like checkout did not finish. You can place the order again safely — "
                    "if a duplicate charge appears we will refund it right away. Reply if you need "
                    "a direct checkout link for the same plan."
                ),
            },
        ],
    },
    "refund": {
        "slug": "refund",
        "label": "Refund",
        "received_title": "We received your refund request",
        "received_intro": (
            "Thanks for your message. We review refund requests against our policy and your "
            "order status, and reply within 24 hours."
        ),
        "received_tip": "See our refund policy at noorlink.co/refund for typical timelines.",
        "assigned_customer_intro": (
            "Your refund request is being reviewed by our support team."
        ),
        "reply_eyebrow": "Refund support",
        "reply_title": "Update on your refund request",
        "reply_tip": "Approved refunds usually return to your original payment method within 5–10 business days.",
        "templates": [
            {
                "key": "refund_review",
                "label": "Under review",
                "body": (
                    "We are reviewing your refund request against our policy and your eSIM usage. "
                    "I will reply shortly with a clear yes/no and timeline."
                ),
            },
            {
                "key": "refund_approved",
                "label": "Refund approved",
                "body": (
                    "Your refund has been approved and submitted to your payment provider. "
                    "Most banks show it within 5–10 business days on the original card."
                ),
            },
            {
                "key": "refund_denied_usage",
                "label": "Refund not eligible (usage)",
                "body": (
                    "I reviewed your order and usage. Because a large share of the data was already "
                    "used, we cannot approve a full refund under our policy. I am happy to help with "
                    "install or remaining data questions — just reply here."
                ),
            },
        ],
    },
    "other": {
        "slug": "other",
        "label": "Other",
        "received_title": "We received your message",
        "received_intro": (
            "Thanks for contacting NoorLink. Our team typically replies within 24 hours."
        ),
        "received_tip": "Include your ticket ID in any follow-up — it helps us find your case faster.",
        "assigned_customer_intro": (
            "Your request has been assigned to a member of our support team."
        ),
        "reply_eyebrow": "Support",
        "reply_title": "Reply from NoorLink",
        "reply_tip": "Reply to this email to continue the conversation.",
        "templates": [
            {
                "key": "general_followup",
                "label": "General follow-up",
                "body": (
                    "Thanks for your patience. I am looking into this now and will follow up "
                    "with a clear answer shortly."
                ),
            },
        ],
    },
}

_SUBJECT_ALIASES: Dict[str, str] = {
    "order help": "order_help",
    "install / qr code": "install_qr",
    "install/qr code": "install_qr",
    "qr code": "install_qr",
    "install": "install_qr",
    "checkout / payment": "checkout_payment",
    "checkout/payment": "checkout_payment",
    "payment": "checkout_payment",
    "refund": "refund",
    "other": "other",
}


def normalize_support_category(subject: Optional[str]) -> str:
    """Map contact-form subject to a stable category slug."""
    raw = (subject or "").strip().lower()
    if raw in _SUBJECT_ALIASES:
        return _SUBJECT_ALIASES[raw]
    for needle, slug in _SUBJECT_ALIASES.items():
        if needle in raw:
            return slug
    return "other"


def get_category_config(category: Optional[str]) -> CategoryConfig:
    slug = (category or "other").strip().lower()
    return _CATEGORY_BY_SLUG.get(slug, _CATEGORY_BY_SLUG["other"])


def list_reply_templates(category: Optional[str]) -> List[ReplyTemplate]:
    return list(get_category_config(category)["templates"])


# Always-available saved replies (shown on every ticket + merged into lookup)
COMMON_REPLY_TEMPLATES: List[ReplyTemplate] = [
    {
        "key": "common_thanks_waiting",
        "label": "Thanks — checking now",
        "body": (
            "Thank you for writing in. I am looking into this now and will reply shortly "
            "with a clear update."
        ),
    },
    {
        "key": "common_qr_missing",
        "label": "QR missing / resend",
        "body": (
            "Sorry you have not received your QR code yet. I am checking your order and will "
            "resend the activation email to the address on the order. Please check inbox, spam, "
            "and promotions — open the email on the phone that will use the eSIM."
        ),
    },
    {
        "key": "common_install_before_fly",
        "label": "Install before you fly",
        "body": (
            "Best practice: install on Wi‑Fi before you fly.\n"
            "1. Open Settings → Cellular → Add eSIM (or scan the QR).\n"
            "2. Keep your home line for calls/SMS if you want.\n"
            "3. After landing, turn on Data Roaming for the travel eSIM and select it for mobile data.\n\n"
            "If a step fails, reply with your phone model and we will guide you."
        ),
    },
    {
        "key": "common_refund_policy",
        "label": "Refund policy overview",
        "body": (
            "We review refunds against our policy and how much data was used. Unused or lightly "
            "used plans are often eligible; heavy usage may not be. I will check your order and "
            "reply with a clear yes/no and timeline. Our policy is at noorlink.co/refund."
        ),
    },
    {
        "key": "common_still_need_help",
        "label": "Anything else?",
        "body": (
            "Hopefully that helps. If anything is still unclear, just reply to this email — "
            "we are here to help."
        ),
    },
    {
        "key": "common_order_lookup_ask",
        "label": "Need order ID",
        "body": (
            "Could you reply with your order ID (it looks like nl-…) and the email used at "
            "checkout? That lets me pull up your eSIM right away."
        ),
    },
]


def list_all_reply_templates(category: Optional[str]) -> List[ReplyTemplate]:
    """Category templates first, then common saved replies (deduped by key)."""
    seen = set()
    out: List[ReplyTemplate] = []
    for tpl in list(get_category_config(category)["templates"]) + list(COMMON_REPLY_TEMPLATES):
        if tpl["key"] in seen:
            continue
        seen.add(tpl["key"])
        out.append(tpl)
    return out


def get_reply_template(category: Optional[str], template_key: Optional[str]) -> Optional[str]:
    if not template_key:
        return None
    key = template_key.strip().lower()
    for item in list_all_reply_templates(category):
        if item["key"] == key:
            return item["body"]
    return None


def category_label(category: Optional[str]) -> str:
    return get_category_config(category)["label"]
