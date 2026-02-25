"""Heuristic-based bot detection from trade patterns."""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BotScore:
    """Individual factor scores and final determination."""

    trade_frequency_score: float = 0.0
    time_regularity_score: float = 0.0
    round_the_clock_score: float = 0.0
    size_consistency_score: float = 0.0
    volume_intensity_score: float = 0.0
    composite_score: float = 0.0
    is_bot: bool = False
    factors: dict[str, float] = field(default_factory=dict)


class BotDetector:
    """Classifies a trader as bot or human based on behavioral heuristics.

    Five heuristics scored 0-1 with weighted composite:
    - Trade frequency: >50 trades/day = bot-like
    - Time regularity: low coefficient of variation in inter-trade intervals
    - 24h activity: trades across many hours of the day
    - Size consistency: low variance in trade sizes
    - Volume intensity: high daily volume relative to trade span
    """

    WEIGHTS = {
        "trade_frequency": 0.25,
        "time_regularity": 0.20,
        "round_the_clock": 0.25,
        "size_consistency": 0.15,
        "volume_intensity": 0.15,
    }

    def __init__(self, threshold: float = 0.6) -> None:
        self._threshold = threshold

    def detect(
        self,
        trades: list[dict[str, Any]],
        activity: list[dict[str, Any]],
        account_created_at: str | None = None,
    ) -> BotScore:
        """Run all heuristics and return composite BotScore."""
        if not trades and not activity:
            return BotScore(is_bot=False)

        timestamps = self._extract_timestamps(trades, activity)
        sizes = self._extract_sizes(trades, activity)

        scores = {
            "trade_frequency": self._score_trade_frequency(timestamps),
            "time_regularity": self._score_time_regularity(timestamps),
            "round_the_clock": self._score_round_the_clock(timestamps),
            "size_consistency": self._score_size_consistency(sizes),
            "volume_intensity": self._score_volume_intensity(sizes, timestamps),
        }

        composite = sum(scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS)

        logger.info(
            "bot_detection_complete",
            composite_score=round(composite, 3),
            is_bot=composite >= self._threshold,
            factors=scores,
        )

        return BotScore(
            trade_frequency_score=scores["trade_frequency"],
            time_regularity_score=scores["time_regularity"],
            round_the_clock_score=scores["round_the_clock"],
            size_consistency_score=scores["size_consistency"],
            volume_intensity_score=scores["volume_intensity"],
            composite_score=round(composite, 3),
            is_bot=composite >= self._threshold,
            factors=scores,
        )

    def _extract_timestamps(
        self, trades: list[dict[str, Any]], activity: list[dict[str, Any]]
    ) -> list[int]:
        ts: set[int] = set()
        for t in trades:
            if "timestamp" in t and t["timestamp"] is not None:
                ts.add(int(t["timestamp"]))
        for a in activity:
            if "timestamp" in a and a["timestamp"] is not None:
                ts.add(int(a["timestamp"]))
        return sorted(ts)

    def _extract_sizes(
        self, trades: list[dict[str, Any]], activity: list[dict[str, Any]]
    ) -> list[float]:
        sizes: list[float] = []
        for t in trades:
            if "size" in t and t["size"] is not None:
                sizes.append(float(t["size"]))
        for a in activity:
            if "usdcSize" in a and a["usdcSize"] is not None:
                sizes.append(float(a["usdcSize"]))
        return sizes

    def _score_trade_frequency(self, timestamps: list[int]) -> float:
        """0 at <=5 trades/day, 1.0 at >=50 trades/day."""
        if len(timestamps) < 2:
            return 0.0
        span_days = max((timestamps[-1] - timestamps[0]) / 86400, 1)
        trades_per_day = len(timestamps) / span_days
        return min(max((trades_per_day - 5) / 45, 0.0), 1.0)

    def _score_time_regularity(self, timestamps: list[int]) -> float:
        """Low coefficient of variation in inter-trade intervals = bot-like."""
        if len(timestamps) < 3:
            return 0.0
        intervals = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        mean_interval = statistics.mean(intervals)
        if mean_interval == 0:
            return 1.0
        stdev_interval = statistics.stdev(intervals)
        cv = stdev_interval / mean_interval
        return min(max((1.5 - cv) / 1.2, 0.0), 1.0)

    def _score_round_the_clock(self, timestamps: list[int]) -> float:
        """Trading across >20 unique hours = bot-like."""
        if not timestamps:
            return 0.0
        hours = {(ts % 86400) // 3600 for ts in timestamps}
        hour_coverage = len(hours) / 24
        return min(max((hour_coverage - 0.33) / 0.5, 0.0), 1.0)

    def _score_size_consistency(self, sizes: list[float]) -> float:
        """Very low CV in trade sizes = bot-like."""
        if len(sizes) < 3:
            return 0.0
        mean_size = statistics.mean(sizes)
        if mean_size == 0:
            return 0.0
        stdev_size = statistics.stdev(sizes)
        cv = stdev_size / mean_size
        return min(max((1.0 - cv) / 0.9, 0.0), 1.0)

    def _score_volume_intensity(
        self, sizes: list[float], timestamps: list[int]
    ) -> float:
        """>$10k/day = 1.0, <$100/day = 0.0."""
        if not sizes or len(timestamps) < 2:
            return 0.0
        total_volume = sum(sizes)
        span_days = max((timestamps[-1] - timestamps[0]) / 86400, 1)
        volume_per_day = total_volume / span_days
        return min(max((volume_per_day - 100) / 9900, 0.0), 1.0)
