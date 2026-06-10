"""
Travel assistant: tailored itinerary + Google Maps deep links per destination.
Persists output on the order metadata JSONB column.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from app.api import supabase_repository as db

logger = logging.getLogger(__name__)

GOOGLE_MAPS_SEARCH = "https://www.google.com/maps/search/?api=1&query={query}"


def maps_deep_link(query: str) -> str:
    return GOOGLE_MAPS_SEARCH.format(query=quote_plus(query))


# Curated anchors per popular destination (extend over time)
DESTINATION_GUIDES: Dict[str, Dict[str, Any]] = {
    "Japan": {
        "timezone": "Asia/Tokyo",
        "highlights": [
            "Activate your eSIM before immigration — scan the QR while on airport Wi‑Fi.",
            "Shinkansen and metro lines have strong 5G in Tokyo, Osaka, and Kyoto.",
            "Convenience stores (konbini) accept mobile payments once data is live.",
        ],
        "maps_queries": [
            ("Arrival — Narita Airport", "Narita International Airport Tokyo"),
            ("Arrival — Haneda Airport", "Haneda Airport Tokyo"),
            ("Shibuya & Shinjuku", "Shibuya Crossing Tokyo"),
            ("Historic Kyoto", "Fushimi Inari Shrine Kyoto"),
            ("Day trip — Mt. Fuji views", "Lake Kawaguchi Fuji"),
        ],
    },
    "United States": {
        "timezone": "America/New_York",
        "highlights": [
            "Install the eSIM profile before boarding; enable data roaming on arrival.",
            "Major carriers provide LTE/5G along interstate corridors and airports.",
            "911 and emergency services work on all activated lines.",
        ],
        "maps_queries": [
            ("JFK Airport", "John F Kennedy International Airport"),
            ("LAX Airport", "Los Angeles International Airport"),
            ("Manhattan", "Times Square New York"),
            ("National Mall", "National Mall Washington DC"),
        ],
    },
    "United Kingdom": {
        "timezone": "Europe/London",
        "highlights": [
            "London Underground and national rail stations have solid 4G/5G coverage.",
            "Oyster/contactless pairs well with always-on mobile data.",
            "Keep your physical SIM for home texts if needed; use NoorLink for data.",
        ],
        "maps_queries": [
            ("Heathrow Airport", "Heathrow Airport London"),
            ("Central London", "Westminster London"),
            ("Museums", "British Museum London"),
            ("Edinburgh Old Town", "Royal Mile Edinburgh"),
        ],
    },
    "Saudi Arabia": {
        "timezone": "Asia/Riyadh",
        "highlights": [
            "Data works across Riyadh, Jeddah, and Makkah corridors.",
            "Respect local guidance for photography near holy sites.",
            "Ride-hail apps require mobile data — activate before leaving the airport.",
        ],
        "maps_queries": [
            ("King Khalid Airport Riyadh", "King Khalid International Airport"),
            ("Jeddah Corniche", "Jeddah Corniche Saudi Arabia"),
            ("Riyadh Boulevard", "Boulevard Riyadh City"),
        ],
    },
    "Turkey": {
        "timezone": "Europe/Istanbul",
        "highlights": [
            "Istanbul spans two continents — your eSIM covers both sides.",
            "Ferry Wi‑Fi is spotty; rely on cellular data on board.",
            "Grand Bazaar and Sultanahmet are walkable with offline maps saved.",
        ],
        "maps_queries": [
            ("Istanbul Airport", "Istanbul Airport"),
            ("Sultanahmet", "Hagia Sophia Istanbul"),
            ("Cappadocia", "Göreme National Park"),
        ],
    },
    "Europe": {
        "timezone": "Europe/Paris",
        "highlights": [
            "One regional plan covers Schengen borders — no manual APN changes.",
            "Enable data roaming once; networks hand off automatically.",
            "Download offline maps for subway systems in Paris, Rome, and Berlin.",
        ],
        "maps_queries": [
            ("Charles de Gaulle Airport", "Paris Charles de Gaulle Airport"),
            ("Rome Termini", "Roma Termini station"),
            ("Brandenburg Gate", "Brandenburg Gate Berlin"),
        ],
    },
}

DEFAULT_GUIDE: Dict[str, Any] = {
    "timezone": "UTC",
    "highlights": [
        "Install your eSIM using the QR code in this email before you land.",
        "Turn on cellular data and roaming after the profile shows Active.",
        "Save our support contact offline in case airport Wi‑Fi is slow.",
    ],
    "maps_queries": [
        ("International airport", "{country} international airport"),
        ("City center", "{country} city center"),
        ("Top attractions", "top tourist attractions in {country}"),
    ],
}


def _resolve_guide(country: str) -> Dict[str, Any]:
    if country in DESTINATION_GUIDES:
        return DESTINATION_GUIDES[country]
    for key, guide in DESTINATION_GUIDES.items():
        if key.lower() in country.lower() or country.lower() in key.lower():
            return guide
    return DEFAULT_GUIDE


def _build_itinerary(
    country: str,
    travel_date: Optional[date],
    highlights: List[str],
) -> List[Dict[str, str]]:
    if not travel_date:
        return [
            {
                "day": "Before you fly",
                "title": "Install & test",
                "detail": (
                    f"Add your {country} eSIM profile and send a test message "
                    "while on Wi‑Fi at home."
                ),
            },
            {
                "day": "Arrival day",
                "title": "Go live on landing",
                "detail": (
                    "Enable the NoorLink line for cellular data. "
                    "Disable your home SIM data to avoid roaming fees."
                ),
            },
            {
                "day": "During your trip",
                "title": "Stay connected",
                "detail": highlights[0] if highlights else "Use mobile data for maps and rides.",
            },
        ]

    days: List[Dict[str, str]] = [
        {
            "day": (travel_date - timedelta(days=1)).isoformat(),
            "title": "Pre-departure checklist",
            "detail": "Install eSIM, confirm profile is Enabled, and download offline maps.",
        },
        {
            "day": travel_date.isoformat(),
            "title": f"Welcome to {country}",
            "detail": (
                "Switch to your NoorLink data line at the airport. "
                + (highlights[0] if highlights else "Confirm maps load on cellular.")
            ),
        },
    ]
    for offset, title, blurb in [
        (1, "Explore & navigate", highlights[1] if len(highlights) > 1 else "Use Google Maps links below for day trips."),
        (2, "Stay on network", highlights[2] if len(highlights) > 2 else "Monitor data usage in device settings."),
    ]:
        days.append(
            {
                "day": (travel_date + timedelta(days=offset)).isoformat(),
                "title": title,
                "detail": blurb,
            }
        )
    return days


def build_travel_guide(
    *,
    country: str,
    travel_date: Optional[str] = None,
    order_number: Optional[str] = None,
) -> Dict[str, Any]:
    guide_source = _resolve_guide(country)
    parsed_date: Optional[date] = None
    if travel_date:
        try:
            parsed_date = date.fromisoformat(str(travel_date)[:10])
        except ValueError:
            parsed_date = None

    highlights = list(guide_source.get("highlights") or [])
    raw_queries = guide_source.get("maps_queries") or DEFAULT_GUIDE["maps_queries"]
    map_places: List[Dict[str, str]] = []
    for item in raw_queries:
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            label, query_template = item[0], item[1]
        elif isinstance(item, dict):
            label = item.get("label", "Place")
            query_template = item.get("query", country)
        else:
            continue
        query = str(query_template).format(country=country)
        map_places.append(
            {
                "label": str(label),
                "query": query,
                "url": maps_deep_link(query),
            }
        )

    itinerary = _build_itinerary(country, parsed_date, highlights)

    return {
        "version": 1,
        "country": country,
        "travel_date": parsed_date.isoformat() if parsed_date else None,
        "timezone": guide_source.get("timezone", "UTC"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "order_number": order_number,
        "highlights": highlights,
        "itinerary": itinerary,
        "maps": map_places,
        "maps_search_template": GOOGLE_MAPS_SEARCH,
    }


def enrich_order_with_travel_assistant(order_row: Dict[str, Any]) -> Dict[str, Any]:
    """Build guide and persist under metadata.travel_assistant."""
    country = order_row.get("country") or "your destination"
    travel_date = order_row.get("travel_date")
    if hasattr(travel_date, "isoformat"):
        travel_date = travel_date.isoformat()

    guide = build_travel_guide(
        country=country,
        travel_date=travel_date,
        order_number=order_row.get("order_number"),
    )
    db.merge_order_metadata(
        order_row["order_number"],
        {"travel_assistant": guide},
    )
    logger.info(
        "Travel assistant saved for order %s (%s)",
        order_row.get("order_number"),
        country,
    )
    return guide
