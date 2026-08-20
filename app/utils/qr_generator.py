"""GSMA LPA formatting and QR code image generation for eSIM activation."""

from __future__ import annotations

import base64
from io import BytesIO

import qrcode


def format_lpa_string(smdp_address: str, activation_code: str) -> str:
    """
    Build a GSMA LPA activation string.

    Format: LPA:1$<SM-DP+ address>$<activation code>
    """
    smdp = (smdp_address or "").strip()
    code = (activation_code or "").strip()
    if not smdp or not code:
        raise ValueError("smdp_address and activation_code are required")
    return f"LPA:1${smdp}${code}"


def generate_qr_code_base64(lpa_string: str) -> str:
    """
    Encode an LPA string as a PNG QR code.

    Returns a data-URI suitable for email/HTML: data:image/png;base64,...
    """
    if not (lpa_string or "").strip():
        raise ValueError("lpa_string is required")

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=2,
    )
    qr.add_data(lpa_string.strip())
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
