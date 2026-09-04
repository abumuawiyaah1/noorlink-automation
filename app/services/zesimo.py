"""
Zesimo Reseller API client.

Auth: Authorization: Bearer {api_key}
Base: https://zesimo.com/api/v1
Docs: https://zesimo.com/portal/docs (OpenAPI: https://zesimo.com/openapi.yaml)

Orders are atomic + idempotent via Idempotency-Key (use order_number).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, MutableMapping, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://zesimo.com/api/v1"


class ZesimoError(Exception):
    """Base Zesimo client error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        payload: Any = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class ZesimoAuthError(ZesimoError):
    """Invalid or missing API token (401)."""


class ZesimoInsufficientBalanceError(ZesimoError):
    """Wallet balance too low (402)."""


class ZesimoConflictError(ZesimoError):
    """Idempotency-Key reused with different payload (409)."""


class ZesimoClient:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = (api_key if api_key is not None else settings.zesimo_api_key).strip()
        self.base_url = (
            base_url if base_url is not None else settings.zesimo_api_base_url
        ).rstrip("/")
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> "ZesimoClient":
        await self._ensure_client()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    def _default_headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ZesimoAuthError("ZESIMO_API_KEY is empty")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "NoorLink/1.0 (+https://noorlink.co)",
        }

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=self._default_headers(),
                timeout=self._timeout,
                trust_env=False,
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
        path: str,
        *,
        json: Optional[Mapping[str, Any]] = None,
        headers: Optional[MutableMapping[str, str]] = None,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        client = await self._ensure_client()
        url = f"{self.base_url}{path}"
        req_headers = self._default_headers()
        if headers:
            req_headers.update(headers)
        try:
            response = await client.request(
                method,
                url,
                json=json,
                headers=req_headers,
                params=params,
            )
        except httpx.RequestError as exc:
            logger.error("Zesimo network error on %s %s: %s", method, url, exc)
            raise ZesimoError(f"Unable to reach Zesimo: {exc}") from exc

        payload: Any = None
        if response.content:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text[:400]

        if response.status_code in (401, 403):
            detail = ""
            if isinstance(payload, dict):
                detail = str(payload.get("message") or "")
            message = f"Zesimo rejected credentials ({response.status_code})"
            if detail:
                message = f"{message}: {detail}"
            raise ZesimoAuthError(message, status_code=response.status_code, payload=payload)

        if response.status_code == 402:
            detail = ""
            if isinstance(payload, dict):
                detail = str(payload.get("message") or "Insufficient wallet balance.")
            raise ZesimoInsufficientBalanceError(
                detail or "Insufficient wallet balance.",
                status_code=402,
                payload=payload,
            )

        if response.status_code == 409:
            detail = ""
            if isinstance(payload, dict):
                detail = str(payload.get("message") or "")
            raise ZesimoConflictError(
                detail or "Zesimo Idempotency-Key conflict",
                status_code=409,
                payload=payload,
            )

        if response.status_code >= 400:
            detail = ""
            if isinstance(payload, dict):
                detail = str(payload.get("message") or payload)
            elif payload:
                detail = str(payload)
            raise ZesimoError(
                f"Zesimo HTTP {response.status_code}: {detail or response.text[:400]}",
                status_code=response.status_code,
                payload=payload,
            )

        return payload if payload is not None else {}

    async def place_order(
        self,
        *,
        package_id: int,
        quantity: int = 1,
        idempotency_key: str,
        days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        POST /orders — returns {"order": OrderWithEsims}.
        HTTP 200 = idempotent replay; 201 = new order.
        """
        body: Dict[str, Any] = {
            "package_id": int(package_id),
            "quantity": int(quantity),
        }
        if days is not None:
            body["days"] = int(days)

        payload = await self._request(
            "POST",
            "/orders",
            json=body,
            headers={"Idempotency-Key": idempotency_key[:128]},
        )
        if not isinstance(payload, dict):
            raise ZesimoError("Zesimo order response was not an object", payload=payload)
        return payload

    async def get_order(self, order_id: int | str) -> Dict[str, Any]:
        payload = await self._request("GET", f"/orders/{order_id}")
        if not isinstance(payload, dict):
            raise ZesimoError("Zesimo get_order response was not an object", payload=payload)
        return payload

    async def get_wallet(self) -> Dict[str, Any]:
        payload = await self._request("GET", "/wallet")
        if not isinstance(payload, dict):
            raise ZesimoError("Zesimo wallet response was not an object", payload=payload)
        return payload


def first_esim_from_order_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Extract the first eSIM credential object from place/get order response."""
    order = payload.get("order")
    if not isinstance(order, Mapping):
        order = payload
    esims = order.get("esims") if isinstance(order, Mapping) else None
    if isinstance(esims, list) and esims:
        first = esims[0]
        if isinstance(first, dict):
            return first
    raise ZesimoError("Zesimo order response missing esims[0]", payload=payload)
