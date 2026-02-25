"""Orchestrates finding and analyzing traders by composing adapters and core logic."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import structlog

from polymarket_mcp.adapters.polymarket_client import PolymarketClient
from polymarket_mcp.config.settings import Settings
from polymarket_mcp.core.bot_detector import BotDetector
from polymarket_mcp.core.pnl_calculator import PnlCalculator
from polymarket_mcp.core.strategy_analyzer import StrategyAnalyzer
from polymarket_mcp.schemas.traders import (
    BatchReportItem,
    StrategyAnalysisResult,
    TopTraderResult,
)

logger = structlog.get_logger(__name__)

TIMEFRAME_MAP = {
    "7d": "WEEK",
    "30d": "MONTH",
    "all_time": "ALL",
}


class TraderService:
    """High-level service composing API calls with analysis logic."""

    def __init__(
        self,
        client: PolymarketClient,
        bot_detector: BotDetector,
        strategy_analyzer: StrategyAnalyzer,
        pnl_calculator: PnlCalculator,
        settings: Settings,
    ) -> None:
        self._client = client
        self._bot_detector = bot_detector
        self._strategy_analyzer = strategy_analyzer
        self._pnl_calc = pnl_calculator
        self._settings = settings

    async def find_top_traders(
        self, limit: int, timeframe: str
    ) -> list[TopTraderResult]:
        start = time.monotonic()
        time_period = TIMEFRAME_MAP.get(timeframe, "ALL")

        leaderboard = await self._client.get_leaderboard(
            time_period=time_period, limit=limit
        )

        semaphore = asyncio.Semaphore(self._settings.max_concurrency)

        async def process_trader(entry: dict[str, Any]) -> TopTraderResult:
            async with semaphore:
                wallet = entry["proxyWallet"]
                pnl = float(entry.get("pnl", 0))
                try:
                    trades = await self._client.get_trades(wallet, limit=200)
                    activity = await self._client.get_activity(wallet, limit=200)
                    profile = await self._client.get_profile(wallet)
                    bot_score = self._bot_detector.detect(
                        trades=trades,
                        activity=activity,
                        account_created_at=profile.get("createdAt"),
                    )
                    return TopTraderResult(
                        profile_id=wallet, pnl=pnl, is_bot=bot_score.is_bot
                    )
                except Exception:
                    logger.exception("error_analyzing_trader", wallet=wallet)
                    return TopTraderResult(
                        profile_id=wallet, pnl=pnl, is_bot=False
                    )

        tasks = [process_trader(entry) for entry in leaderboard]
        results = list(await asyncio.gather(*tasks))
        results.sort(key=lambda r: r.pnl, reverse=True)

        latency_ms = (time.monotonic() - start) * 1000
        logger.info(
            "find_top_traders_complete",
            count=len(results),
            latency_ms=round(latency_ms, 1),
        )
        return results

    async def analyze_trader(self, profile_id: str) -> StrategyAnalysisResult:
        start = time.monotonic()
        wallet = await self._client.resolve_profile_id(profile_id)

        positions, trades, activity, profile = await asyncio.gather(
            self._client.get_positions(wallet),
            self._client.get_trades(wallet),
            self._client.get_activity(wallet),
            self._client.get_profile(wallet),
        )

        bot_score = self._bot_detector.detect(
            trades=trades,
            activity=activity,
            account_created_at=profile.get("createdAt"),
        )

        classification = self._strategy_analyzer.classify(
            positions=positions, trades=trades, activity=activity
        )

        risk = self._strategy_analyzer.assess_risk(positions, classification)

        pnl = self._pnl_calc.total_pnl(positions)

        success_score = self._strategy_analyzer.calculate_success_score(
            classification, is_bot=bot_score.is_bot, pnl=pnl
        )

        description = self._strategy_analyzer.generate_description(
            classification, positions, trades, pnl
        )

        latency_ms = (time.monotonic() - start) * 1000
        logger.info(
            "analyze_trader_complete",
            wallet=wallet,
            strategy=classification.strategy_type,
            latency_ms=round(latency_ms, 1),
        )

        return StrategyAnalysisResult(
            strategy_description=description,
            risk_level=risk.level,
            risk_justification=risk.justification,
            success_score=success_score,
            is_bot=bot_score.is_bot,
        )

    async def generate_batch_report(
        self, profile_ids: list[str]
    ) -> tuple[list[BatchReportItem], float]:
        start = time.monotonic()
        semaphore = asyncio.Semaphore(self._settings.max_concurrency)

        async def process_one(pid: str) -> BatchReportItem:
            async with semaphore:
                wallet = await self._client.resolve_profile_id(pid)
                analysis = await self.analyze_trader(pid)
                # Get PnL from leaderboard (more accurate than positions sum)
                pnl = await self._get_leaderboard_pnl(wallet)
                return BatchReportItem(
                    profile_id=pid,
                    pnl=pnl,
                    risk_level=analysis.risk_level,
                    success_score=analysis.success_score,
                    is_bot=analysis.is_bot,
                )

        tasks = [process_one(pid) for pid in profile_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        items: list[BatchReportItem] = []
        for r in results:
            if isinstance(r, Exception):
                logger.exception("batch_item_error", error=str(r))
            else:
                items.append(r)

        latency_ms = (time.monotonic() - start) * 1000
        logger.info(
            "batch_report_complete",
            count=len(items),
            latency_ms=round(latency_ms, 1),
        )
        return items, latency_ms

    async def _get_leaderboard_pnl(self, wallet: str) -> float:
        """Get PnL from leaderboard API for accurate realized PnL."""
        try:
            data = await self._client.get_leaderboard(
                time_period="ALL", limit=1,
            )
            # Search specific wallet in cached leaderboard
            leaderboard = await self._client.get_leaderboard(time_period="ALL", limit=50)
            for entry in leaderboard:
                if entry.get("proxyWallet", "").lower() == wallet.lower():
                    return float(entry.get("pnl", 0))
        except Exception:
            logger.warning("leaderboard_pnl_fallback", wallet=wallet)
        # Fallback to positions-based PnL
        positions = await self._client.get_positions(wallet)
        return self._pnl_calc.total_pnl(positions)
