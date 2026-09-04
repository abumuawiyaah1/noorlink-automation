"""GSMA LPA formatting, branded QR images, and one-tap install links."""

from __future__ import annotations

import base64
import logging
from io import BytesIO
from typing import Any, Dict, Optional
from urllib.parse import quote, urlencode
from urllib.request import urlopen

import qrcode

logger = logging.getLogger(__name__)

DEFAULT_LOGO_URL = "https://noorlink.co/images/logo.png"
# Teal modules on white — matches NoorLink primary #0F3D3E
QR_FILL = "#0F3D3E"
QR_BACK = "#FFFFFF"
# Center logo ratio that still scans with ERROR_CORRECT_H
LOGO_RATIO = 0.22


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


def normalize_lpa(lpa_string: str) -> str:
    return (lpa_string or "").strip()


def matching_id_from_lpa(lpa_string: str) -> str:
    parts = normalize_lpa(lpa_string).split("$")
    if len(parts) >= 3 and parts[-1]:
        return parts[-1].strip()
    return normalize_lpa(lpa_string)


def smdp_from_lpa(lpa_string: str) -> str:
    parts = normalize_lpa(lpa_string).split("$")
    if len(parts) >= 2:
        return parts[1].strip()
    return ""


def ios_tap_link(lpa_string: str) -> str:
    """Apple one-tap eSIM install (iOS 17.4+)."""
    lpa = normalize_lpa(lpa_string)
    if not lpa:
        return ""
    return (
        "https://esimsetup.apple.com/esim_qrcode_provisioning"
        f"?carddata={quote(lpa, safe='')}"
    )


def android_tap_link(lpa_string: str) -> str:
    """Android one-tap eSIM install (Android 10+ where supported)."""
    lpa = normalize_lpa(lpa_string)
    if not lpa:
        return ""
    return (
        "https://esimsetup.android.com/esim_qrcode_provisioning"
        f"?carddata={quote(lpa, safe='')}"
    )


def branded_qr_image_url(
    lpa_string: str,
    *,
    logo_url: Optional[str] = None,
    size: int = 400,
) -> str:
    """
    HTTPS QR image URL with NoorLink logo centered (email-safe).

    Uses QuickChart with high error correction so the center mark still scans.
    """
    lpa = normalize_lpa(lpa_string)
    if not lpa:
        raise ValueError("lpa_string is required")
    logo = (logo_url or DEFAULT_LOGO_URL).strip() or DEFAULT_LOGO_URL
    params = {
        "text": lpa,
        "size": int(size),
        "ecLevel": "H",
        "margin": 2,
        "dark": "0F3D3E",
        "light": "ffffff",
        "centerImageUrl": logo,
        "centerImageSizeRatio": str(LOGO_RATIO),
    }
    return f"https://quickchart.io/qr?{urlencode(params)}"


def _load_logo_image(logo_url: Optional[str] = None):
    from PIL import Image

    url = (logo_url or DEFAULT_LOGO_URL).strip() or DEFAULT_LOGO_URL
    try:
        with urlopen(url, timeout=8) as response:  # noqa: S310 — fixed brand CDN URL
            return Image.open(BytesIO(response.read())).convert("RGBA")
    except Exception as exc:
        logger.warning("Could not load brand logo for QR overlay (%s); plain QR", exc)
        return None


def generate_branded_qr_png_bytes(
    lpa_string: str,
    *,
    logo_url: Optional[str] = None,
    box_size: int = 10,
) -> bytes:
    """Render a teal QR PNG with optional centered NoorLink logo."""
    from PIL import Image as PILImage

    lpa = normalize_lpa(lpa_string)
    if not lpa:
        raise ValueError("lpa_string is required")

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=2,
    )
    qr.add_data(lpa)
    qr.make(fit=True)

    image = qr.make_image(fill_color=QR_FILL, back_color=QR_BACK).convert("RGBA")

    logo = _load_logo_image(logo_url)
    if logo is not None:
        qr_w, qr_h = image.size
        logo_max = int(min(qr_w, qr_h) * LOGO_RATIO)
        logo.thumbnail((logo_max, logo_max), PILImage.Resampling.LANCZOS)
        pad = 8
        badge_size = (logo.size[0] + pad * 2, logo.size[1] + pad * 2)
        badge = PILImage.new("RGBA", badge_size, (255, 255, 255, 255))
        badge.paste(logo, (pad, pad), logo)
        pos = ((qr_w - badge.size[0]) // 2, (qr_h - badge.size[1]) // 2)
        image.paste(badge, pos, badge)

    buffer = BytesIO()
    image.convert("RGB").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def generate_qr_code_base64(lpa_string: str) -> str:
    """
    Encode an LPA string as a branded PNG QR code.

    Returns a data-URI suitable for HTML: data:image/png;base64,...
    """
    png = generate_branded_qr_png_bytes(lpa_string)
    encoded = base64.b64encode(png).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_install_artifacts(
    lpa_string: str,
    *,
    logo_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Customer-facing install bundle from an LPA string.

    qr_code_url is an HTTPS QuickChart URL (logo in center) so emails render
    reliably; ios/android links enable one-tap install without scanning.
    """
    lpa = normalize_lpa(lpa_string)
    if not lpa:
        return {
            "lpa_string": "",
            "qr_code_url": "",
            "ios_tap_link": "",
            "android_tap_link": "",
            "activation_code": "",
            "smdp_address": "",
        }
    logo = (logo_url or DEFAULT_LOGO_URL).strip() or DEFAULT_LOGO_URL
    return {
        "lpa_string": lpa,
        "qr_code_url": branded_qr_image_url(lpa, logo_url=logo),
        "ios_tap_link": ios_tap_link(lpa),
        "android_tap_link": android_tap_link(lpa),
        "activation_code": matching_id_from_lpa(lpa),
        "smdp_address": smdp_from_lpa(lpa),
    }


def resolve_lpa_from_order_row(row: Dict[str, Any]) -> str:
    """Prefer orders.lpa_string, then metadata.fulfillment.lpa_string."""
    direct = normalize_lpa(str(row.get("lpa_string") or ""))
    if direct:
        return direct
    metadata = row.get("metadata") or {}
    if not isinstance(metadata, dict):
        return ""
    fulfillment = metadata.get("fulfillment") or {}
    if not isinstance(fulfillment, dict):
        return ""
    return normalize_lpa(str(fulfillment.get("lpa_string") or ""))
