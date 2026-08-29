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


def get_reply_template(category: Optional[str], template_key: Optional[str]) -> Optional[str]:
    if not template_key:
        return None
    key = template_key.strip().lower()
    for item in list_reply_templates(category):
        if item["key"] == key:
            return item["body"]
    return None


def category_label(category: Optional[str]) -> str:
    return get_category_config(category)["label"]
