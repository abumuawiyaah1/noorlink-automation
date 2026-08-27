"""
Shared NoorLink email brand chrome (colors, logo image, support signature).

Matches the live site: primary teal #0F3D3E + accent orange #FF9500.
Logo: https://noorlink.co/images/logo.png
"""

from __future__ import annotations

import html
from typing import Optional
from urllib.parse import quote

# Brand tokens (aligned with noorlink.co CSS)
PRIMARY = "#0F3D3E"
PRIMARY_DARK = "#05191A"
ACCENT = "#FF9500"
BG = "#F3F5F7"
SURFACE = "#FFFFFF"
TEXT = "#111827"
MUTED = "#6B7280"
WHATSAPP = "#25D366"
WHATSAPP_NUMBER = "17184729390"

# Hosted brand mark (Next.js public/images/logo.png)
DEFAULT_LOGO_URL = "https://noorlink.co/images/logo.png"


def brand_logo(*, href: str, logo_url: Optional[str] = None, height: int = 56) -> str:
    """PNG logo for email clients (absolute HTTPS URL required)."""
    safe_href = html.escape(href.rstrip("/"))
    src = html.escape((logo_url or DEFAULT_LOGO_URL).strip())
    return f"""
      <a href="{safe_href}" style="text-decoration:none;display:inline-block;">
        <img src="{src}"
             width="{height}"
             height="{height}"
             alt="NoorLink"
             style="display:block;width:{height}px;height:{height}px;border:0;border-radius:12px;background:{SURFACE};"/>
      </a>
    """


def brand_wordmark(*, href: str) -> str:
    safe_href = html.escape(href.rstrip("/"))
    return f"""
      <a href="{safe_href}" style="text-decoration:none;display:inline-block;vertical-align:middle;">
        <span style="font-family:Arial,Helvetica,sans-serif;font-size:26px;font-weight:800;letter-spacing:-0.02em;color:{SURFACE};">
          Noor<span style="color:{ACCENT};">Link</span><sup style="font-size:10px;color:{ACCENT};margin-left:2px;">TM</sup>
        </span>
      </a>
    """


def brand_header_lockup(*, href: str, logo_url: Optional[str] = None) -> str:
    """Logo image + wordmark side by side."""
    return f"""
      <table cellpadding="0" cellspacing="0" role="presentation">
        <tr>
          <td style="vertical-align:middle;padding-right:14px;">
            {brand_logo(href=href, logo_url=logo_url, height=52)}
          </td>
          <td style="vertical-align:middle;">
            {brand_wordmark(href=href)}
          </td>
        </tr>
      </table>
    """


def cta_button(*, href: str, label: str) -> str:
    return f"""
      <a href="{html.escape(href)}"
         style="display:inline-block;background:{ACCENT};color:{PRIMARY_DARK};padding:14px 28px;border-radius:999px;text-decoration:none;font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:700;">
        {html.escape(label)}
      </a>
    """


def review_request_block(
    *,
    app_url: str,
    order_number: Optional[str] = None,
    google_review_url: Optional[str] = None,
) -> str:
    """Post-trip review ask — matches NoorLink brand card styling."""
    base = app_url.rstrip("/")
    review_page = f"{base}/review"
    if order_number:
        review_page = f"{review_page}?orderId={quote(order_number.strip())}"
    feedback_href = f"{base}/support?subject={quote('Service review')}"
    if order_number:
        feedback_href = (
            f"{feedback_href}&orderId={quote(order_number.strip())}"
            f"&message={quote(f'Hi NoorLink, here is my feedback on order {order_number.strip()}:')}"
        )

    google_btn = ""
    if (google_review_url or "").strip():
        google_btn = f"""
          <a href="{html.escape(google_review_url.strip())}"
             style="display:inline-block;background:{PRIMARY};color:#ffffff;padding:12px 22px;border-radius:999px;text-decoration:none;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:700;margin-right:8px;margin-bottom:8px;">
            Rate us on Google
          </a>
        """

    return f"""
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:28px;background:#FFF8F0;border:1px solid #FFE0B2;border-radius:12px;">
        <tr>
          <td style="padding:22px 24px;font-family:Arial,Helvetica,sans-serif;">
            <p style="margin:0 0 8px;font-size:11px;letter-spacing:0.12em;text-transform:uppercase;color:{ACCENT};font-weight:700;">
              Your feedback matters
            </p>
            <h3 style="margin:0 0 10px;color:{PRIMARY};font-size:17px;font-weight:700;">
              Leave us a review
            </h3>
            <p style="margin:0 0 16px;font-size:14px;line-height:1.55;color:{TEXT};">
              If you choose to rate our service, you will have an opportunity to leave a
              comment as well. Please tell us how we can help you on your next trip — and
              any improvements we can make at NoorLink.
            </p>
            <p style="margin:0 0 16px;">
              {google_btn}
              <a href="{html.escape(review_page)}"
                 style="display:inline-block;background:{ACCENT};color:{PRIMARY_DARK};padding:12px 22px;border-radius:999px;text-decoration:none;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:700;margin-right:8px;margin-bottom:8px;">
                Share your experience
              </a>
              <a href="{feedback_href}"
                 style="display:inline-block;border:2px solid {PRIMARY};color:{PRIMARY};padding:10px 20px;border-radius:999px;text-decoration:none;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:700;margin-bottom:8px;">
                Send private feedback
              </a>
            </p>
          </td>
        </tr>
      </table>
    """


def support_signature(
    *,
    app_url: str,
    tip: Optional[str] = None,
    logo_url: Optional[str] = None,
) -> str:
    """Professional footer: tech help + WhatsApp + support links."""
    base = app_url.rstrip("/")
    support = f"{base}/support"
    wa = f"https://wa.me/{WHATSAPP_NUMBER}"
    tip_html = ""
    if tip:
        tip_html = f"""
          <tr>
            <td style="padding:0 0 16px;">
              <table width="100%" cellpadding="0" cellspacing="0" style="background:#FFF8F0;border:1px solid #FFE0B2;border-radius:10px;">
                <tr>
                  <td style="padding:14px 16px;font-family:Arial,Helvetica,sans-serif;font-size:13px;line-height:1.5;color:{TEXT};">
                    <strong style="color:{PRIMARY};">Tech tip:</strong>
                    {html.escape(tip)}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        """

    return f"""
      <table width="100%" cellpadding="0" cellspacing="0">
        {tip_html}
        <tr>
          <td style="padding:0 0 12px;font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:1.55;color:{TEXT};">
            <strong style="color:{PRIMARY};">Need help installing or activating?</strong><br/>
            Our team is online 24/7 — reply to this email or message us on WhatsApp.
          </td>
        </tr>
        <tr>
          <td style="padding:0 0 18px;">
            <a href="{html.escape(wa)}"
               style="display:inline-block;background:{WHATSAPP};color:#ffffff;padding:10px 18px;border-radius:999px;text-decoration:none;font-family:Arial,Helvetica,sans-serif;font-size:13px;font-weight:700;margin-right:8px;">
              WhatsApp support
            </a>
            <a href="{html.escape(support)}"
               style="display:inline-block;background:{PRIMARY};color:#ffffff;padding:10px 18px;border-radius:999px;text-decoration:none;font-family:Arial,Helvetica,sans-serif;font-size:13px;font-weight:700;">
              Support center
            </a>
          </td>
        </tr>
        <tr>
          <td style="padding-top:12px;border-top:1px solid #E5E7EB;">
            <table cellpadding="0" cellspacing="0" role="presentation">
              <tr>
                <td style="vertical-align:middle;padding-right:10px;">
                  {brand_logo(href=base, logo_url=logo_url, height=36)}
                </td>
                <td style="vertical-align:middle;font-family:Arial,Helvetica,sans-serif;font-size:12px;line-height:1.5;color:{MUTED};">
                  <strong style="color:{PRIMARY};">Noor<span style="color:{ACCENT};">Link</span></strong>
                  · Travel eSIM for Umrah, Hajj &amp; journeys worldwide<br/>
                  <a href="{html.escape(base)}" style="color:{PRIMARY};text-decoration:none;">noorlink.co</a>
                  · <a href="mailto:support@noorlink.co" style="color:{PRIMARY};text-decoration:none;">support@noorlink.co</a>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    """


def wrap_branded_email(
    *,
    eyebrow: str,
    title: str,
    body_html: str,
    app_url: str,
    tip: Optional[str] = None,
    logo_url: Optional[str] = None,
) -> str:
    """Full HTML document with NoorLink logo header + support signature."""
    from app.core.config import get_settings

    settings = get_settings()
    resolved_logo = (logo_url or getattr(settings, "email_logo_url", "") or DEFAULT_LOGO_URL).strip()
    base = app_url.rstrip("/")
    lockup = brand_header_lockup(href=base, logo_url=resolved_logo)
    signature = support_signature(app_url=base, tip=tip, logo_url=resolved_logo)
    safe_eyebrow = html.escape(eyebrow.upper())
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>NoorLink</title>
</head>
<body style="margin:0;padding:0;background:{BG};">
  <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:{BG};padding:28px 12px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" role="presentation" style="width:100%;max-width:600px;background:{SURFACE};border-radius:16px;overflow:hidden;border:1px solid #E5E7EB;">
        <tr>
          <td style="background:{PRIMARY};padding:28px 32px 24px;">
            {lockup}
            <p style="margin:18px 0 0;font-family:Arial,Helvetica,sans-serif;font-size:11px;letter-spacing:0.14em;text-transform:uppercase;color:{ACCENT};font-weight:700;">
              {safe_eyebrow}
            </p>
            <h1 style="margin:8px 0 0;font-family:Georgia,'Times New Roman',serif;font-size:26px;line-height:1.25;font-weight:normal;color:{SURFACE};">
              {title}
            </h1>
          </td>
        </tr>
        <tr>
          <td style="padding:28px 32px;font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.6;color:{TEXT};">
            {body_html}
          </td>
        </tr>
        <tr>
          <td style="padding:8px 32px 28px;background:{SURFACE};">
            {signature}
          </td>
        </tr>
        <tr>
          <td style="padding:14px 32px;background:{PRIMARY_DARK};text-align:center;font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#9CA3AF;">
            You’re receiving this because you interacted with NoorLink.
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""
