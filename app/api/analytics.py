"""
Analytics routes for hero search telemetry and trending destinations.
"""

from fastapi import APIRouter, HTTPException

from app.services.analytics_store import (
    FALLBACK_POPULAR,
    get_fallback,
    get_trending,
    record_search,
)

from .schemas import (
    PopularAnalyticsResponse,
    PopularDestinationItem,
    SearchLogRequest,
    SearchLogResponse,
    TrendingDestinationItem,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.post("/search-log", response_model=SearchLogResponse)
async def log_search(body: SearchLogRequest):
    """Record a hero search selection or query from the Next.js storefront."""
    try:
        meta = record_search(body.destination)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return SearchLogResponse(
        success=True,
        destination=meta["destination"],
        message="Search logged.",
    )


@router.get("/popular", response_model=PopularAnalyticsResponse)
async def popular_destinations():
    """
    Return top trending destinations from in-memory metrics.

    Always includes a fallback block with Umrah, Turkey, and Europe so the
    frontend can render high-intent pills when live data is sparse.
    """
    trending = get_trending(limit=3)
    fallback = get_fallback()

    return PopularAnalyticsResponse(
        success=True,
        trending=[
            TrendingDestinationItem(
                destination=item["destination"],
                query=item["query"],
                href=item["href"],
                flag=item["flag"],
                count=item["count"],
            )
            for item in trending
        ],
        fallback=[
            PopularDestinationItem(
                destination=item["destination"],
                query=item["query"],
                href=item["href"],
                flag=item["flag"],
            )
            for item in fallback
        ],
        fallback_labels=[item["destination"] for item in FALLBACK_POPULAR],
    )
