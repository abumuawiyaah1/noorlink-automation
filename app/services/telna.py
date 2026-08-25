"""
Telna Connect Flex API client.

Ordering:   https://ppo-api.telna.com/v1/ordering
Diagnostic: https://ppo-api.telna.com/v1/diagnostic
Auth: Authorization: <token>  (raw token — do NOT prefix with "Bearer")
Docs: https://flex-developer.telna.com/llms.txt

Note: Public OpenAPI product schema may omit unit cost. Live responses and the
portal often include cost fields — normalize_product() extracts whatever exists.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_ORDERING_BASE_URL = "https://ppo-api.telna.com/v1/ordering"
DEFAULT_DIAGNOSTIC_BASE_URL = "https://ppo-api.telna.com/v1/diagnostic"


class TelnaError(Exception):
    """Base Telna Connect Flex client error."""

    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class TelnaAuthError(TelnaError):
    """Invalid or missing API token (401/403)."""


class TelnaNotFoundError(TelnaError):
    """Resource not found (404)."""


def _bytes_to_mb(data_bytes: Any) -> Optional[float]:
    try:
        value = float(data_bytes)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return round(value / (1024.0 * 1024.0), 4)


def _seconds_to_days(seconds: Any) -> Optional[float]:
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return round(value / 86400.0, 4)


def _extract_unit_cost_usd(raw: Mapping[str, Any]) -> Optional[float]:
    """Best-effort wholesale USD from portal/API field variants."""
    candidates: List[Any] = [
        raw.get("unit_cost"),
        raw.get("unitCost"),
        raw.get("cost"),
        raw.get("price"),
        raw.get("wholesale_price"),
        raw.get("wholesalePrice"),
    ]
    package = raw.get("package_template")
    if isinstance(package, Mapping):
        candidates.extend(
            [
                package.get("unit_cost"),
                package.get("unitCost"),
                package.get("cost"),
                package.get("price"),
            ]
        )
    for value in candidates:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def normalize_product(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """Flatten a Telna product into a comparison-friendly dict."""
    package = raw.get("package_template")
    if not isinstance(package, Mapping):
        package = {}

    time_allowance = package.get("time_allowance")
    if not isinstance(time_allowance, Mapping):
        time_allowance = {}

    duration_unit = str(time_allowance.get("unit") or "").upper()
    duration_value = time_allowance.get("duration")
    duration_days: Optional[float] = None
    if duration_unit == "SECOND":
        duration_days = _seconds_to_days(duration_value)
    elif duration_unit == "CALENDAR_MONTH":
        try:
            duration_days = float(duration_value) * 30.0
        except (TypeError, ValueError):
            duration_days = None

    countries = package.get("supported_countries")
    if not isinstance(countries, list):
        countries = []

    data_mb = _bytes_to_mb(package.get("data_usage_allowance"))
    unit_cost = _extract_unit_cost_usd(raw)

    return {
        "id": str(raw.get("id") or ""),
        "name": str(raw.get("name") or ""),
        "sim_product": raw.get("sim_product"),
        "status": raw.get("status"),
        "unit_cost_usd": unit_cost,
        "data_mb": data_mb,
        "data_bytes": package.get("data_usage_allowance"),
        "duration_unit": duration_unit or None,
        "duration_value": duration_value,
        "duration_days": duration_days,
        "activation_type": package.get("activation_type"),
        "activation_time_allowance_sec": package.get("activation_time_allowance"),
        "traffic_policy": package.get("traffic_policy"),
        "supported_countries": [str(c) for c in countries],
        "country_count": len(countries),
        "package_template_id": package.get("id"),
        "package_template_name": package.get("name"),
        "raw": dict(raw),
    }


class TelnaClient:
    """Async httpx client for Telna Connect Flex."""

    def __init__(
        self,
        *,
        api_token: Optional[str] = None,
        ordering_base_url: Optional[str] = None,
        diagnostic_base_url: Optional[str] = None,
        account_id: Optional[str] = None,
        timeout: float = 45.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        settings = get_settings()
        self.api_token = (
            api_token if api_token is not None else settings.telna_api_token
        ).strip()
        self.ordering_base_url = (
            ordering_base_url
            if ordering_base_url is not None
            else settings.telna_ordering_base_url
        ).rstrip("/")
        self.diagnostic_base_url = (
            diagnostic_base_url
            if diagnostic_base_url is not None
            else settings.telna_diagnostic_base_url
        ).rstrip("/")
        self.account_id = (
            account_id if account_id is not None else settings.telna_account_id
        ).strip()
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

        if not self.api_token:
            raise TelnaAuthError("TELNA_API_TOKEN is not configured")

    async def __aenter__(self) -> "TelnaClient":
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self._default_headers(),
                timeout=self._timeout,
            )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    def _default_headers(self) -> Dict[str, str]:
        return {
            # Telna Connect Flex expects the raw token, not "Bearer <token>".
            "Authorization": self.api_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Request-ID": str(uuid.uuid4()),
        }

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self._default_headers(),
                timeout=self._timeout,
            )
            self._owns_client = True
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Optional[Mapping[str, Any]] = None,
        headers: Optional[MutableMapping[str, str]] = None,
    ) -> Any:
        client = await self._ensure_client()
        req_headers = self._default_headers()
        if headers:
            req_headers.update(headers)
        try:
            response = await client.request(
                method,
                url,
                params=params,
                json=json,
                headers=req_headers,
            )
        except httpx.RequestError as exc:
            logger.error("Telna network error on %s %s: %s", method, url, exc)
            raise TelnaError(f"Unable to reach Telna: {exc}") from exc

        if response.status_code in (401, 403):
            raise TelnaAuthError(
                f"Telna rejected credentials ({response.status_code})",
                status_code=response.status_code,
            )
        if response.status_code == 404:
            raise TelnaNotFoundError(
                f"Telna resource not found: {url}",
                status_code=404,
            )

        if response.status_code >= 400:
            raise TelnaError(
                f"Telna HTTP {response.status_code}: {response.text[:400]}",
                status_code=response.status_code,
            )

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise TelnaError(
                f"Invalid JSON from Telna ({response.status_code}): "
                f"{response.text[:300]}"
            ) from exc

    async def list_products(
        self,
        *,
        count: int = 100,
        offset: int = 0,
        account: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"count": count, "offset": offset}
        account_id = (account if account is not None else self.account_id).strip()
        if account_id:
            params["account"] = account_id
        return await self._request(
            "GET",
            f"{self.ordering_base_url}/products",
            params=params,
        )

    async def list_all_products(
        self,
        *,
        page_size: int = 100,
        account: Optional[str] = None,
        max_pages: int = 50,
    ) -> List[Dict[str, Any]]:
        """Paginate through the full Flex product catalog."""
        items: List[Dict[str, Any]] = []
        offset = 0
        for _ in range(max_pages):
            payload = await self.list_products(
                count=page_size,
                offset=offset,
                account=account,
            )
            batch = payload.get("products") if isinstance(payload, dict) else None
            if not isinstance(batch, list):
                break
            items.extend([p for p in batch if isinstance(p, dict)])
            total = int(payload.get("total") or 0)
            offset += len(batch)
            if not batch or offset >= total:
                break
        return items

    async def get_product(self, product_id: str) -> Dict[str, Any]:
        pid = product_id.strip()
        if not pid:
            raise TelnaError("product_id is required")
        return await self._request(
            "GET",
            f"{self.ordering_base_url}/products/{pid}",
        )

    async def create_work_order(
        self,
        *,
        product_id: str,
        customer_ref: str,
        account: Optional[str] = None,
        iccid: Optional[str] = None,
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "customer_ref": customer_ref.strip(),
            "product": product_id.strip(),
        }
        account_id = (account if account is not None else self.account_id).strip()
        if account_id:
            body["account"] = account_id
        if iccid and iccid.strip():
            body["iccid"] = iccid.strip()
        return await self._request(
            "POST",
            f"{self.ordering_base_url}/work-orders",
            json=body,
        )

    async def get_work_order(self, work_order_id: str) -> Dict[str, Any]:
        wid = work_order_id.strip()
        if not wid:
            raise TelnaError("work_order_id is required")
        return await self._request(
            "GET",
            f"{self.ordering_base_url}/work-orders/{wid}",
        )

    async def get_euicc_profile(self, iccid: str) -> Dict[str, Any]:
        value = iccid.strip()
        if not value:
            raise TelnaError("iccid is required")
        return await self._request(
            "GET",
            f"{self.diagnostic_base_url}/euicc-profiles/{value}",
        )

    async def catalog_summary(
        self,
        *,
        account: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Normalized catalog for pricing comparison."""
        raw_products = await self.list_all_products(account=account)
        return [normalize_product(p) for p in raw_products]
