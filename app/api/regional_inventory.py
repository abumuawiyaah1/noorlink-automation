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
            "basic": {"name": "Basic", "data": "3GB", "days": 7, "price": 12.99},
            "standard": {
                "name": "Standard",
                "data": "10GB",
                "days": 15,
                "price": 24.99,
                "popular": True,
            },
            "plus": {"name": "Plus", "data": "20GB", "days": 30, "price": 39.99},
            "premium": {"name": "Premium", "data": "UNLIMITED*", "days": 30, "price": 59.99},
            "family": {
                "name": "Family Bundle",
                "lines": 4,
                "sharedData": "50GB",
                "days": 30,
                "price": 79.99,
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
                "data": "10GB",
                "days": 15,
                "price": 29.99,
                "popular": True,
            },
            "plus": {"name": "Plus", "data": "20GB", "days": 30, "price": 44.99},
            "premium": {"name": "Premium", "data": "UNLIMITED*", "days": 30, "price": 54.99},
            "family": {
                "name": "Family Bundle",
                "lines": 4,
                "sharedData": "40GB",
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
            "plus": {"name": "Plus", "data": "20GB", "days": 30, "price": 44.99},
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
            "plus": {"name": "Plus", "data": "15GB", "days": 30, "price": 34.99},
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
            "basic": {"name": "Basic", "data": "3GB", "days": 7, "price": 14.99},
            "standard": {
                "name": "Standard",
                "data": "10GB",
                "days": 15,
                "price": 24.99,
                "popular": True,
            },
            "plus": {"name": "Plus", "data": "20GB", "days": 30, "price": 39.99},
            "premium": {"name": "Premium", "data": "UNLIMITED*", "days": 30, "price": 54.99},
            "family": {
                "name": "Family Bundle",
                "lines": 4,
                "sharedData": "50GB",
                "days": 30,
                "price": 89.99,
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
                "data": "10GB",
                "days": 15,
                "price": 24.99,
                "popular": True,
            },
            "plus": {"name": "Plus", "data": "20GB", "days": 30, "price": 39.99},
            "premium": {"name": "Premium", "data": "UNLIMITED*", "days": 30, "price": 49.99},
            "family": {
                "name": "Family Bundle",
                "lines": 4,
                "sharedData": "40GB",
                "days": 30,
                "price": 74.99,
            },
        },
    },
    "global": {
        "name": "Global",
        "currency": "USD",
        "plans": {
            "basic": {"name": "Basic", "data": "5GB", "days": 7, "price": 24.99},
            "standard": {
                "name": "Standard",
                "data": "15GB",
                "days": 15,
                "price": 44.99,
                "popular": True,
            },
            "plus": {"name": "Plus", "data": "30GB", "days": 30, "price": 69.99},
            "premium": {"name": "Premium", "data": "UNLIMITED*", "days": 30, "price": 89.99},
            "family": {
                "name": "Family Bundle",
                "lines": 4,
                "sharedData": "60GB",
                "days": 30,
                "price": 119.99,
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
    "global": "Global",
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

PLAN_KEYS_ORDER: Tuple[str, ...] = ("basic", "standard", "plus", "premium", "family")


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


# region_id values used by pricing_rules REGION scope (see migrations)
TEMPLATE_KEY_TO_REGION_ID: Dict[str, str] = {
    "europe": "europe",
    "asia-pacific": "asia",
    "middle-east": "middle-east",
    "africa": "africa",
    "north-america": "americas",
    "south-america": "americas",
    "global": "global",
}


def _plan_category_for_template(plan_key: str, data_label: str) -> str:
    if plan_key == "family":
        return "FLEXIBLE"
    if "UNLIMITED" in data_label.upper():
        return "UNLIMITED"
    return "FIXED"


def build_template_mobile_data_rows(country_input: str) -> List[Dict[str, Any]]:
    """
    Synthesize mobile_data_plans-shaped rows from regional templates.

    Used by /api/v1/plans when a country has no seeded catalog rows, so every
    destination still returns browsable priced plans (checkout already
    provisions matching esim_packages from the same templates).
    """
    display_name, template_key = resolve_country_identity(country_input)
    template = get_template(template_key)
    if not template:
        return []

    country_slug = normalize_country_key(display_name)
    # Prefer the request slug when it's already a known hint key
    request_slug = normalize_country_key(country_input)
    if request_slug in COUNTRY_TEMPLATE_HINTS:
        country_slug = request_slug
        # Canonical aliases
        if country_slug in {"united-states", "us"}:
            country_slug = "usa"
        elif country_slug in {"united-kingdom", "gb"}:
            country_slug = "uk"
        elif country_slug in {"united-arab-emirates"}:
            country_slug = "uae"

    region_id = TEMPLATE_KEY_TO_REGION_ID.get(template_key, template_key)
    currency = template.get("currency") or "USD"
    rows: List[Dict[str, Any]] = []

    for sort_index, plan_key in enumerate(PLAN_KEYS_ORDER):
        plan = template["plans"].get(plan_key)
        if not plan:
            continue

        data_label = plan_data_label(plan)
        validity_days = int(plan["days"])
        data_gb = parse_data_total_gb(data_label)
        price = float(plan["price"])
        is_featured = bool(plan.get("popular"))
        category = _plan_category_for_template(plan_key, data_label)

        if plan_key == "family":
            name = f"{display_name} Family · {data_label}"
        elif category == "UNLIMITED":
            name = f"{display_name} Unlimited · {validity_days} Days"
        else:
            name = f"{display_name} {data_label} · {validity_days} Days"

        rows.append(
            {
                "id": f"tmpl-{country_slug}-{plan_key}",
                "country_id": country_slug,
                "country_name": display_name,
                "name": name,
                "data_gb": data_gb,
                "duration_days": validity_days,
                "price": price,
                "override_price": price,
                "price_cents": plan_price_cents(plan),
                "currency": currency,
                "pricing_strategy": "MANUAL",
                "plan_category": category,
                "is_featured": is_featured,
                "is_active": True,
                "sort_order": (sort_index + 1) * 10,
                "region_id": region_id,
                "is_rechargeable": plan_key == "family",
            }
        )

    return rows


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
    regional_id = resolve_regional_product_slug(country_input)
    if not regional_id:
        regional_id = resolve_regional_product_by_display_name(country_input)
    if regional_id:
        return build_regional_package_payload(
            regional_product_id=regional_id,
            price_cents=price_cents,
            flag_emoji=flag_emoji,
        )

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


# ── Multi-country regional products (one eSIM, many countries) ─────────────

REGIONAL_PRODUCTS: Dict[str, Dict[str, Any]] = {
    "regional-europe": {
        "route_slug": "europe",
        "display_name": "Europe Regional",
        "short_name": "Europe",
        "flag_emoji": "🌍",
        "template_key": "europe",
        "hero_tagline": "One plan across Europe — install once, cross borders freely.",
        "countries": [
            "United Kingdom",
            "France",
            "Germany",
            "Italy",
            "Spain",
            "Netherlands",
            "Switzerland",
            "Portugal",
            "Austria",
            "Belgium",
            "Ireland",
            "Sweden",
            "Norway",
            "Denmark",
            "Finland",
            "Iceland",
            "Malta",
        ],
        "exclusions": ["Turkey", "Russia", "Belarus", "Ukraine"],
        "single_country_slug": "france",
    },
    "regional-north-america": {
        "route_slug": "north-america",
        "display_name": "North America Regional",
        "short_name": "North America",
        "flag_emoji": "🌎",
        "template_key": "north-america",
        "hero_tagline": "USA, Canada & Mexico on one eSIM — no plan swap at the border.",
        "countries": [
            "United States",
            "Canada",
            "Mexico",
            "Panama",
            "Costa Rica",
            "Bahamas",
        ],
        "exclusions": [],
        "single_country_slug": "usa",
    },
    "regional-asia-pacific": {
        "route_slug": "asia-pacific",
        "display_name": "Asia Pacific Regional",
        "short_name": "Asia Pacific",
        "flag_emoji": "🌏",
        "template_key": "asia-pacific",
        "hero_tagline": "Japan to Thailand and beyond — one QR for your whole region.",
        "countries": [
            "Japan",
            "China",
            "India",
            "Australia",
            "Singapore",
            "Thailand",
            "South Korea",
            "Indonesia",
            "Malaysia",
            "Philippines",
            "Vietnam",
            "Fiji",
            "Maldives",
        ],
        "exclusions": [],
        "single_country_slug": "japan",
    },
    "regional-middle-east": {
        "route_slug": "middle-east",
        "display_name": "Middle East Regional",
        "short_name": "Middle East",
        "flag_emoji": "🕌",
        "template_key": "middle-east",
        "hero_tagline": "Gulf, Turkey, and more — one plan for multi-stop Middle East trips.",
        "countries": [
            "Saudi Arabia",
            "United Arab Emirates",
            "Qatar",
            "Kuwait",
            "Bahrain",
            "Oman",
            "Turkey",
            "Egypt",
            "Jordan",
            "Lebanon",
        ],
        "exclusions": [],
        "single_country_slug": "turkey",
    },
    "regional-africa": {
        "route_slug": "africa",
        "display_name": "Africa Regional",
        "short_name": "Africa",
        "flag_emoji": "🌍",
        "template_key": "africa",
        "hero_tagline": "Safaris, cities, and coastlines — one plan across African destinations.",
        "countries": [
            "South Africa",
            "Nigeria",
            "Morocco",
            "Kenya",
            "Ghana",
            "Egypt",
            "Tanzania",
            "Tunisia",
        ],
        "exclusions": [],
        "single_country_slug": "south-africa",
    },
    "regional-south-america": {
        "route_slug": "south-america",
        "display_name": "South America Regional",
        "short_name": "South America",
        "flag_emoji": "🌎",
        "template_key": "south-america",
        "hero_tagline": "Brazil to Patagonia — one eSIM for multi-country South America trips.",
        "countries": [
            "Brazil",
            "Argentina",
            "Chile",
            "Colombia",
            "Peru",
            "Uruguay",
            "Ecuador",
        ],
        "exclusions": [],
        "single_country_slug": "brazil",
    },
    "regional-global": {
        "route_slug": "global",
        "display_name": "Global Regional",
        "short_name": "Global",
        "flag_emoji": "🌐",
        "template_key": "global",
        "hero_tagline": "100+ countries on one plan — for long-haul and multi-region journeys.",
        "countries": [
            "United States",
            "Canada",
            "United Kingdom",
            "France",
            "Germany",
            "Italy",
            "Spain",
            "Japan",
            "Australia",
            "Singapore",
            "United Arab Emirates",
            "Turkey",
            "Mexico",
            "Brazil",
            "South Africa",
            "Thailand",
            "Saudi Arabia",
        ],
        "exclusions": [],
        "single_country_slug": "usa",
    },
}

REGIONAL_ROUTE_TO_PRODUCT: Dict[str, str] = {
    "europe": "regional-europe",
    "regional-europe": "regional-europe",
    "north-america": "regional-north-america",
    "regional-north-america": "regional-north-america",
    "asia-pacific": "regional-asia-pacific",
    "asia": "regional-asia-pacific",
    "regional-asia-pacific": "regional-asia-pacific",
    "middle-east": "regional-middle-east",
    "regional-middle-east": "regional-middle-east",
    "africa": "regional-africa",
    "regional-africa": "regional-africa",
    "south-america": "regional-south-america",
    "latin-america": "regional-south-america",
    "latam": "regional-south-america",
    "regional-south-america": "regional-south-america",
    "global": "regional-global",
    "worldwide": "regional-global",
    "world": "regional-global",
    "regional-global": "regional-global",
}


def resolve_regional_product_slug(slug: str) -> Optional[str]:
    """Map URL/API slug to a regional product id (e.g. europe → regional-europe)."""
    key = normalize_country_key(slug)
    product_id = REGIONAL_ROUTE_TO_PRODUCT.get(key)
    if product_id and product_id in REGIONAL_PRODUCTS:
        return product_id
    if key.startswith("regional-") and key in REGIONAL_PRODUCTS:
        return key
    return None


def resolve_regional_product_by_display_name(name: str) -> Optional[str]:
    """Resolve checkout/display labels like 'Europe Regional'."""
    normalized = name.strip().lower()
    if not normalized:
        return None
    for product_id, product in REGIONAL_PRODUCTS.items():
        display = str(product["display_name"]).lower()
        if normalized == display or normalized.startswith(display):
            return product_id
    return None


def get_regional_product(product_id: str) -> Optional[Dict[str, Any]]:
    return REGIONAL_PRODUCTS.get(product_id)


def build_regional_product_rows(product_id: str) -> List[Dict[str, Any]]:
    """Browsable plans for a multi-country regional SKU."""
    product = REGIONAL_PRODUCTS.get(product_id)
    if not product:
        return []

    template_key = str(product["template_key"])
    template = get_template(template_key)
    if not template:
        return []

    display_name = str(product["display_name"])
    region_id = TEMPLATE_KEY_TO_REGION_ID.get(template_key, template_key)
    currency = template.get("currency") or "USD"
    rows: List[Dict[str, Any]] = []

    for sort_index, plan_key in enumerate(PLAN_KEYS_ORDER):
        plan = template["plans"].get(plan_key)
        if not plan:
            continue

        data_label = plan_data_label(plan)
        validity_days = int(plan["days"])
        data_gb = parse_data_total_gb(data_label)
        price = float(plan["price"])
        is_featured = bool(plan.get("popular"))
        category = _plan_category_for_template(plan_key, data_label)

        if plan_key == "family":
            name = f"{display_name} Family · {data_label}"
        elif category == "UNLIMITED":
            name = f"{display_name} Unlimited · {validity_days} Days"
        else:
            name = f"{display_name} {data_label} · {validity_days} Days"

        rows.append(
            {
                "id": f"regional-{product_id.replace('regional-', '')}-{plan_key}",
                "country_id": product_id,
                "country_name": display_name,
                "name": name,
                "data_gb": data_gb,
                "duration_days": validity_days,
                "price": price,
                "override_price": price,
                "price_cents": plan_price_cents(plan),
                "currency": currency,
                "pricing_strategy": "MANUAL",
                "plan_category": category,
                "is_featured": is_featured,
                "is_active": True,
                "sort_order": (sort_index + 1) * 10,
                "region_id": region_id,
                "is_rechargeable": plan_key == "family",
                "flag_emoji": product.get("flag_emoji"),
                "product_type": "regional",
            }
        )

    return rows


def build_regional_package_payload(
    *,
    regional_product_id: str,
    price_cents: int,
    flag_emoji: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Build esim_packages insert payload for a regional multi-country product."""
    product = REGIONAL_PRODUCTS.get(regional_product_id)
    if not product:
        return None

    template_key = str(product["template_key"])
    template = get_template(template_key)
    if not template:
        return None

    plan_key, plan = select_plan_for_price(template, price_cents)
    data_label = plan_data_label(plan)
    validity_days = int(plan["days"])
    display_name = str(product["display_name"])
    route_slug = str(product["route_slug"])
    slug = build_package_slug(
        regional_product_id.replace("regional-", "regional-"),
        plan_key,
        data_label,
        validity_days,
    )
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
        "flag_emoji": flag_emoji or product.get("flag_emoji"),
        "data_label": data_label,
        "data_total_gb": parse_data_total_gb(data_label),
        "validity_days": validity_days,
        "price_cents": price_cents,
        "currency": template.get("currency") or "USD",
        "is_active": True,
        "is_managed": False,
        "is_featured": False,
        "tier": "regional",
        "sort_order": 8000,
        "metadata": {
            "source": "dynamic_provision",
            "product_type": "regional",
            "region_slug": route_slug,
            "regional_product_id": regional_product_id,
            "template_region": template_key,
            "plan_key": plan_key,
            "coverage_countries": product.get("countries") or [],
            "coverage_exclusions": product.get("exclusions") or [],
            "template_plan_price_cents": plan_price_cents(plan),
        },
    }
