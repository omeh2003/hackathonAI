"""Contract tests: verify MCP tool outputs match Pydantic schemas."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from polymarket_mcp.config.settings import Settings
from polymarket_mcp.core.bot_detector import BotDetector
from polymarket_mcp.core.pnl_calculator import PnlCalculator
from polymarket_mcp.core.strategy_analyzer import StrategyAnalyzer
from polymarket_mcp.adapters.polymarket_client import PolymarketClient
from polymarket_mcp.schemas.traders import (
    BatchReportItem,
    StrategyAnalysisResult,
    TopTraderResult,
)
from polymarket_mcp.services.trader_service import TraderService


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock(spec=PolymarketClient)
    client.resolve_profile_id = AsyncMock(return_value="0xtest_wallet")
    client.get_leaderboard = AsyncMock(
        return_value=[
            {"rank": "1", "proxyWallet": "0xwallet1", "pnl": 50000.0, "userName": "t1"},
            {"rank": "2", "proxyWallet": "0xwallet2", "pnl": 30000.0, "userName": "t2"},
        ]
    )
    client.get_trades = AsyncMock(return_value=[])
    client.get_activity = AsyncMock(return_value=[])
    client.get_positions = AsyncMock(return_value=[])
    client.get_profile = AsyncMock(return_value={"createdAt": "2023-01-01T00:00:00Z"})
    return client


@pytest.fixture
def service(mock_client: AsyncMock, settings: Settings) -> TraderService:
    return TraderService(
        client=mock_client,
        bot_detector=BotDetector(threshold=settings.bot_detection_threshold),
        strategy_analyzer=StrategyAnalyzer(),
        pnl_calculator=PnlCalculator(),
        settings=settings,
    )


class TestFindTopTradersContract:
    async def test_output_matches_schema(self, service: TraderService) -> None:
        results = await service.find_top_traders(limit=2, timeframe="all_time")
        assert len(results) == 2
        for r in results:
            validated = TopTraderResult.model_validate(r.model_dump())
            assert isinstance(validated.profile_id, str)
            assert isinstance(validated.pnl, float)
            assert isinstance(validated.is_bot, bool)

    async def test_sorted_by_pnl_descending(self, service: TraderService) -> None:
        results = await service.find_top_traders(limit=2, timeframe="all_time")
        pnls = [r.pnl for r in results]
        assert pnls == sorted(pnls, reverse=True)


class TestAnalyzeTraderContract:
    async def test_output_matches_schema(self, service: TraderService) -> None:
        result = await service.analyze_trader("0xtest_wallet")
        validated = StrategyAnalysisResult.model_validate(result.model_dump())
        assert len(validated.strategy_description) <= 500
        assert validated.risk_level in ("Low", "Medium", "High")
        assert 1 <= validated.success_score <= 10
        assert isinstance(validated.is_bot, bool)
        assert isinstance(validated.risk_justification, str)


class TestBatchReportContract:
    async def test_output_matches_schema(self, service: TraderService) -> None:
        items, latency = await service.generate_batch_report(["0xwallet1"])
        assert len(items) == 1
        for item in items:
            validated = BatchReportItem.model_validate(item.model_dump())
            assert validated.risk_level in ("Low", "Medium", "High")
            assert 1 <= validated.success_score <= 10
            assert isinstance(validated.is_bot, bool)
        assert latency > 0

    async def test_handles_multiple_profiles(self, service: TraderService) -> None:
        items, _ = await service.generate_batch_report(["0xwallet1", "0xwallet2"])
        assert len(items) == 2
