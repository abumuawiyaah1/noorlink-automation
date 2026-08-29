"""Log support requests on behalf of customers (staff wizard)."""

from __future__ import annotations

from typing import Any, Dict

from app.services.support_categories import normalize_support_category
from app.services.support_messaging import SupportMessagingError, create_ticket_from_contact
from app.services.support_notifications import dispatch_ticket_created_notifications


class AdminSupportWizardError(Exception):
    """Staff support wizard failed."""


SUPPORT_TOPIC_OPTIONS = {
    "Order help": "order_help",
    "Install / QR code": "install_qr",
    "Checkout / payment": "checkout_payment",
    "Refund": "refund",
    "Other": "other",
}


def parse_help_customer_form(form: Dict[str, Any]) -> Dict[str, Any]:
    name = str(form.get("name") or "").strip()
    email = str(form.get("email") or "").strip().lower()
    order_number = str(form.get("order_number") or "").strip().upper() or None
    subject = str(form.get("subject") or "Order help").strip()
    message = str(form.get("message") or "").strip()

    if not name:
        raise AdminSupportWizardError("Customer name is required.")
    if not email or "@" not in email:
        raise AdminSupportWizardError("A valid customer email is required.")
    if not message:
        raise AdminSupportWizardError("Please describe what the customer needs.")

    return {
        "name": name,
        "email": email,
        "order_number": order_number,
        "subject": subject,
        "message": message,
        "category": normalize_support_category(subject),
    }


def create_customer_help_ticket(*, form: Dict[str, Any]) -> Dict[str, Any]:
    parsed = parse_help_customer_form(form)
    try:
        created = create_ticket_from_contact(
            name=parsed["name"],
            email=parsed["email"],
            subject=parsed["subject"],
            message=parsed["message"],
            order_number=parsed["order_number"],
        )
    except SupportMessagingError as exc:
        raise AdminSupportWizardError(str(exc)) from exc

    try:
        dispatch_ticket_created_notifications(
            ticket_id=created["ticket_number"],
            name=parsed["name"],
            email=parsed["email"],
            subject=parsed["subject"],
            message=parsed["message"],
            order_number=parsed["order_number"],
            category=created.get("category"),
            run_auto_reply=False,
        )
    except Exception:
        pass

    return {
        "ticket_number": created["ticket_number"],
        "email": parsed["email"],
        "order_number": parsed["order_number"],
    }
