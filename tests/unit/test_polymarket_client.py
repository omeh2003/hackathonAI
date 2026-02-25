"""Tests for PolymarketClient using respx mocks."""

from __future__ import annotations

import pytest
import httpx
import respx

from polymarket_mcp.adapters.polymarket_client import PolymarketClient
from polymarket_mcp.config.settings import Settings


@pytest.fixture
async def client(settings: Settings) -> PolymarketClient:
    c = PolymarketClient(settings)
    yield c
    await c.close()


class TestGetLeaderboard:
    @respx.mock
    async def test_returns_data(self, client: PolymarketClient) -> None:
        mock_data = [{"rank": "1", "proxyWallet": "0xabc", "pnl": 1000.0}]
        respx.get("https://data-api.polymarket.com/v1/leaderboard").mock(
            return_value=httpx.Response(200, json=mock_data)
        )
        result = await client.get_leaderboard(time_period="ALL", limit=10)
        assert result == mock_data

    @respx.mock
    async def test_retries_on_timeout(self, client: PolymarketClient) -> None:
        route = respx.get("https://data-api.polymarket.com/v1/leaderboard").mock(
            side_effect=[
                httpx.TimeoutException("timeout"),
                httpx.Response(200, json=[]),
            ]
        )
        result = await client.get_leaderboard()
        assert route.call_count == 2
        assert result == []

    @respx.mock
    async def test_retries_on_5xx(self, client: PolymarketClient) -> None:
        route = respx.get("https://data-api.polymarket.com/v1/leaderboard").mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(200, json=[{"ok": True}]),
            ]
        )
        result = await client.get_leaderboard()
        assert route.call_count == 2


class TestGetTrades:
    @respx.mock
    async def test_returns_trades(self, client: PolymarketClient) -> None:
        mock_data = [{"side": "BUY", "size": 100}]
        respx.get("https://data-api.polymarket.com/trades").mock(
            return_value=httpx.Response(200, json=mock_data)
        )
        result = await client.get_trades("0xwallet")
        assert result == mock_data


class TestGetPositions:
    @respx.mock
    async def test_returns_positions(self, client: PolymarketClient) -> None:
        mock_data = [{"conditionId": "c1", "cashPnl": 500}]
        respx.get("https://data-api.polymarket.com/positions").mock(
            return_value=httpx.Response(200, json=mock_data)
        )
        result = await client.get_positions("0xwallet")
        assert result == mock_data


class TestGetActivity:
    @respx.mock
    async def test_returns_activity(self, client: PolymarketClient) -> None:
        mock_data = [{"type": "TRADE", "usdcSize": 65.0}]
        respx.get("https://data-api.polymarket.com/activity").mock(
            return_value=httpx.Response(200, json=mock_data)
        )
        result = await client.get_activity("0xwallet")
        assert result == mock_data


class TestGetProfile:
    @respx.mock
    async def test_returns_profile(self, client: PolymarketClient) -> None:
        mock_data = {"name": "testuser", "proxyWallet": "0xabc"}
        respx.get("https://gamma-api.polymarket.com/public-profile").mock(
            return_value=httpx.Response(200, json=mock_data)
        )
        result = await client.get_profile("0xabc")
        assert result == mock_data


class TestResolveProfileId:
    @respx.mock
    async def test_wallet_passthrough(self, client: PolymarketClient) -> None:
        result = await client.resolve_profile_id("0xabc123")
        assert result == "0xabc123"

    @respx.mock
    async def test_username_resolution(self, client: PolymarketClient) -> None:
        respx.get("https://gamma-api.polymarket.com/public-search").mock(
            return_value=httpx.Response(200, json={
                "profiles": [{"name": "testuser", "proxyWallet": "0xresolved"}]
            })
        )
        result = await client.resolve_profile_id("@testuser")
        assert result == "0xresolved"

    @respx.mock
    async def test_username_not_found_raises(self, client: PolymarketClient) -> None:
        respx.get("https://gamma-api.polymarket.com/public-search").mock(
            return_value=httpx.Response(200, json={"profiles": []})
        )
        with pytest.raises(ValueError, match="No profile found"):
            await client.resolve_profile_id("@nonexistent")

    @respx.mock
    async def test_username_exact_match_preferred(self, client: PolymarketClient) -> None:
        respx.get("https://gamma-api.polymarket.com/public-search").mock(
            return_value=httpx.Response(200, json={
                "profiles": [
                    {"name": "other", "proxyWallet": "0xother"},
                    {"name": "target", "proxyWallet": "0xtarget"},
                ]
            })
        )
        result = await client.resolve_profile_id("@target")
        assert result == "0xtarget"


class TestCaching:
    @respx.mock
    async def test_cache_hit_skips_request(self, settings: Settings) -> None:
        settings.cache_ttl = 300
        client = PolymarketClient(settings)
        route = respx.get("https://data-api.polymarket.com/v1/leaderboard").mock(
            return_value=httpx.Response(200, json=[{"cached": True}])
        )
        result1 = await client.get_leaderboard()
        result2 = await client.get_leaderboard()
        assert result1 == result2
        assert route.call_count == 1
        await client.close()
