"""
In-memory search analytics counter for hero destination lookups.

Thread-safe for concurrent FastAPI requests. Can be swapped for Supabase
persistence later without changing the analytics router contract.
"""

from __future__ import annotations

import threading
from typing import Dict, List, TypedDict


class PopularDestination(TypedDict):
    destination: str
    query: str
    href: str
    flag: str


class TrendingDestination(PopularDestination):
    count: int


# High-intent conversion streams — always returned as fallback for the frontend.
FALLBACK_POPULAR: List[PopularDestination] = [
    {
        "destination": "Umrah",
        "query": "Umrah",
        "href": "/destinations?country=saudi-arabia",
        "flag": "🇸🇦",
    },
    {
        "destination": "Turkey",
        "query": "Turkey",
        "href": "/destinations?country=turkey",
        "flag": "🇹🇷",
    },
    {
        "destination": "Europe",
        "query": "Europe",
        "href": "/destinations?region=Europe",
        "flag": "🇪🇺",
    },
]

# Map normalized search keys → canonical display + routing metadata.
_CANONICAL: Dict[str, PopularDestination] = {
    "umrah": FALLBACK_POPULAR[0],
    "hajj": FALLBACK_POPULAR[0],
    "saudi arabia": {
        "destination": "Saudi Arabia",
        "query": "Saudi Arabia",
        "href": "/destinations?country=saudi-arabia",
        "flag": "🇸🇦",
    },
    "turkey": FALLBACK_POPULAR[1],
    "europe": FALLBACK_POPULAR[2],
    "spain": {
        "destination": "Spain",
        "query": "Spain",
        "href": "/destinations?country=spain",
        "flag": "🇪🇸",
    },
    "france": {
        "destination": "France",
        "query": "France",
        "href": "/destinations?country=france",
        "flag": "🇫🇷",
    },
    "colombia": {
        "destination": "Colombia",
        "query": "Colombia",
        "href": "/destinations?country=colombia",
        "flag": "🇨🇴",
    },
    "italy": {
        "destination": "Italy",
        "query": "Italy",
        "href": "/destinations?country=italy",
        "flag": "🇮🇹",
    },
    "latin america": {
        "destination": "Latin America",
        "query": "Latin America",
        "href": "/destinations?region=Americas",
        "flag": "🌎",
    },
    "latam": {
        "destination": "Latin America",
        "query": "LATAM",
        "href": "/destinations?region=Americas",
        "flag": "🌎",
    },
    "asia": {
        "destination": "Asia",
        "query": "Asia",
        "href": "/destinations?region=Asia",
        "flag": "🌏",
    },
}

_lock = threading.Lock()
_counts: Dict[str, int] = {}


def _normalize(destination: str) -> str:
    return destination.strip().lower()


def _resolve_meta(normalized: str, raw: str) -> PopularDestination:
    if normalized in _CANONICAL:
        return _CANONICAL[normalized]
    label = raw.strip() or normalized.title()
    slug = normalized.replace(" ", "-")
    return {
        "destination": label,
        "query": label,
        "href": f"/destinations?q={slug}",
        "flag": "🌍",
    }


def record_search(destination: str) -> PopularDestination:
    """Increment the counter for a destination search and return canonical meta."""
    raw = destination.strip()
    if not raw:
        raise ValueError("destination must not be empty")

    normalized = _normalize(raw)
    meta = _resolve_meta(normalized, raw)

    with _lock:
        _counts[normalized] = _counts.get(normalized, 0) + 1

    return meta


def get_trending(limit: int = 3) -> List[TrendingDestination]:
    """Return the top-N destinations by search count."""
    with _lock:
        ranked = sorted(_counts.items(), key=lambda item: item[1], reverse=True)

    trending: List[TrendingDestination] = []
    for normalized, count in ranked[:limit]:
        meta = _resolve_meta(normalized, normalized)
        trending.append({**meta, "count": count})

    return trending


def get_fallback() -> List[PopularDestination]:
    return list(FALLBACK_POPULAR)
