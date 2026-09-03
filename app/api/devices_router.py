"""
Device compatibility catalog API for the storefront compatibility modal.
"""

from fastapi import APIRouter

from app.services.device_catalog_monitor import record_device_check_miss

from .devices import get_compatible_catalog
from .schemas import (
    CompatibleDevicesResponse,
    DeviceBrandItem,
    DeviceCheckMissRequest,
    DeviceCheckMissResponse,
    DeviceModelItem,
)

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])


@router.get("/compatible", response_model=CompatibleDevicesResponse)
async def list_compatible_devices():
    """Return structured eSIM-capable brands and models for UI dropdowns."""
    brands = get_compatible_catalog()
    return CompatibleDevicesResponse(
        success=True,
        brands=[
            DeviceBrandItem(
                id=brand["id"],
                name=brand["name"],
                models=[
                    DeviceModelItem(id=model["id"], name=model["name"])
                    for model in brand["models"]
                ],
            )
            for brand in brands
        ],
    )


@router.post("/report-miss", response_model=DeviceCheckMissResponse)
async def report_device_check_miss(body: DeviceCheckMissRequest):
    """Log a customer device search we could not match (for weekly ops review)."""
    query = body.query.strip()
    if len(query) < 2:
        return DeviceCheckMissResponse(success=True, recorded=False)
    record_device_check_miss(query, source="site")
    return DeviceCheckMissResponse(success=True, recorded=True)
