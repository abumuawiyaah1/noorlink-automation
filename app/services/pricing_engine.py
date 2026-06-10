"""
Database-driven hybrid pricing for mobile_data_plans.

All coefficients and margin floors come from pricing_rules — no hardcoded
multipliers or buffers in application code.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Literal, Optional, Tuple

PricingStrategy = Literal["MANUAL", "AUTOMATED"]
MarginStatus = Literal["manual", "automated", "floor_applied"]
PlanCategory = Literal["fixed", "unlimited", "flexible"]
DisplayBadge = Literal["best_choice", "flexible"]

_MONEY = Decimal("0.01")


def _to_decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _money(value: Decimal) -> float:
    return float(value.quantize(_MONEY, rounding=ROUND_HALF_UP))


def normalize_strategy(value: Any) -> PricingStrategy:
    raw = str(value or "MANUAL").strip().upper()
    return "AUTOMATED" if raw == "AUTOMATED" else "MANUAL"


def normalize_plan_category(
    row: Dict[str, Any],
    *,
    is_rechargeable: bool,
) -> PlanCategory:
    explicit = str(row.get("plan_category") or "").strip().upper()
    if explicit == "UNLIMITED":
        return "unlimited"
    if explicit == "FLEXIBLE" or is_rechargeable:
        return "flexible"
    if explicit == "FIXED":
        return "fixed"

    if is_rechargeable:
        return "flexible"
    if row.get("data_gb") is None and row.get("data_total_gb") is None:
        name = str(row.get("name") or "").lower()
        if "unlimited" in name:
            return "unlimited"
        if "pay-as-you-go" in name or "pay as you go" in name:
            return "flexible"
    return "fixed"


def resolve_display_badge(
    *,
    plan_category: PlanCategory,
    is_featured: bool,
) -> Optional[DisplayBadge]:
    if plan_category in ("flexible", "unlimited"):
        return "flexible"
    if is_featured and plan_category == "fixed":
        return "best_choice"
    return None


def normalize_scope_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower().replace("_", "-")
    return text or None


def select_pricing_rule_hierarchy(
    rules: list[Dict[str, Any]],
    *,
    country_id: str,
    region_id: Optional[str],
) -> Dict[str, Any]:
    """
    Resolve pricing rule by precedence:
    1. COUNTRY + target_id == country_id
    2. REGION + target_id == region_id
    3. GLOBAL
    """
    active = [rule for rule in rules if rule.get("is_active", True) is not False]
    country_key = normalize_scope_id(country_id)
    region_key = normalize_scope_id(region_id)

    for rule in active:
        scope = str(rule.get("scope") or "GLOBAL").strip().upper()
        if scope != "COUNTRY":
            continue
        target = normalize_scope_id(rule.get("target_id"))
        if target and country_key and target == country_key:
            return rule

    if region_key:
        for rule in active:
            scope = str(rule.get("scope") or "GLOBAL").strip().upper()
            if scope != "REGION":
                continue
            target = normalize_scope_id(rule.get("target_id"))
            if target and target == region_key:
                return rule

    for rule in active:
        scope = str(rule.get("scope") or "GLOBAL").strip().upper()
        if scope == "GLOBAL":
            return rule

    raise ValueError("No active GLOBAL pricing rule configured")


def has_global_pricing_rule(rules: list[Dict[str, Any]]) -> bool:
    return any(
        str(rule.get("scope") or "GLOBAL").strip().upper() == "GLOBAL"
        and rule.get("is_active", True) is not False
        for rule in rules
    )


def apply_price_suffix(calculated_price: float, suffix_rule: Any) -> float:
    """
    Psychological retail suffix from pricing_rules.price_suffix_rule.
    Applied after margin floor on AUTOMATED prices.
    """
    rule = str(suffix_rule or "STANDARD").strip().upper()
    dollars = int(calculated_price)

    if rule == "ROUND_TO_77":
        return float(dollars) + 0.77
    if rule == "ROUND_TO_95":
        return float(dollars) + 0.95
    return round(calculated_price, 2)


def format_price_parts(price: float) -> Dict[str, str]:
    """Split a retail price for frontend superscript cents styling."""
    dollars = int(price)
    cents = int(round((price - dollars) * 100))
    if cents == 100:
        dollars += 1
        cents = 0
    return {"dollars": str(dollars), "cents": str(cents)}


def resolve_plan_price(
    row: Dict[str, Any],
    rule: Dict[str, Any],
) -> Tuple[float, PricingStrategy, MarginStatus, Dict[str, str]]:
    """
    Hybrid pricing:
    - MANUAL → override_price
    - AUTOMATED → (wholesale_cost * multiplier) + fixed_buffer
      → margin floor → psychological price_suffix_rule
    """
    strategy = normalize_strategy(row.get("pricing_strategy"))

    if strategy == "MANUAL":
        override = row.get("override_price")
        if override is not None:
            price = _money(_to_decimal(override))
            return price, strategy, "manual", format_price_parts(price)
        legacy = row.get("price")
        if legacy is not None:
            price = _money(_to_decimal(legacy))
            return price, strategy, "manual", format_price_parts(price)
        legacy_cents = row.get("price_cents")
        if legacy_cents is not None:
            price = _money(_to_decimal(legacy_cents) / Decimal("100"))
            return price, strategy, "manual", format_price_parts(price)
        return 0.0, strategy, "manual", format_price_parts(0.0)

    wholesale = _to_decimal(row.get("wholesale_cost"))
    multiplier = _to_decimal(rule.get("multiplier"))
    fixed_buffer = _to_decimal(rule.get("fixed_buffer"))
    min_margin = _to_decimal(rule.get("min_margin_amount"))

    calculated = (wholesale * multiplier) + fixed_buffer
    floor_price = wholesale + min_margin
    pre_suffix = calculated if calculated >= floor_price else floor_price
    margin_status: MarginStatus = (
        "floor_applied" if pre_suffix == floor_price and calculated < floor_price
        else "automated"
    )

    final_price = apply_price_suffix(
        _money(pre_suffix),
        rule.get("price_suffix_rule"),
    )
    return final_price, strategy, margin_status, format_price_parts(final_price)
