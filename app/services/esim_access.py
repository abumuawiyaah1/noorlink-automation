"""
eSIM Access Partner API client.

Base: https://api.esimaccess.com/api/v1/open
Auth: RT-AccessCode + HMAC-SHA256 (access code is also the signing key)
Docs: https://docs.esimaccess.com/
Prices: API integer / 10_000 = USD
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.esimaccess.com/api/v1/open"
PRICE_SCALE = 10_000


class EsimAccessError(Exception):
    """Base eSIM Access client error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        code: Optional[str] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class EsimAccessAuthError(EsimAccessError):
    """Invalid credentials or signature."""


class EsimAccessInsufficientBalanceError(EsimAccessError):
    """Reseller wallet too low (200007)."""


def usd_to_api_price(usd: float) -> int:
    return int(round(float(usd) * PRICE_SCALE))


def api_price_to_usd(api_price: int | float) -> float:
    return float(api_price) / PRICE_SCALE


def build_signed_headers(access_code: str, body: str) -> Dict[str, str]:
    """HMAC headers required on every eSIM Access request."""
    timestamp = str(int(time.time() * 1000))
    request_id = str(uuid.uuid4())
    sign_str = f"{timestamp}{request_id}{access_code}{body}"
    signature = hmac.new(
        access_code.encode("utf-8"),
        sign_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest().lower()
    return {
        "Content-Type": "application/json",
        "RT-AccessCode": access_code,
        "RT-Timestamp": timestamp,
        "RT-RequestID": request_id,
        "RT-Signature": signature,
    }


class EsimAccessClient:
    """Async httpx client for the eSIM Access open API."""

    def __init__(
        self,
        *,
        access_code: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 45.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        settings = get_settings()
        self.access_code = (
            access_code
            if access_code is not None
            else settings.esim_access_access_code
        ).strip()
        self.base_url = (
            base_url if base_url is not None else settings.esim_access_api_base_url
        ).rstrip("/")
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

        if not self.access_code:
            raise EsimAccessAuthError("ESIM_ACCESS_ACCESS_CODE is not configured")

    async def __aenter__(self) -> "EsimAccessClient":
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self._timeout,
            )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
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
        path: str,
        body: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        payload = dict(body or {})
        body_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        headers = build_signed_headers(self.access_code, body_str)
        client = await self._ensure_client()
        try:
            response = await client.post(path, content=body_str, headers=headers)
        except httpx.RequestError as exc:
            logger.error("eSIM Access network error on %s: %s", path, exc)
            raise EsimAccessError(f"Unable to reach eSIM Access: {exc}") from exc

        if response.status_code in (401, 403):
            raise EsimAccessAuthError(
                "eSIM Access rejected credentials",
                status_code=response.status_code,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise EsimAccessError(
                f"Invalid JSON from eSIM Access ({response.status_code}): "
                f"{response.text[:300]}"
            ) from exc

        if response.status_code >= 400:
            raise EsimAccessError(
                f"eSIM Access HTTP {response.status_code}: {response.text[:400]}",
                status_code=response.status_code,
            )

        if isinstance(data, dict) and data.get("success") is False:
            code = str(data.get("errorCode") or "")
            msg = str(data.get("errorMsg") or "Request failed")
            if code == "200007":
                raise EsimAccessInsufficientBalanceError(
                    f"Insufficient eSIM Access balance: {msg}",
                    status_code=response.status_code,
                    code=code,
                )
            if code in {"401001", "000101", "000102", "101003"}:
                raise EsimAccessAuthError(
                    f"eSIM Access auth error ({code}): {msg}",
                    status_code=response.status_code,
                    code=code,
                )
            raise EsimAccessError(
                f"eSIM Access error ({code}): {msg}",
                status_code=response.status_code,
                code=code,
            )

        return data

    async def get_balance(self) -> Dict[str, Any]:
        data = await self._request("/balance/query", {})
        obj = data.get("obj") if isinstance(data, dict) else None
        if not isinstance(obj, dict):
            raise EsimAccessError("balance/query missing obj")
        balance_api = obj.get("balance", 0)
        return {
            "balance_api": balance_api,
            "balance_usd": api_price_to_usd(balance_api or 0),
            "raw": obj,
        }

    async def list_packages(
        self,
        *,
        location_code: str = "",
        package_code: str = "",
        slug: str = "",
        package_type: str = "",
        iccid: str = "",
    ) -> List[Dict[str, Any]]:
        data = await self._request(
            "/package/list",
            {
                "locationCode": location_code,
                "type": package_type,
                "slug": slug,
                "packageCode": package_code,
                "iccid": iccid,
            },
        )
        obj = data.get("obj") if isinstance(data, dict) else None
        if not isinstance(obj, dict):
            return []
        packages = obj.get("packageList") or []
        return packages if isinstance(packages, list) else []

    async def order_esim(
        self,
        *,
        transaction_id: str,
        package_code: str,
        count: int = 1,
        period_num: Optional[int] = None,
        price_api: Optional[int] = None,
        amount_api: Optional[int] = None,
    ) -> Dict[str, Any]:
        package_info: Dict[str, Any] = {
            "packageCode": package_code,
            "count": count,
        }
        if period_num is not None:
            package_info["periodNum"] = int(period_num)
        if price_api is not None:
            package_info["price"] = int(price_api)

        body: Dict[str, Any] = {
            "transactionId": transaction_id,
            "packageInfoList": [package_info],
        }
        if amount_api is not None:
            body["amount"] = int(amount_api)

        data = await self._request("/esim/order", body)
        obj = data.get("obj") if isinstance(data, dict) else None
        if not isinstance(obj, dict) or not obj.get("orderNo"):
            raise EsimAccessError("esim/order response missing orderNo")
        return obj

    async def query_esims(
        self,
        *,
        order_no: str = "",
        iccid: str = "",
        page_num: int = 1,
        page_size: int = 20,
    ) -> List[Dict[str, Any]]:
        data = await self._request(
            "/esim/query",
            {
                "orderNo": order_no,
                "iccid": iccid,
                "pager": {"pageNum": page_num, "pageSize": page_size},
            },
        )
        obj = data.get("obj") if isinstance(data, dict) else None
        if not isinstance(obj, dict):
            return []
        esim_list = obj.get("esimList") or []
        return esim_list if isinstance(esim_list, list) else []

    async def cancel_esim(self, *, esim_tran_no: str) -> Any:
        return await self._request("/esim/cancel", {"esimTranNo": esim_tran_no})

    async def wait_for_profile(
        self,
        *,
        order_no: str,
        attempts: int = 8,
        delay_seconds: float = 1.5,
    ) -> Dict[str, Any]:
        """Poll until ICCID / QR appear for an order."""
        import asyncio

        last: List[Dict[str, Any]] = []
        for attempt in range(attempts):
            last = await self.query_esims(order_no=order_no)
            if last:
                profile = last[0]
                if profile.get("iccid") or profile.get("qrCodeUrl") or profile.get("ac"):
                    return profile
            if attempt + 1 < attempts:
                await asyncio.sleep(delay_seconds)
        if last:
            return last[0]
        raise EsimAccessError(f"No eSIM profile returned for orderNo={order_no}")
