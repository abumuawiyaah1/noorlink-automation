"""
Device compatibility catalog API for the storefront compatibility modal.
"""

from fastapi import APIRouter

from .devices import get_compatible_catalog
from .schemas import (
    CompatibleDevicesResponse,
    DeviceBrandItem,
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
