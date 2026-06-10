"""
Browsable country plans API backed by Supabase "Mobile Data Plans" table.
"""

from fastapi import APIRouter, HTTPException, Query

from . import supabase_repository as db
from .schemas import EsimPlanItem, PlanCategoryGroups, PlansByCountryResponse

router = APIRouter(prefix="/api/v1/plans", tags=["plans"])


@router.get("", response_model=PlansByCountryResponse)
async def list_plans_by_country(
    country_id: str = Query(..., min_length=1, max_length=120),
):
    """Return mobile_data_plans rows for a country_id slug or UUID."""
    try:
        payload = db.get_plans_by_country(country_id)
    except db.SupabaseRepositoryError as exc:
        raise HTTPException(
            status_code=503,
            detail="Plans catalog temporarily unavailable. Please try again.",
        ) from exc

    plan_items = [EsimPlanItem(**row) for row in payload.get("plans", [])]
    groups = payload.get("plan_groups") or {}

    return PlansByCountryResponse(
        success=True,
        country_id=payload["country_id"],
        country_name=payload.get("country_name"),
        flag=payload.get("flag"),
        plans=plan_items,
        plan_groups=PlanCategoryGroups(
            fixed=[EsimPlanItem(**row) for row in groups.get("fixed", [])],
            unlimited=[EsimPlanItem(**row) for row in groups.get("unlimited", [])],
            flexible=[EsimPlanItem(**row) for row in groups.get("flexible", [])],
        ),
    )
