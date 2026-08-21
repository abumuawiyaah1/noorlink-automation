"""
Citrus Mobile Reseller API client (v2).

Base: https://citrusmobile.com/api/v2/reseller
Auth: Authorization: Bearer rsk_...
Docs: https://citrusmobile.com/llms-full.txt
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://citrusmobile.com/api/v2/reseller"


class CitrusError(Exception):
    """Base Citrus client error."""

    def __init__(self, message: str, *, status_code: Optional[int] = None, code: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class CitrusAuthError(CitrusError):
    """Invalid or missing API key (401)."""


class CitrusNotFoundError(CitrusError):
    """Resource not found (404)."""


class CitrusInsufficientBalanceError(CitrusError):
    """Reseller wallet too low (402)."""


class CitrusClient:
    """Async httpx client for the Citrus Mobile reseller API."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = (api_key if api_key is not None else settings.citrus_api_key).strip()
        self.base_url = (
            base_url if base_url is not None else settings.citrus_api_base_url
        ).rstrip("/")
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

        if not self.api_key:
            raise CitrusAuthError("CITRUS_API_KEY is not configured")

    async def __aenter__(self) -> "CitrusClient":
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._default_headers(),
                timeout=self._timeout,
            )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    def _default_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
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
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Optional[Mapping[str, Any]] = None,
        headers: Optional[MutableMapping[str, str]] = None,
    ) -> Any:
        client = await self._ensure_client()
        try:
            response = await client.request(
                method,
                path,
                params=params,
                json=json,
                headers=headers,
            )
        except httpx.RequestError as exc:
            logger.error("Citrus network error on %s %s: %s", method, path, exc)
            raise CitrusError(f"Unable to reach Citrus: {exc}") from exc

        if response.status_code in (401, 403):
            raise CitrusAuthError(
                "Citrus rejected the API key",
                status_code=response.status_code,
            )

        if response.status_code == 404:
            raise CitrusNotFoundError(
                f"Citrus resource not found: {path}",
                status_code=404,
            )

        if response.status_code == 402:
            detail = response.text[:400]
            raise CitrusInsufficientBalanceError(
                f"Insufficient Citrus balance: {detail}",
                status_code=402,
                code="INSUFFICIENT_BALANCE",
            )

        if response.status_code >= 400:
            detail = response.text[:400]
            logger.error(
                "Citrus API error %s on %s %s: %s",
                response.status_code,
                method,
                path,
                detail,
            )
            raise CitrusError(
                f"Citrus API error ({response.status_code}): {detail}",
                status_code=response.status_code,
            )

        if response.status_code == 204 or not response.content:
            return {}

        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    async def get_account(self) -> Dict[str, Any]:
        """GET /account"""
        payload = await self._request("GET", "/account")
        return payload if isinstance(payload, dict) else {"data": payload}

    async def get_wallet_balance(self) -> Dict[str, Any]:
        """GET /wallet/balance"""
        payload = await self._request("GET", "/wallet/balance")
        return payload if isinstance(payload, dict) else {"data": payload}

    async def list_esims(
        self,
        *,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """GET /esim/list"""
        params: Dict[str, Any] = {
            "limit": max(1, min(int(limit), 200)),
            "offset": max(0, int(offset)),
        }
        if status:
            params["status"] = status
        payload = await self._request("GET", "/esim/list", params=params)
        return payload if isinstance(payload, dict) else {"esims": payload}

    async def get_esim(self, iccid: str) -> Dict[str, Any]:
        """GET /esim/{iccid}"""
        iccid = (iccid or "").strip()
        if not iccid:
            raise ValueError("iccid is required")
        payload = await self._request("GET", f"/esim/{iccid}")
        return payload if isinstance(payload, dict) else {"data": payload}

    async def provision_esim(
        self,
        *,
        end_user_reference: Optional[str] = None,
        label: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        POST /esim/provision

        Charges ~$1.75 from the reseller balance. Returns LPA + QR data URL.
        """
        body: Dict[str, Any] = {}
        if end_user_reference:
            body["end_user_reference"] = end_user_reference
        if label:
            body["label"] = label
        if group_id:
            body["group_id"] = group_id
        payload = await self._request("POST", "/esim/provision", json=body)
        return payload if isinstance(payload, dict) else {"data": payload}

    async def fund_esim(self, iccid: str, amount_usd: float) -> Dict[str, Any]:
        """POST /esim/{iccid}/fund — moves USD onto the SIM wallet."""
        iccid = (iccid or "").strip()
        if not iccid:
            raise ValueError("iccid is required")
        if amount_usd <= 0:
            raise ValueError("amount_usd must be > 0")
        payload = await self._request(
            "POST",
            f"/esim/{iccid}/fund",
            json={"amount": float(amount_usd)},
        )
        return payload if isinstance(payload, dict) else {"data": payload}

    async def disable_esim(self, iccid: str) -> Dict[str, Any]:
        """POST /esim/{iccid}/disable"""
        iccid = (iccid or "").strip()
        if not iccid:
            raise ValueError("iccid is required")
        payload = await self._request("POST", f"/esim/{iccid}/disable")
        return payload if isinstance(payload, dict) else {"data": payload}

    async def enable_esim(self, iccid: str) -> Dict[str, Any]:
        """POST /esim/{iccid}/enable"""
        iccid = (iccid or "").strip()
        if not iccid:
            raise ValueError("iccid is required")
        payload = await self._request("POST", f"/esim/{iccid}/enable")
        return payload if isinstance(payload, dict) else {"data": payload}

    async def list_webhooks(self) -> Dict[str, Any]:
        """GET /webhooks"""
        payload = await self._request("GET", "/webhooks")
        return payload if isinstance(payload, dict) else {"webhooks": payload}

    async def create_webhook(
        self,
        *,
        url: str,
        events: Sequence[str],
    ) -> Dict[str, Any]:
        """
        POST /webhooks

        Response includes `signing_secret` once — store it as CITRUS_WEBHOOK_SECRET.
        """
        payload = await self._request(
            "POST",
            "/webhooks",
            json={"url": url, "events": list(events)},
        )
        return payload if isinstance(payload, dict) else {"data": payload}

    async def test_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """POST /webhooks/{id}/test"""
        webhook_id = (webhook_id or "").strip()
        if not webhook_id:
            raise ValueError("webhook_id is required")
        payload = await self._request("POST", f"/webhooks/{webhook_id}/test")
        return payload if isinstance(payload, dict) else {"data": payload}
