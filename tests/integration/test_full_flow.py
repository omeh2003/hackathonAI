"""Integration tests: full flows with respx-mocked Polymarket API."""

from __future__ import annotations

import pytest
import httpx
import respx

from polymarket_mcp.adapters.polymarket_client import PolymarketClient
from polymarket_mcp.config.settings import Settings
from polymarket_mcp.core.bot_detector import BotDetector
from polymarket_mcp.core.pnl_calculator import PnlCalculator
from polymarket_mcp.core.strategy_analyzer import StrategyAnalyzer
from polymarket_mcp.services.trader_service import TraderService


@pytest.fixture
def integration_settings() -> Settings:
    return Settings(
        polymarket_data_api_base="https://data-api.polymarket.com",
        polymarket_gamma_api_base="https://gamma-api.polymarket.com",
        request_timeout=5,
        max_concurrency=2,
        cache_ttl=0,
        bot_detection_threshold=0.6,
    )


def _mock_trader_endpoints() -> None:
    """Set up standard mocks for all trader-related endpoints."""
    respx.get("https://data-api.polymarket.com/v1/leaderboard").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "rank": "1",
                    "proxyWallet": "0xwallet1",
                    "pnl": 50000.0,
                    "userName": "top1",
                    "vol": 100000.0,
                    "profileImage": "",
                    "xUsername": "",
                    "verifiedBadge": False,
                },
            ],
        )
    )
    respx.get("https://data-api.polymarket.com/trades").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://data-api.polymarket.com/activity").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://data-api.polymarket.com/positions").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get("https://gamma-api.polymarket.com/public-profile").mock(
        return_value=httpx.Response(
            200,
            json={
                "createdAt": "2023-01-01T00:00:00Z",
                "proxyWallet": "0xwallet1",
                "name": "top1",
                "pseudonym": "test",
                "bio": "",
                "displayUsernamePublic": True,
                "verifiedBadge": False,
                "users": [],
            },
        )
    )
    respx.get("https://gamma-api.polymarket.com/public-search").mock(
        return_value=httpx.Response(
            200,
            json={"profiles": [{"name": "top1", "proxyWallet": "0xwallet1"}]},
        )
    )


def _build_service(settings: Settings) -> tuple[TraderService, PolymarketClient]:
    client = PolymarketClient(settings)
    service = TraderService(
        client=client,
        bot_detector=BotDetector(threshold=settings.bot_detection_threshold),
        strategy_analyzer=StrategyAnalyzer(),
        pnl_calculator=PnlCalculator(),
        settings=settings,
    )
    return service, client


class TestFindTopTradersFlow:
    @respx.mock
    async def test_end_to_end(self, integration_settings: Settings) -> None:
        _mock_trader_endpoints()
        service, client = _build_service(integration_settings)

        results = await service.find_top_traders(limit=1, timeframe="all_time")
        await client.close()

        assert len(results) == 1
        assert results[0].profile_id == "0xwallet1"
        assert results[0].pnl == 50000.0
        assert results[0].is_bot is False


class TestAnalyzeTraderFlow:
    @respx.mock
    async def test_end_to_end_with_wallet(self, integration_settings: Settings) -> None:
        _mock_trader_endpoints()
        service, client = _build_service(integration_settings)

        result = await service.analyze_trader("0xwallet1")
        await client.close()

        assert result.risk_level in ("Low", "Medium", "High")
        assert 1 <= result.success_score <= 10
        assert len(result.strategy_description) <= 500

    @respx.mock
    async def test_end_to_end_with_username(self, integration_settings: Settings) -> None:
        _mock_trader_endpoints()
        service, client = _build_service(integration_settings)

        result = await service.analyze_trader("@top1")
        await client.close()

        assert result.risk_level in ("Low", "Medium", "High")


class TestBatchReportFlow:
    @respx.mock
    async def test_end_to_end(self, integration_settings: Settings) -> None:
        _mock_trader_endpoints()
        service, client = _build_service(integration_settings)

        items, latency = await service.generate_batch_report(["0xwallet1"])
        await client.close()

        assert len(items) == 1
        assert items[0].profile_id == "0xwallet1"
        assert latency > 0


class TestEdgeCases:
    @respx.mock
    async def test_empty_leaderboard(self, integration_settings: Settings) -> None:
        respx.get("https://data-api.polymarket.com/v1/leaderboard").mock(
            return_value=httpx.Response(200, json=[])
        )
        service, client = _build_service(integration_settings)

        results = await service.find_top_traders(limit=10, timeframe="7d")
        await client.close()

        assert results == []

    @respx.mock
    async def test_api_timeout_retries(self, integration_settings: Settings) -> None:
        route = respx.get("https://data-api.polymarket.com/v1/leaderboard").mock(
            side_effect=[
                httpx.TimeoutException("timeout"),
                httpx.TimeoutException("timeout"),
                httpx.Response(200, json=[]),
            ]
        )
        service, client = _build_service(integration_settings)

        results = await service.find_top_traders(limit=5, timeframe="all_time")
        await client.close()

        assert route.call_count == 3
        assert results == []
