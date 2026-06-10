"""
Regional pricing templates ported from Desktop/noorlink/esim-database.js.

Tier-2 (template) countries use these plans when no catalog row exists;
the repository can auto-insert an esim_packages row on first checkout.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# Mirrors regionalTemplates in esim-database.js
REGIONAL_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "europe": {
        "name": "Europe",
        "currency": "USD",
        "plans": {
            "basic": {"name": "Basic", "data": "5GB", "days": 7, "price": 19.99},
            "standard": {
                "name": "Standard",
                "data": "10GB",
                "days": 15,
                "price": 34.99,
                "popular": True,
            },
            "premium": {"name": "Premium", "data": "UNLIMITED*", "days": 30, "price": 69.99},
            "family": {
                "name": "Family Bundle",
                "lines": 4,
                "sharedData": "50GB",
                "days": 30,
                "price": 89.99,
            },
        },
    },
    "asia-pacific": {
        "name": "Asia Pacific",
        "currency": "USD",
        "plans": {
            "basic": {"name": "Basic", "data": "3GB", "days": 7, "price": 14.99},
            "standard": {
                "name": "Standard",
                "data": "7GB",
                "days": 15,
                "price": 24.99,
                "popular": True,
            },
            "premium": {"name": "Premium", "data": "UNLIMITED*", "days": 30, "price": 49.99},
            "family": {
                "name": "Family Bundle",
                "lines": 4,
                "sharedData": "35GB",
                "days": 30,
                "price": 79.99,
            },
        },
    },
    "middle-east": {
        "name": "Middle East",
        "currency": "USD",
        "plans": {
            "basic": {"name": "Basic", "data": "5GB", "days": 7, "price": 17.99},
            "standard": {
                "name": "Standard",
                "data": "10GB",
                "days": 15,
                "price": 29.99,
                "popular": True,
            },
            "premium": {"name": "Premium", "data": "UNLIMITED*", "days": 30, "price": 59.99},
            "family": {
                "name": "Family Bundle",
                "lines": 4,
                "sharedData": "60GB",
                "days": 30,
                "price": 94.99,
            },
        },
    },
    "africa": {
        "name": "Africa",
        "currency": "USD",
        "plans": {
            "basic": {"name": "Basic", "data": "3GB", "days": 7, "price": 12.99},
            "standard": {
                "name": "Standard",
                "data": "5GB",
                "days": 15,
                "price": 22.99,
                "popular": True,
            },
            "premium": {"name": "Premium", "data": "UNLIMITED*", "days": 30, "price": 44.99},
            "family": {
                "name": "Family Bundle",
                "lines": 4,
                "sharedData": "30GB",
                "days": 30,
                "price": 69.99,
            },
        },
    },
    "north-america": {
        "name": "North America",
        "currency": "USD",
        "plans": {
            "basic": {"name": "Basic", "data": "3GB", "days": 7, "price": 16.99},
            "standard": {
                "name": "Standard",
                "data": "10GB",
                "days": 15,
                "price": 29.99,
                "popular": True,
            },
            "premium": {"name": "Premium", "data": "UNLIMITED*", "days": 30, "price": 64.99},
            "family": {
                "name": "Family Bundle",
                "lines": 4,
                "sharedData": "80GB",
                "days": 30,
                "price": 109.99,
            },
        },
    },
    "south-america": {
        "name": "South America",
        "currency": "USD",
        "plans": {
            "basic": {"name": "Basic", "data": "3GB", "days": 7, "price": 13.99},
            "standard": {
                "name": "Standard",
                "data": "7GB",
                "days": 15,
                "price": 23.99,
                "popular": True,
            },
            "premium": {"name": "Premium", "data": "UNLIMITED*", "days": 30, "price": 44.99},
            "family": {
                "name": "Family Bundle",
                "lines": 4,
                "sharedData": "40GB",
                "days": 30,
                "price": 74.99,
            },
        },
    },
}

# PostgreSQL region_slug enum values
TEMPLATE_KEY_TO_DB_REGION: Dict[str, str] = {
    "europe": "Europe",
    "asia-pacific": "Asia",
    "middle-east": "Middle East",
    "africa": "Africa",
    "north-america": "Americas",
    "south-america": "Americas",
}

# Country slug / alias → (display name, regional template key)
# Ported from tier1Countries, addTier2Country, and determineRegion() in esim-database.js
COUNTRY_TEMPLATE_HINTS: Dict[str, Tuple[str, str]] = {
    # North America
    "usa": ("United States", "north-america"),
    "united-states": ("United States", "north-america"),
    "us": ("United States", "north-america"),
    "canada": ("Canada", "north-america"),
    "mexico": ("Mexico", "north-america"),
    "panama": ("Panama", "north-america"),
    "costa-rica": ("Costa Rica", "north-america"),
    "bahamas": ("Bahamas", "north-america"),
    # Europe
    "uk": ("United Kingdom", "europe"),
    "united-kingdom": ("United Kingdom", "europe"),
    "france": ("France", "europe"),
    "germany": ("Germany", "europe"),
    "italy": ("Italy", "europe"),
    "spain": ("Spain", "europe"),
    "netherlands": ("Netherlands", "europe"),
    "switzerland": ("Switzerland", "europe"),
    "portugal": ("Portugal", "europe"),
    "austria": ("Austria", "europe"),
    "belgium": ("Belgium", "europe"),
    "ireland": ("Ireland", "europe"),
    "sweden": ("Sweden", "europe"),
    "norway": ("Norway", "europe"),
    "denmark": ("Denmark", "europe"),
    "finland": ("Finland", "europe"),
    "iceland": ("Iceland", "europe"),
    "malta": ("Malta", "europe"),
    "europe": ("Europe", "europe"),
    # Asia Pacific
    "japan": ("Japan", "asia-pacific"),
    "china": ("China", "asia-pacific"),
    "india": ("India", "asia-pacific"),
    "australia": ("Australia", "asia-pacific"),
    "singapore": ("Singapore", "asia-pacific"),
    "thailand": ("Thailand", "asia-pacific"),
    "south-korea": ("South Korea", "asia-pacific"),
    "korea": ("South Korea", "asia-pacific"),
    "indonesia": ("Indonesia", "asia-pacific"),
    "malaysia": ("Malaysia", "asia-pacific"),
    "philippines": ("Philippines", "asia-pacific"),
    "vietnam": ("Vietnam", "asia-pacific"),
    "fiji": ("Fiji", "asia-pacific"),
    "maldives": ("Maldives", "asia-pacific"),
    # Middle East
    "saudi-arabia": ("Saudi Arabia", "middle-east"),
    "uae": ("United Arab Emirates", "middle-east"),
    "united-arab-emirates": ("United Arab Emirates", "middle-east"),
    "qatar": ("Qatar", "middle-east"),
    "kuwait": ("Kuwait", "middle-east"),
    "bahrain": ("Bahrain", "middle-east"),
    "oman": ("Oman", "middle-east"),
    "turkey": ("Turkey", "middle-east"),
    "egypt": ("Egypt", "middle-east"),
    "jordan": ("Jordan", "middle-east"),
    "lebanon": ("Lebanon", "middle-east"),
    # South America
    "brazil": ("Brazil", "south-america"),
    "argentina": ("Argentina", "south-america"),
    "chile": ("Chile", "south-america"),
    "colombia": ("Colombia", "south-america"),
    "peru": ("Peru", "south-america"),
    # Africa
    "south-africa": ("South Africa", "africa"),
    "nigeria": ("Nigeria", "africa"),
    "morocco": ("Morocco", "africa"),
}

DEFAULT_TEMPLATE_KEY = "europe"

PLAN_KEYS_ORDER: Tuple[str, ...] = ("basic", "standard", "premium", "family")


def _slugify(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    return lowered.strip("-")


def normalize_country_key(country: str) -> str:
    return _slugify(country)


def resolve_country_identity(country: str) -> Tuple[str, str]:
    """
    Return (canonical display name, regional template key).
    Unknown countries default to title-cased input + Europe template (JS parity).
    """
    key = normalize_country_key(country)
    if key in COUNTRY_TEMPLATE_HINTS:
        return COUNTRY_TEMPLATE_HINTS[key]
    display = country.strip()
    if not display:
        display = "Unknown"
    elif display.isupper() or display.islower():
        display = display.title()
    return display, DEFAULT_TEMPLATE_KEY


def infer_template_key(country: str) -> str:
    _, template_key = resolve_country_identity(country)
    return template_key


def get_template(template_key: str) -> Optional[Dict[str, Any]]:
    return REGIONAL_TEMPLATES.get(template_key)


def plan_price_cents(plan: Dict[str, Any]) -> int:
    return int(round(float(plan["price"]) * 100))


def plan_data_label(plan: Dict[str, Any]) -> str:
    return str(plan.get("sharedData") or plan.get("data") or "10GB")


def parse_data_total_gb(data_label: str) -> Optional[float]:
    upper = data_label.upper()
    if "UNLIMITED" in upper:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)\s*GB", data_label, re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1))


def select_plan_for_price(
    template: Dict[str, Any], price_cents: int
) -> Tuple[str, Dict[str, Any]]:
    """Pick plan tier by exact catalog cents, else nearest template price."""
    plans: Dict[str, Dict[str, Any]] = template["plans"]
    exact: List[Tuple[str, Dict[str, Any]]] = []
    ranked: List[Tuple[int, str, Dict[str, Any]]] = []

    for key in PLAN_KEYS_ORDER:
        plan = plans.get(key)
        if not plan:
            continue
        cents = plan_price_cents(plan)
        if cents == price_cents:
            exact.append((key, plan))
        ranked.append((abs(cents - price_cents), key, plan))

    if exact:
        for key in PLAN_KEYS_ORDER:
            for match_key, match_plan in exact:
                if match_key == key:
                    return match_key, match_plan
        return exact[0]

    ranked.sort(key=lambda item: item[0])
    _, plan_key, plan = ranked[0]
    return plan_key, plan


def build_package_slug(
    country_slug: str, plan_key: str, data_label: str, validity_days: int
) -> str:
    data_part = _slugify(data_label.replace("*", ""))
    return f"{country_slug}-{plan_key}-{data_part}-{validity_days}d"


def build_dynamic_package_payload(
    *,
    country_input: str,
    price_cents: int,
    flag_emoji: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Build an esim_packages insert payload from regional templates.
    Returns None if no template applies.
    """
    display_name, template_key = resolve_country_identity(country_input)
    template = get_template(template_key)
    if not template:
        return None

    plan_key, plan = select_plan_for_price(template, price_cents)
    data_label = plan_data_label(plan)
    validity_days = int(plan["days"])
    country_slug = normalize_country_key(display_name)
    slug = build_package_slug(country_slug, plan_key, data_label, validity_days)
    db_region = TEMPLATE_KEY_TO_DB_REGION[template_key]

    title = f"{display_name} {data_label} · {validity_days} Days"
    if plan_key == "family":
        title = f"{display_name} Family · {data_label} · {validity_days} Days"

    return {
        "slug": slug,
        "name": title,
        "country": display_name,
        "country_code": None,
        "region": db_region,
        "flag_emoji": flag_emoji,
        "data_label": data_label,
        "data_total_gb": parse_data_total_gb(data_label),
        "validity_days": validity_days,
        "price_cents": price_cents,
        "currency": template.get("currency") or "USD",
        "is_active": True,
        "is_managed": False,
        "is_featured": False,
        "tier": "regional",
        "sort_order": 9000,
        "metadata": {
            "source": "dynamic_provision",
            "template_region": template_key,
            "plan_key": plan_key,
            "template_plan_price_cents": plan_price_cents(plan),
        },
    }
