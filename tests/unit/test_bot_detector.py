"""Unit tests for BotDetector with synthetic trade data."""

from __future__ import annotations

import random

import pytest

from polymarket_mcp.core.bot_detector import BotDetector


@pytest.fixture
def detector() -> BotDetector:
    return BotDetector(threshold=0.6)


class TestEmptyData:
    def test_no_trades_returns_not_bot(self, detector: BotDetector) -> None:
        result = detector.detect(trades=[], activity=[])
        assert result.is_bot is False
        assert result.composite_score == 0.0


class TestTradeFrequency:
    def test_high_frequency_scores_high(self, detector: BotDetector) -> None:
        base_ts = 1700000000
        trades = [{"timestamp": base_ts + i * 600, "size": 10.0} for i in range(100)]
        result = detector.detect(trades=trades, activity=[])
        assert result.trade_frequency_score > 0.8

    def test_low_frequency_scores_low(self, detector: BotDetector) -> None:
        base_ts = 1700000000
        trades = [{"timestamp": base_ts + i * 86400 * 6, "size": 10.0} for i in range(5)]
        result = detector.detect(trades=trades, activity=[])
        assert result.trade_frequency_score < 0.2


class TestTimeRegularity:
    def test_perfectly_regular_is_bot_like(self, detector: BotDetector) -> None:
        base_ts = 1700000000
        trades = [{"timestamp": base_ts + i * 60, "size": 10.0} for i in range(100)]
        result = detector.detect(trades=trades, activity=[])
        assert result.time_regularity_score > 0.9

    def test_random_intervals_is_human_like(self, detector: BotDetector) -> None:
        random.seed(42)
        base_ts = 1700000000
        timestamps = sorted([base_ts + random.randint(0, 86400 * 30) for _ in range(50)])
        trades = [{"timestamp": ts, "size": 10.0} for ts in timestamps]
        result = detector.detect(trades=trades, activity=[])
        assert result.time_regularity_score < 0.5


class TestRoundTheClock:
    def test_24h_coverage_scores_high(self, detector: BotDetector) -> None:
        base_ts = 1700000000
        trades = [{"timestamp": base_ts + h * 3600, "size": 10.0} for h in range(24)]
        result = detector.detect(trades=trades, activity=[])
        assert result.round_the_clock_score > 0.9

    def test_8h_window_scores_low(self, detector: BotDetector) -> None:
        base_ts = 1700000000 - (1700000000 % 86400)
        trades = [
            {"timestamp": base_ts + 9 * 3600 + i * 1800, "size": 10.0}
            for i in range(16)
        ]
        result = detector.detect(trades=trades, activity=[])
        assert result.round_the_clock_score < 0.4


class TestSizeConsistency:
    def test_identical_sizes_scores_high(self, detector: BotDetector) -> None:
        trades = [{"timestamp": 1700000000 + i * 60, "size": 100.0} for i in range(50)]
        result = detector.detect(trades=trades, activity=[])
        assert result.size_consistency_score > 0.9

    def test_varied_sizes_scores_low(self, detector: BotDetector) -> None:
        random.seed(42)
        trades = [
            {"timestamp": 1700000000 + i * 60, "size": random.uniform(1, 10000)}
            for i in range(50)
        ]
        result = detector.detect(trades=trades, activity=[])
        assert result.size_consistency_score < 0.5


class TestComposite:
    def test_obvious_bot_detected(self, detector: BotDetector) -> None:
        base_ts = 1700000000
        trades = [
            {"timestamp": base_ts + i * 120, "size": 100.0}
            for i in range(720)  # 24 hours, every 2 min
        ]
        result = detector.detect(trades=trades, activity=[])
        assert result.is_bot is True
        assert result.composite_score >= 0.6

    def test_obvious_human_not_detected(self, detector: BotDetector) -> None:
        random.seed(42)
        base_ts = 1700000000
        trades = [
            {"timestamp": base_ts + random.randint(0, 86400 * 30), "size": random.uniform(50, 500)}
            for _ in range(10)
        ]
        result = detector.detect(trades=trades, activity=[])
        assert result.is_bot is False

    def test_activity_data_also_works(self, detector: BotDetector) -> None:
        base_ts = 1700000000
        activity = [
            {"timestamp": base_ts + i * 120, "usdcSize": 100.0}
            for i in range(720)
        ]
        result = detector.detect(trades=[], activity=activity)
        assert result.is_bot is True


class TestEdgeCases:
    def test_single_trade(self, detector: BotDetector) -> None:
        result = detector.detect(trades=[{"timestamp": 1700000000, "size": 100}], activity=[])
        assert result.is_bot is False

    def test_two_trades(self, detector: BotDetector) -> None:
        trades = [
            {"timestamp": 1700000000, "size": 100},
            {"timestamp": 1700000100, "size": 100},
        ]
        result = detector.detect(trades=trades, activity=[])
        assert result.is_bot is False

    def test_missing_fields_handled(self, detector: BotDetector) -> None:
        trades = [{"other_field": "value"}, {"timestamp": None}]
        result = detector.detect(trades=trades, activity=[])
        assert result.is_bot is False
