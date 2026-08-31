"""Static copy and links for the admin social media hub."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

SOCIAL_QUICK_LINKS: Tuple[Dict[str, str], ...] = (
    {
        "title": "Create post (Business Suite)",
        "href": "https://business.facebook.com/latest/composer/",
    },
    {
        "title": "Meta Business Suite",
        "href": "https://business.facebook.com/",
    },
    {
        "title": "Instagram — @noorlinkesim",
        "href": "https://www.instagram.com/noorlinkesim/",
    },
    {
        "title": "Facebook Page — NoorLink",
        "href": "https://www.facebook.com/profile.php?id=61593708492331",
    },
    {
        "title": "Accounts Center",
        "href": "https://accountscenter.facebook.com/profiles",
    },
)

SOCIAL_POST_WORKFLOW: Tuple[str, ...] = (
    "Upload partner photos or videos in the Media library below.",
    "Copy a caption template and adjust the destination if needed.",
    "Post to Facebook via Business Suite composer.",
    "Post the same image + caption on Instagram (@noorlinkesim) until cross-posting is linked.",
    "Mark the asset Posted and delete from the library once saved elsewhere if space is tight.",
)

SOCIAL_CAPTION_TEMPLATES: Tuple[Dict[str, str], ...] = (
    {
        "label": "Brand intro",
        "text": (
            "Stay connected abroad — without swapping SIMs.\n\n"
            "NoorLink eSIM covers 190+ destinations.\n"
            "Install before you fly, land ready to go.\n\n"
            "→ noorlink.co/destinations\n\n"
            "#eSIM #TravelTech #StayConnected #NoorLink"
        ),
    },
    {
        "label": "Destination spotlight",
        "text": (
            "Heading to [destination]? Install your eSIM before you fly.\n\n"
            "• 190+ destinations on NoorLink\n"
            "• QR by email — install at home\n"
            "• Hotspot included on every plan\n\n"
            "Browse plans → noorlink.co/destinations\n\n"
            "#eSIM #Travel #NoorLink"
        ),
    },
    {
        "label": "Umrah / Hajj",
        "text": (
            "Pilgrimage travel is easier when data works on arrival.\n\n"
            "Install your NoorLink eSIM before you fly so maps, messages, "
            "and group coordination work in Makkah and Madinah.\n\n"
            "See Umrah & Hajj plans → noorlink.co/hajj-umrah\n\n"
            "#Umrah #Hajj #eSIM #NoorLink"
        ),
    },
)

SOCIAL_BRAND_ASSETS: Tuple[Dict[str, str], ...] = (
    {"label": "Profile avatar (IG / FB)", "path": "/images/logo-profile.png"},
    {"label": "Full logo", "path": "/images/logo.png"},
    {"label": "Share image (1200×630)", "path": "/images/og.jpg"},
    {"label": "Travel hero photo", "path": "/images/traveler.jpg"},
    {"label": "eSIM product photo", "path": "/images/sim-card.jpg"},
    {"label": "Brand hero", "path": "/images/hero.jpg"},
)

SITE_BASE = "https://noorlink.co"

STATUSES: Tuple[Tuple[str, str], ...] = (
    ("new", "New"),
    ("ready", "Ready to post"),
    ("posted", "Posted"),
)


def status_label(code: str) -> str:
    for key, label in STATUSES:
        if key == code:
            return label
    return code
