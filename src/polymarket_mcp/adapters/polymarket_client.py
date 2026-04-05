"""Single Polymarket API client with retry, timeout, and caching."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from polymarket_mcp.config.settings import Settings

logger = structlog.get_logger(__name__)


class PolymarketClient:
    """Unified async client for data-api and gamma-api."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._data_client = httpx.AsyncClient(
            base_url=settings.polymarket_data_api_base,
            timeout=httpx.Timeout(settings.request_timeout),
        )
        self._gamma_client = httpx.AsyncClient(
            base_url=settings.polymarket_gamma_api_base,
            timeout=httpx.Timeout(settings.request_timeout),
        )
        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_ttl = settings.cache_ttl
        self._semaphore = asyncio.Semaphore(settings.max_concurrency * 10)

    def _cache_key(self, base: str, path: str, params: dict[str, Any]) -> str:
        sorted_params = sorted(params.items())
        return f"{base}{path}|{sorted_params}"

    def _get_cached(self, key: str) -> Any | None:
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.monotonic() < expiry:
                return value
            del self._cache[key]
        return None

    def _set_cached(self, key: str, value: Any) -> None:
        if self._cache_ttl > 0:
            self._cache[key] = (value, time.monotonic() + self._cache_ttl)

    async def _request(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: dict[str, Any],
    ) -> Any:
        """Execute HTTP GET with retry, rate limiting, caching."""
        cache_key = self._cache_key(str(client.base_url), path, params)
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.debug("cache_hit", path=path)
            return cached

        data = await self._request_with_retry(client, path, params)
        self._set_cached(cache_key, data)
        return data

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    )
    async def _request_with_retry(
        self,
        client: httpx.AsyncClient,
        path: str,
        params: dict[str, Any],
    ) -> Any:
        async with self._semaphore:
            start = time.monotonic()
            logger.info("api_request", path=path, params=params)
            response = await client.get(path, params=params)
            response.raise_for_status()
            latency_ms = (time.monotonic() - start) * 1000
            logger.info(
                "api_response", path=path, status=response.status_code,
                latency_ms=round(latency_ms, 1),
            )
            return response.json()

    # --- Public API methods ---

    async def get_leaderboard(
        self,
        time_period: str = "ALL",
        order_by: str = "PNL",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return await self._request(
            self._data_client,
            "/v1/leaderboard",
            {"timePeriod": time_period, "orderBy": order_by, "limit": limit},
        )

    async def get_positions(
        self, wallet: str, limit: int = 500, sort_by: str = "CASHPNL",
    ) -> list[dict[str, Any]]:
        return await self._request(
            self._data_client,
            "/positions",
            {"user": wallet, "limit": limit, "sortBy": sort_by},
        )

    async def get_trades(
        self, wallet: str, limit: int = 500,
    ) -> list[dict[str, Any]]:
        return await self._request(
            self._data_client,
            "/trades",
            {"user": wallet, "limit": limit},
        )

    async def get_activity(
        self, wallet: str, limit: int = 500, activity_type: str = "TRADE",
    ) -> list[dict[str, Any]]:
        return await self._request(
            self._data_client,
            "/activity",
            {"user": wallet, "limit": limit, "type": activity_type},
        )

    async def get_profile(self, wallet: str) -> dict[str, Any]:
        return await self._request(
            self._gamma_client,
            "/public-profile",
            {"address": wallet},
        )

    async def search_profiles(self, query: str) -> dict[str, Any]:
        return await self._request(
            self._gamma_client,
            "/public-search",
            {"q": query, "search_profiles": "true"},
        )

    async def resolve_profile_id(self, profile_id: str) -> str:
        """Resolve @username to wallet address, or return wallet as-is."""
        if profile_id.startswith("0x"):
            return profile_id
        username = profile_id.lstrip("@")
        result = await self.search_profiles(username)
        profiles = result.get("profiles", [])
        for p in profiles:
            if p.get("name", "").lower() == username.lower():
                return p["proxyWallet"]
        raise ValueError(f"No profile found for username: {username}")

    async def close(self) -> None:
        await self._data_client.aclose()
        await self._gamma_client.aclose()
