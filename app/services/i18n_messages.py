"""Customer-facing locale strings for emails (and shared with site drafts).

Decisions: en (source) · es LatAm · ar MSA. Draft for owner review.
Keep keys aligned with noorlink-next `messages/*/emails`.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

SUPPORTED_LOCALES = ("en", "es", "ar")
DEFAULT_LOCALE = "en"

# Draft — review via site content/i18n/REVIEW.md
_EMAILS: Dict[str, Dict[str, str]] = {
    "en": {
        "supportConfirmSubject": "[{ticketId}] {subject}",
        "supportConfirmEyebrow": "Support",
        "supportConfirmTitle": "We received your message",
        "supportConfirmHi": "Hi {name},",
        "supportConfirmBody": (
            "Your support ticket has been created. Our team typically replies within 24 hours."
        ),
        "supportConfirmTicket": "Ticket ID:",
        "supportConfirmSubjectLabel": "Subject:",
        "supportConfirmYourMessage": "Your message",
        "supportConfirmTip": (
            "Include your ticket ID in any follow-up — it helps us find your case faster."
        ),
        "installHelpSubject": "Good news — your eSIM is ready (and we’re here to help)",
        "installHelpEyebrow": "Install help",
        "installHelpTitle": "Your eSIM is ready — we’re here if you need a hand",
        "installCongratsSubject": "You’re installed — connect automatically when you land",
        "installCongratsEyebrow": "You’re installed",
        "installCongratsTitle": "Nice work — here’s how to connect on landing",
        "myEsimsSubject": "Your My eSIMs link — NoorLink",
        "fulfillmentReadySubject": "Your NoorLink eSIM is ready — {country}",
        "beforeFlyTip": (
            "Install on Wi‑Fi before departure. Keep your main number for calls/WhatsApp; "
            "use the travel eSIM for data abroad."
        ),
    },
    "es": {
        "supportConfirmSubject": "[{ticketId}] {subject}",
        "supportConfirmEyebrow": "Soporte",
        "supportConfirmTitle": "Recibimos tu mensaje",
        "supportConfirmHi": "Hola {name},",
        "supportConfirmBody": (
            "Tu ticket de soporte ya está creado. El equipo suele responder en 24 horas."
        ),
        "supportConfirmTicket": "ID del ticket:",
        "supportConfirmSubjectLabel": "Asunto:",
        "supportConfirmYourMessage": "Tu mensaje",
        "supportConfirmTip": (
            "Incluye el ID del ticket en cualquier seguimiento — así encontramos tu caso más rápido."
        ),
        "installHelpSubject": "Buenas noticias — tu eSIM está lista (y estamos para ayudarte)",
        "installHelpEyebrow": "Ayuda para instalar",
        "installHelpTitle": "Tu eSIM está lista — aquí estamos si necesitas una mano",
        "installCongratsSubject": "Ya está instalada — conéctate al aterrizar",
        "installCongratsEyebrow": "Ya está instalada",
        "installCongratsTitle": "Muy bien — así te conectas al llegar",
        "myEsimsSubject": "Tu enlace a Mis eSIM — NoorLink",
        "fulfillmentReadySubject": "Tu eSIM NoorLink está lista — {country}",
        "beforeFlyTip": (
            "Instálala con Wi‑Fi antes de salir. Mantén tu número principal para llamadas/WhatsApp; "
            "usa la eSIM de viaje para datos en el extranjero."
        ),
    },
    "ar": {
        "supportConfirmSubject": "[{ticketId}] {subject}",
        "supportConfirmEyebrow": "الدعم",
        "supportConfirmTitle": "استلمنا رسالتك",
        "supportConfirmHi": "مرحبًا {name}،",
        "supportConfirmBody": (
            "تم إنشاء تذكرة الدعم الخاصة بك. يردّ فريقنا عادة خلال 24 ساعة."
        ),
        "supportConfirmTicket": "رقم التذكرة:",
        "supportConfirmSubjectLabel": "الموضوع:",
        "supportConfirmYourMessage": "رسالتك",
        "supportConfirmTip": (
            "أدرج رقم التذكرة في أي متابعة — يساعدنا ذلك على إيجاد حالتك أسرع."
        ),
        "installHelpSubject": "خبر سار — شريحة eSIM جاهزة (ونحن هنا للمساعدة)",
        "installHelpEyebrow": "مساعدة التثبيت",
        "installHelpTitle": "شريحة eSIM جاهزة — نحن هنا إن احتجت مساعدة",
        "installCongratsSubject": "تم التثبيت — اتصل تلقائيًا عند الهبوط",
        "installCongratsEyebrow": "تم التثبيت",
        "installCongratsTitle": "أحسنت — هكذا تتصل عند الوصول",
        "myEsimsSubject": "رابط شرائح eSIM الخاصة بك — NoorLink",
        "fulfillmentReadySubject": "شريحة NoorLink eSIM جاهزة — {country}",
        "beforeFlyTip": (
            "ثبّتها عبر Wi‑Fi قبل المغادرة. أبقِ رقمك الأساسي للمكالمات/واتساب؛ "
            "واستخدم eSIM السفر للبيانات في الخارج."
        ),
    },
}


def normalize_locale(value: Optional[str]) -> str:
    code = (value or "").strip().lower().split("-")[0][:8]
    if code in SUPPORTED_LOCALES:
        return code
    return DEFAULT_LOCALE


def email_messages(locale: Optional[str] = None) -> Mapping[str, str]:
    return _EMAILS[normalize_locale(locale)]


def t_email(locale: Optional[str], key: str, **vars: Any) -> str:
    table = email_messages(locale)
    text = table.get(key) or _EMAILS[DEFAULT_LOCALE].get(key) or key
    if not vars:
        return text
    try:
        return text.format(**vars)
    except (KeyError, ValueError):
        return text
