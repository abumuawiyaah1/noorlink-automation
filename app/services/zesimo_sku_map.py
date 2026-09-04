"""
Locked Zesimo fulfillment map (24 SKUs).

provider = "zesimo"
provider_sku = package_id (portal /packages/{id}/order)
Prefer cheap-ladder IDs only.

Everything NOT listed here keeps existing rules:
  - Saudi fixed 3/5/10/20/50 → esimaccess
  - Saudi unlimited 14d → esimaccess (no Zesimo twin in this cut)
  - Caribbean regional → telna
  - PAYG → citrus
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# phase, catalog_key, zesimo product name, package_id, wholesale_cents, retail_cents
ZESIMO_SKU_MAP: List[Dict[str, Any]] = [
    # Phase 1 — MENA (use live SA unlimited catalog keys)
    {
        "phase": 1,
        "catalog_key": "sa-unlimited-3gb-7d",
        "country_code": "SA",
        "country_slug": "saudi-arabia",
        "data_gb": 3.0,
        "validity_days": 7,
        "package_id": "10903",
        "provider_slug": "zesimo-sa-unlimited-7d",
        "wholesale_cents": 2142,
        "retail_cents": 3499,
        "product_name": "Saudi Arabia Unlimited 7 Days",
    },
    {
        "phase": 1,
        "catalog_key": "sa-unlimited-3gb-10d",
        "country_code": "SA",
        "country_slug": "saudi-arabia",
        "data_gb": 3.0,
        "validity_days": 10,
        "package_id": "10905",
        "provider_slug": "zesimo-sa-unlimited-10d",
        "wholesale_cents": 2786,
        "retail_cents": 4299,
        "product_name": "Saudi Arabia Unlimited 10 Days",
    },
    {
        "phase": 1,
        "catalog_key": "me-5gb-15",
        "country_code": None,
        "country_slug": "regional-middle-east",
        "data_gb": 5.0,
        "validity_days": 15,
        "package_id": "1085",
        "provider_slug": "zesimo-me-5gb-15d",
        "wholesale_cents": 991,
        "retail_cents": 1999,
        "product_name": "MIDDLE EAST 5GB 15 Days",
    },
    {
        "phase": 1,
        "catalog_key": "me-10gb-30",
        "country_code": None,
        "country_slug": "regional-middle-east",
        "data_gb": 10.0,
        "validity_days": 30,
        "package_id": "1086",
        "provider_slug": "zesimo-me-10gb-30d",
        "wholesale_cents": 1784,
        "retail_cents": 3299,
        "product_name": "MIDDLE EAST 10GB 30 Days",
    },
    # Phase 2
    {
        "phase": 2,
        "catalog_key": "eu-5gb-30",
        "country_slug": "regional-europe",
        "data_gb": 5.0,
        "validity_days": 30,
        "package_id": "11707",
        "provider_slug": "zesimo-eu-5gb-30d",
        "wholesale_cents": 602,
        "retail_cents": 1799,
        "product_name": "Europe 5GB 30 Days",
    },
    {
        "phase": 2,
        "catalog_key": "eu-10gb-30",
        "country_slug": "regional-europe",
        "data_gb": 10.0,
        "validity_days": 30,
        "package_id": "583",
        "provider_slug": "zesimo-eu-10gb-30d",
        "wholesale_cents": 798,
        "retail_cents": 2299,
        "product_name": "Europe 10GB 30 Days",
    },
    {
        "phase": 2,
        "catalog_key": "la-5gb-30",
        "country_slug": "regional-south-america",
        "data_gb": 5.0,
        "validity_days": 30,
        "package_id": "12121",
        "provider_slug": "zesimo-la-5gb-30d",
        "wholesale_cents": 1050,
        "retail_cents": 2299,
        "product_name": "Latin America 5GB 30 Days",
    },
    {
        "phase": 2,
        "catalog_key": "la-10gb-30",
        "country_slug": "regional-south-america",
        "data_gb": 10.0,
        "validity_days": 30,
        "package_id": "12122",
        "provider_slug": "zesimo-la-10gb-30d",
        "wholesale_cents": 1764,
        "retail_cents": 3499,
        "product_name": "Latin America 10GB 30 Days",
    },
    {
        "phase": 2,
        "catalog_key": "mx-5gb-30",
        "country_code": "MX",
        "country_slug": "mexico",
        "data_gb": 5.0,
        "validity_days": 30,
        "package_id": "8186",
        "provider_slug": "zesimo-mx-5gb-30d",
        "wholesale_cents": 812,
        "retail_cents": 1799,
        "product_name": "Mexico 5GB 30 Days",
    },
    {
        "phase": 2,
        "catalog_key": "mx-10gb-30",
        "country_code": "MX",
        "country_slug": "mexico",
        "data_gb": 10.0,
        "validity_days": 30,
        "package_id": "8188",
        "provider_slug": "zesimo-mx-10gb-30d",
        "wholesale_cents": 1400,
        "retail_cents": 2799,
        "product_name": "Mexico 10GB 30 Days",
    },
    {
        "phase": 2,
        "catalog_key": "us-5gb-30",
        "country_code": "US",
        "country_slug": "united-states",
        "data_gb": 5.0,
        "validity_days": 30,
        "package_id": "3363",
        "provider_slug": "zesimo-us-5gb-30d",
        "wholesale_cents": 463,
        "retail_cents": 1499,
        "product_name": "United States 5GB 30 Days",
    },
    {
        "phase": 2,
        "catalog_key": "us-10gb-30",
        "country_code": "US",
        "country_slug": "united-states",
        "data_gb": 10.0,
        "validity_days": 30,
        "package_id": "7673",
        "provider_slug": "zesimo-us-10gb-30d",
        "wholesale_cents": 809,
        "retail_cents": 1999,
        "product_name": "United States 10GB 30 Days",
    },
    {
        "phase": 2,
        "catalog_key": "na-10gb-30",
        "country_slug": "regional-north-america",
        "data_gb": 10.0,
        "validity_days": 30,
        "package_id": "587",
        "provider_slug": "zesimo-na-10gb-30d",
        "wholesale_cents": 1398,
        "retail_cents": 2799,
        "product_name": "North America 10GB 30 Days",
    },
    {
        "phase": 2,
        "catalog_key": "as-5gb-30",
        "country_slug": "regional-asia-pacific",
        "data_gb": 5.0,
        "validity_days": 30,
        "package_id": "11733",
        "provider_slug": "zesimo-as-5gb-30d",
        "wholesale_cents": 434,
        "retail_cents": 1799,
        "product_name": "Asia 5GB 30 Days",
    },
    {
        "phase": 2,
        "catalog_key": "as-10gb-30",
        "country_slug": "regional-asia-pacific",
        "data_gb": 10.0,
        "validity_days": 30,
        "package_id": "11736",
        "provider_slug": "zesimo-as-10gb-30d",
        "wholesale_cents": 714,
        "retail_cents": 2999,
        "product_name": "Asia 10GB 30 Days",
    },
    # Phase 3
    {
        "phase": 3,
        "catalog_key": "eu-20gb-30",
        "country_slug": "regional-europe",
        "data_gb": 20.0,
        "validity_days": 30,
        "package_id": "586",
        "provider_slug": "zesimo-eu-20gb-30d",
        "wholesale_cents": 1409,
        "retail_cents": 3999,
        "product_name": "Europe 20GB 30 Days",
    },
    {
        "phase": 3,
        "catalog_key": "as-20gb-30",
        "country_slug": "regional-asia-pacific",
        "data_gb": 20.0,
        "validity_days": 30,
        "package_id": "11738",
        "provider_slug": "zesimo-as-20gb-30d",
        "wholesale_cents": 1092,
        "retail_cents": 3999,
        "product_name": "Asia 20GB 30 Days",
    },
    {
        "phase": 3,
        "catalog_key": "us-20gb-30",
        "country_code": "US",
        "country_slug": "united-states",
        "data_gb": 20.0,
        "validity_days": 30,
        "package_id": "7677",
        "provider_slug": "zesimo-us-20gb-30d",
        "wholesale_cents": 1450,
        "retail_cents": 2999,
        "product_name": "United States 20GB 30 Days",
    },
    {
        "phase": 3,
        "catalog_key": "la-20gb-30",
        "country_slug": "regional-south-america",
        "data_gb": 20.0,
        "validity_days": 30,
        "package_id": "12123",
        "provider_slug": "zesimo-la-20gb-30d",
        "wholesale_cents": 2814,
        "retail_cents": 4999,
        "product_name": "Latin America 20GB 30 Days",
    },
    {
        "phase": 3,
        "catalog_key": "mx-20gb-30",
        "country_code": "MX",
        "country_slug": "mexico",
        "data_gb": 20.0,
        "validity_days": 30,
        "package_id": "8190",
        "provider_slug": "zesimo-mx-20gb-30d",
        "wholesale_cents": 2226,
        "retail_cents": 3999,
        "product_name": "Mexico 20GB 30 Days",
    },
    {
        "phase": 3,
        "catalog_key": "eu-1gb-7",
        "country_slug": "regional-europe",
        "data_gb": 1.0,
        "validity_days": 7,
        "package_id": "11701",
        "provider_slug": "zesimo-eu-1gb-7d",
        "wholesale_cents": 252,
        "retail_cents": 999,
        "product_name": "Europe 1GB 7 Days",
    },
    {
        "phase": 3,
        "catalog_key": "na-1gb-7",
        "country_slug": "regional-north-america",
        "data_gb": 1.0,
        "validity_days": 7,
        "package_id": "580",
        "provider_slug": "zesimo-na-1gb-7d",
        "wholesale_cents": 182,
        "retail_cents": 799,
        "product_name": "North America 1GB 7 Days",
    },
    {
        "phase": 3,
        "catalog_key": "gulf-5gb-30",
        "country_slug": "regional-gulf",
        "data_gb": 5.0,
        "validity_days": 30,
        "package_id": "2544",
        "provider_slug": "zesimo-gulf-5gb-30d",
        "wholesale_cents": 1512,
        "retail_cents": 2799,
        "product_name": "Gulf Region 5GB 30 Days",
    },
    {
        "phase": 3,
        "catalog_key": "la-3gb-30",
        "country_slug": "regional-south-america",
        "data_gb": 3.0,
        "validity_days": 30,
        "package_id": "12094",
        "provider_slug": "zesimo-la-3gb-30d",
        "wholesale_cents": 700,
        "retail_cents": 1699,
        "product_name": "Latin America 3GB 30 Days",
    },
]


def by_phase(phase: int) -> List[Dict[str, Any]]:
    return [row for row in ZESIMO_SKU_MAP if row["phase"] == phase]


def get_sku(catalog_key: str) -> Optional[Dict[str, Any]]:
    for row in ZESIMO_SKU_MAP:
        if row["catalog_key"] == catalog_key:
            return row
    return None


def fulfillment_rows() -> List[Dict[str, Any]]:
    """Rows ready for plan_fulfillment_map upsert."""
    rows: List[Dict[str, Any]] = []
    for sku in ZESIMO_SKU_MAP:
        package_id = sku.get("package_id")
        if not package_id:
            raise ValueError(f"Missing package_id for {sku['catalog_key']}")
        rows.append(
            {
                "catalog_key": sku["catalog_key"],
                "country_code": sku.get("country_code"),
                "country_slug": sku.get("country_slug"),
                "data_gb": sku.get("data_gb"),
                "validity_days": sku.get("validity_days"),
                "provider": "zesimo",
                "provider_sku": str(package_id),
                "provider_slug": sku["provider_slug"],
                "wholesale_cents": sku["wholesale_cents"],
                "period_num": None,
                "notes": f"Zesimo phase {sku['phase']}: {sku['product_name']}",
                "is_active": True,
                "admin_approved": True,
            }
        )
    return rows


assert len(ZESIMO_SKU_MAP) == 24
assert len(by_phase(1)) == 4
assert len(by_phase(2)) == 11
assert len(by_phase(3)) == 9
assert all(row.get("package_id") for row in ZESIMO_SKU_MAP)
