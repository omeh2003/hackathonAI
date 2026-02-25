"""Tests for StrategyAnalyzer rule-based classification."""

from __future__ import annotations

import pytest

from polymarket_mcp.core.strategy_analyzer import StrategyAnalyzer
from polymarket_mcp.schemas.traders import StrategyClassification


@pytest.fixture
def analyzer() -> StrategyAnalyzer:
    return StrategyAnalyzer()


class TestClassify:
    def test_arbitrage_detected(self, analyzer: StrategyAnalyzer) -> None:
        trades = []
        for i in range(200):
            # Each market gets both BUY and SELL trades
            trades.append({
                "conditionId": f"market_{i % 10}",
                "side": "BUY" if (i // 10) % 2 == 0 else "SELL",
                "price": 0.50 + (i % 3) * 0.01,
                "timestamp": 1700000000 + i * 300,
                "size": 100.0,
            })
        result = analyzer.classify(positions=[], trades=trades, activity=[])
        assert result.strategy_type == "arbitrage"

    def test_event_driven_detected(self, analyzer: StrategyAnalyzer) -> None:
        positions = [
            {"conditionId": "market_1", "currentValue": 9000.0},
            {"conditionId": "market_2", "currentValue": 500.0},
            {"conditionId": "market_3", "currentValue": 500.0},
        ]
        trades = [
            {
                "conditionId": "market_1",
                "side": "BUY",
                "price": 0.7,
                "timestamp": 1700000000 + i * 3600,
                "size": 1000,
            }
            for i in range(20)
        ]
        result = analyzer.classify(positions=positions, trades=trades, activity=[])
        assert result.strategy_type == "event_driven"

    def test_diversified_detected(self, analyzer: StrategyAnalyzer) -> None:
        positions = [
            {"conditionId": f"market_{i}", "currentValue": 100.0} for i in range(15)
        ]
        trades = [
            {
                "conditionId": f"market_{i}",
                "side": "BUY",
                "price": 0.6,
                "timestamp": 1700000000 + i * 86400,
                "size": 500,
            }
            for i in range(15)
        ]
        result = analyzer.classify(positions=positions, trades=trades, activity=[])
        assert result.strategy_type in ("diversified", "trend_following")

    def test_unknown_fallback(self, analyzer: StrategyAnalyzer) -> None:
        result = analyzer.classify(positions=[], trades=[], activity=[])
        assert result.strategy_type == "unknown"

    def test_empty_trades_returns_unknown(self, analyzer: StrategyAnalyzer) -> None:
        positions = [{"conditionId": "m1", "currentValue": 100}]
        result = analyzer.classify(positions=positions, trades=[], activity=[])
        assert result.strategy_type in ("event_driven", "unknown")


class TestRiskAssessment:
    def test_high_concentration_is_high_risk(self, analyzer: StrategyAnalyzer) -> None:
        positions = [
            {"conditionId": "m1", "currentValue": 9500.0},
            {"conditionId": "m2", "currentValue": 500.0},
        ]
        classification = StrategyClassification(
            strategy_type="event_driven",
            confidence=0.8,
            indicators={"concentration": 0.95},
        )
        risk = analyzer.assess_risk(positions, classification)
        assert risk.level == "High"

    def test_diversified_is_low_risk(self, analyzer: StrategyAnalyzer) -> None:
        positions = [{"conditionId": f"m{i}", "currentValue": 100.0} for i in range(20)]
        classification = StrategyClassification(
            strategy_type="diversified",
            confidence=0.6,
            indicators={"concentration": 0.05},
        )
        risk = analyzer.assess_risk(positions, classification)
        assert risk.level == "Low"

    def test_arbitrage_always_high_risk(self, analyzer: StrategyAnalyzer) -> None:
        positions = [{"conditionId": f"m{i}", "currentValue": 100.0} for i in range(20)]
        classification = StrategyClassification(
            strategy_type="arbitrage",
            confidence=0.8,
            indicators={"concentration": 0.1},
        )
        risk = analyzer.assess_risk(positions, classification)
        assert risk.level == "High"


class TestSuccessScore:
    def test_bot_arbitrage_scores_high(self, analyzer: StrategyAnalyzer) -> None:
        classification = StrategyClassification(
            strategy_type="arbitrage",
            confidence=0.8,
            indicators={"trades_per_day": 100},
        )
        score = analyzer.calculate_success_score(classification, is_bot=True, pnl=500000)
        assert score >= 7

    def test_human_diversified_scores_low(self, analyzer: StrategyAnalyzer) -> None:
        classification = StrategyClassification(
            strategy_type="diversified",
            confidence=0.6,
            indicators={"trades_per_day": 3},
        )
        score = analyzer.calculate_success_score(classification, is_bot=False, pnl=5000)
        assert score <= 3

    def test_score_clamped_to_range(self, analyzer: StrategyAnalyzer) -> None:
        classification = StrategyClassification(
            strategy_type="arbitrage",
            confidence=0.9,
            indicators={"trades_per_day": 200},
        )
        score = analyzer.calculate_success_score(classification, is_bot=True, pnl=1000000)
        assert 1 <= score <= 10


class TestDescription:
    def test_description_under_500_chars(self, analyzer: StrategyAnalyzer) -> None:
        classification = StrategyClassification(
            strategy_type="arbitrage",
            confidence=0.8,
            indicators={
                "trades_per_day": 50,
                "unique_markets": 20,
                "avg_margin": 0.02,
                "n_trades": 500,
                "avg_hold_hours": 1,
                "concentration": 0.1,
            },
        )
        desc = analyzer.generate_description(classification, [], [], 10000)
        assert len(desc) <= 500
        assert "arbitrage" in desc.lower()

    def test_each_strategy_generates_description(self, analyzer: StrategyAnalyzer) -> None:
        for stype in [
            "arbitrage", "market_making", "trend_following",
            "event_driven", "diversified", "scalping", "unknown",
        ]:
            classification = StrategyClassification(
                strategy_type=stype,
                confidence=0.5,
                indicators={
                    "trades_per_day": 10,
                    "unique_markets": 5,
                    "avg_margin": 0.03,
                    "n_trades": 100,
                    "avg_hold_hours": 12,
                    "concentration": 0.3,
                },
            )
            desc = analyzer.generate_description(classification, [], [], 1000)
            assert len(desc) > 0
            assert len(desc) <= 500
