"""Detect customer language for support tickets."""

from __future__ import annotations

import re

from typing import Optional

SUPPORTED_LANGUAGES = {
    "en": "English",
    "ar": "Arabic",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
}

_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")

# Light Spanish signal for LatAm / general ES tickets (hint still wins).
_SPANISH_HINTS = (
    "hola",
    "gracias",
    "por favor",
    "necesito",
    "ayuda",
    "pedido",
    "correo",
    "teléfono",
    "telefono",
    "no funciona",
    "mi esim",
    "mi e-sim",
)


def detect_ticket_language(*, message: str, hint: Optional[str] = None) -> str:
    """Return a short language code (en, ar, es, …). Hint wins if supported."""
    cleaned_hint = (hint or "").strip().lower()[:8]
    if cleaned_hint in SUPPORTED_LANGUAGES:
        return cleaned_hint

    text = (message or "").strip()
    if not text:
        return "en"

    arabic_chars = len(_ARABIC_RE.findall(text))
    if arabic_chars >= max(3, len(text) * 0.12):
        return "ar"

    lowered = text.lower()
    if sum(1 for hint_word in _SPANISH_HINTS if hint_word in lowered) >= 2:
        return "es"

    return "en"


def language_label(code: Optional[str]) -> str:
    return SUPPORTED_LANGUAGES.get((code or "en").lower(), (code or "en").upper())
