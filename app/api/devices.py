from typing import Dict, List, Optional, Tuple, TypedDict


class DeviceModel(TypedDict):
    id: str
    name: str


class DeviceBrand(TypedDict):
    id: str
    name: str
    models: List[DeviceModel]


# Industry-standard eSIM-capable devices (2024–2026 reference sets).
COMPATIBLE_DEVICES_BY_BRAND: Dict[str, DeviceBrand] = {
    "apple": {
        "id": "apple",
        "name": "Apple",
        "models": [
            {"id": "iphone-xr", "name": "iPhone XR"},
            {"id": "iphone-xs", "name": "iPhone XS"},
            {"id": "iphone-xs-max", "name": "iPhone XS Max"},
            {"id": "iphone-11", "name": "iPhone 11"},
            {"id": "iphone-11-pro", "name": "iPhone 11 Pro"},
            {"id": "iphone-11-pro-max", "name": "iPhone 11 Pro Max"},
            {"id": "iphone-12", "name": "iPhone 12"},
            {"id": "iphone-12-mini", "name": "iPhone 12 mini"},
            {"id": "iphone-12-pro", "name": "iPhone 12 Pro"},
            {"id": "iphone-12-pro-max", "name": "iPhone 12 Pro Max"},
            {"id": "iphone-13", "name": "iPhone 13"},
            {"id": "iphone-13-mini", "name": "iPhone 13 mini"},
            {"id": "iphone-13-pro", "name": "iPhone 13 Pro"},
            {"id": "iphone-13-pro-max", "name": "iPhone 13 Pro Max"},
            {"id": "iphone-14", "name": "iPhone 14"},
            {"id": "iphone-14-plus", "name": "iPhone 14 Plus"},
            {"id": "iphone-14-pro", "name": "iPhone 14 Pro"},
            {"id": "iphone-14-pro-max", "name": "iPhone 14 Pro Max"},
            {"id": "iphone-15", "name": "iPhone 15"},
            {"id": "iphone-15-plus", "name": "iPhone 15 Plus"},
            {"id": "iphone-15-pro", "name": "iPhone 15 Pro"},
            {"id": "iphone-15-pro-max", "name": "iPhone 15 Pro Max"},
            {"id": "iphone-16", "name": "iPhone 16"},
            {"id": "iphone-16-plus", "name": "iPhone 16 Plus"},
            {"id": "iphone-16-pro", "name": "iPhone 16 Pro"},
            {"id": "iphone-16-pro-max", "name": "iPhone 16 Pro Max"},
            {"id": "iphone-17", "name": "iPhone 17"},
            {"id": "iphone-17-pro", "name": "iPhone 17 Pro"},
            {"id": "iphone-17-pro-max", "name": "iPhone 17 Pro Max"},
            {"id": "iphone-air", "name": "iPhone Air"},
            {"id": "iphone-se-2", "name": "iPhone SE (2nd gen)"},
            {"id": "iphone-se-3", "name": "iPhone SE (3rd gen)"},
        ],
    },
    "samsung": {
        "id": "samsung",
        "name": "Samsung",
        "models": [
            {"id": "galaxy-s20", "name": "Galaxy S20"},
            {"id": "galaxy-s20-plus", "name": "Galaxy S20+"},
            {"id": "galaxy-s20-ultra", "name": "Galaxy S20 Ultra"},
            {"id": "galaxy-s21", "name": "Galaxy S21"},
            {"id": "galaxy-s21-plus", "name": "Galaxy S21+"},
            {"id": "galaxy-s21-ultra", "name": "Galaxy S21 Ultra"},
            {"id": "galaxy-s22", "name": "Galaxy S22"},
            {"id": "galaxy-s22-plus", "name": "Galaxy S22+"},
            {"id": "galaxy-s22-ultra", "name": "Galaxy S22 Ultra"},
            {"id": "galaxy-s23", "name": "Galaxy S23"},
            {"id": "galaxy-s23-plus", "name": "Galaxy S23+"},
            {"id": "galaxy-s23-ultra", "name": "Galaxy S23 Ultra"},
            {"id": "galaxy-s24", "name": "Galaxy S24"},
            {"id": "galaxy-s24-plus", "name": "Galaxy S24+"},
            {"id": "galaxy-s24-ultra", "name": "Galaxy S24 Ultra"},
            {"id": "galaxy-z-flip-3", "name": "Galaxy Z Flip3"},
            {"id": "galaxy-z-flip-4", "name": "Galaxy Z Flip4"},
            {"id": "galaxy-z-flip-5", "name": "Galaxy Z Flip5"},
            {"id": "galaxy-z-fold-3", "name": "Galaxy Z Fold3"},
            {"id": "galaxy-z-fold-4", "name": "Galaxy Z Fold4"},
            {"id": "galaxy-z-fold-5", "name": "Galaxy Z Fold5"},
            {"id": "galaxy-note-20", "name": "Galaxy Note 20"},
            {"id": "galaxy-note-20-ultra", "name": "Galaxy Note 20 Ultra"},
        ],
    },
    "google": {
        "id": "google",
        "name": "Google",
        "models": [
            {"id": "pixel-3", "name": "Pixel 3"},
            {"id": "pixel-3-xl", "name": "Pixel 3 XL"},
            {"id": "pixel-3a", "name": "Pixel 3a"},
            {"id": "pixel-4", "name": "Pixel 4"},
            {"id": "pixel-4-xl", "name": "Pixel 4 XL"},
            {"id": "pixel-4a", "name": "Pixel 4a"},
            {"id": "pixel-5", "name": "Pixel 5"},
            {"id": "pixel-5a", "name": "Pixel 5a"},
            {"id": "pixel-6", "name": "Pixel 6"},
            {"id": "pixel-6-pro", "name": "Pixel 6 Pro"},
            {"id": "pixel-6a", "name": "Pixel 6a"},
            {"id": "pixel-7", "name": "Pixel 7"},
            {"id": "pixel-7-pro", "name": "Pixel 7 Pro"},
            {"id": "pixel-7a", "name": "Pixel 7a"},
            {"id": "pixel-8", "name": "Pixel 8"},
            {"id": "pixel-8-pro", "name": "Pixel 8 Pro"},
            {"id": "pixel-8a", "name": "Pixel 8a"},
            {"id": "pixel-9", "name": "Pixel 9"},
            {"id": "pixel-9-pro", "name": "Pixel 9 Pro"},
        ],
    },
    "motorola": {
        "id": "motorola",
        "name": "Motorola",
        "models": [
            {"id": "razr-2019", "name": "Razr (2019)"},
            {"id": "razr-5g", "name": "Razr 5G"},
            {"id": "razr-40", "name": "Razr 40"},
            {"id": "razr-40-ultra", "name": "Razr 40 Ultra"},
            {"id": "edge-2022", "name": "Edge (2022)"},
            {"id": "edge-plus-2022", "name": "Edge+ (2022)"},
            {"id": "edge-40", "name": "Edge 40"},
            {"id": "edge-40-pro", "name": "Edge 40 Pro"},
            {"id": "edge-40-neo", "name": "Edge 40 Neo"},
            {"id": "g52j-5g", "name": "Moto G52j 5G"},
            {"id": "g53-5g", "name": "Moto G53 5G"},
            {"id": "g54-5g", "name": "Moto G54 5G"},
        ],
    },
    "xiaomi": {
        "id": "xiaomi",
        "name": "Xiaomi",
        "models": [
            {"id": "12t-pro", "name": "12T Pro"},
            {"id": "13", "name": "13"},
            {"id": "13-pro", "name": "13 Pro"},
            {"id": "13t", "name": "13T"},
            {"id": "13t-pro", "name": "13T Pro"},
            {"id": "14", "name": "14"},
            {"id": "14-pro", "name": "14 Pro"},
            {"id": "14-ultra", "name": "14 Ultra"},
            {"id": "redmi-note-13-pro-plus", "name": "Redmi Note 13 Pro+"},
        ],
    },
}


def get_compatible_catalog() -> List[DeviceBrand]:
    """Return brands sorted alphabetically with their eSIM-capable models."""
    return sorted(
        COMPATIBLE_DEVICES_BY_BRAND.values(),
        key=lambda brand: brand["name"],
    )


def _flatten_search_keys() -> List[str]:
    keys: List[str] = []
    for brand in COMPATIBLE_DEVICES_BY_BRAND.values():
        keys.append(brand["name"].lower())
        for model in brand["models"]:
            keys.append(model["name"].lower())
    return keys


COMPATIBLE_DEVICES = _flatten_search_keys()


def check_device(device_name: str) -> Tuple[bool, Optional[str]]:
    normalized = device_name.strip().lower()
    if len(normalized) < 3:
        return False, None
    for model in COMPATIBLE_DEVICES:
        if model in normalized:
            return True, model
    return False, None
