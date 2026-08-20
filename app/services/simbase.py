"""
Simbase API v2 client.

Docs: https://developer.simbase.com/
Auth header: Authorization: Bearer <SIMBASE_API_KEY>
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Mapping, MutableMapping, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class SimbaseError(Exception):
    """Base Simbase client error."""


    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class SimbaseAuthError(SimbaseError):
    """Invalid or missing API key (401/403)."""


class SimbaseNotFoundError(SimbaseError):
    """Resource not found (404)."""


class SimbaseClient:
    """Async httpx client for Simbase v2 endpoints."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = (api_key if api_key is not None else settings.simbase_api_key).strip()
        self.base_url = (
            base_url if base_url is not None else settings.simbase_api_base_url
        ).rstrip("/")
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

        if not self.api_key:
            raise SimbaseAuthError("SIMBASE_API_KEY is not configured")

    async def __aenter__(self) -> "SimbaseClient":
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._default_headers(),
                timeout=self._timeout,
            )
            self._owns_client = True
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    def _default_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
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
        url = path if path.startswith("http") else path
        try:
            response = await client.request(
                method,
                url,
                params=params,
                json=json,
                headers=headers,
            )
        except httpx.RequestError as exc:
            logger.error("Simbase network error on %s %s: %s", method, path, exc)
            raise SimbaseError(f"Unable to reach Simbase: {exc}") from exc

        if response.status_code in (401, 403):
            logger.error(
                "Simbase auth failed (%s) for %s %s",
                response.status_code,
                method,
                path,
            )
            raise SimbaseAuthError(
                "Simbase rejected the API key",
                status_code=response.status_code,
            )

        if response.status_code == 404:
            raise SimbaseNotFoundError(
                f"Simbase resource not found: {path}",
                status_code=404,
            )

        if response.status_code >= 400:
            detail = response.text[:400]
            logger.error(
                "Simbase API error %s on %s %s: %s",
                response.status_code,
                method,
                path,
                detail,
            )
            raise SimbaseError(
                f"Simbase API error ({response.status_code}): {detail}",
                status_code=response.status_code,
            )

        if response.status_code == 204 or not response.content:
            return {}

        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    async def get_account_balance(self) -> Dict[str, Any]:
        """GET /account/balance"""
        payload = await self._request("GET", "/account/balance")
        if not isinstance(payload, dict) or not payload:
            raise SimbaseError("Empty balance response from Simbase")
        return payload

    async def list_simcards(self, limit: int = 50) -> Dict[str, Any]:
        """GET /simcards"""
        safe_limit = max(1, min(int(limit), 200))
        payload = await self._request(
            "GET",
            "/simcards",
            params={"limit": safe_limit},
        )
        return payload if isinstance(payload, dict) else {"simcards": payload}

    async def get_sim_details(self, iccid: str) -> Dict[str, Any]:
        """GET /simcards/{iccid}"""
        iccid = (iccid or "").strip()
        if not iccid:
            raise ValueError("iccid is required")
        payload = await self._request("GET", f"/simcards/{iccid}")
        return payload if isinstance(payload, dict) else {"data": payload}

    async def update_sim_state(self, iccid: str, state: str) -> Dict[str, Any]:
        """
        PATCH /simcards/{iccid}

        Uses Content-Type: application/merge-patch+json to set state
        to "enabled" or "disabled".
        """
        iccid = (iccid or "").strip()
        normalized = (state or "").strip().lower()
        if not iccid:
            raise ValueError("iccid is required")
        if normalized not in {"enabled", "disabled"}:
            raise ValueError('state must be "enabled" or "disabled"')

        payload = await self._request(
            "PATCH",
            f"/simcards/{iccid}",
            json={"state": normalized},
            headers={"Content-Type": "application/merge-patch+json"},
        )
        return payload if isinstance(payload, dict) else {"data": payload}

    async def get_sim_usage(self, iccid: str) -> Dict[str, Any]:
        """GET /usage/simcards/{iccid}"""
        iccid = (iccid or "").strip()
        if not iccid:
            raise ValueError("iccid is required")
        payload = await self._request("GET", f"/usage/simcards/{iccid}")
        return payload if isinstance(payload, dict) else {"data": payload}

# Task / docs alias
SimbaseAPIError = SimbaseError
