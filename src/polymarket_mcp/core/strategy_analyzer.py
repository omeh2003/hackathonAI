"""Rule-based strategy classification and template description generation."""

from __future__ import annotations

import statistics
from typing import Any

import structlog

from polymarket_mcp.schemas.traders import RiskAssessment, StrategyClassification

logger = structlog.get_logger(__name__)


STRATEGY_TEMPLATES: dict[str, str] = {
    "arbitrage": (
        "Trader employs an arbitrage strategy, trading both sides of markets "
        "to capture price discrepancies. Executes trades at {freq} frequency "
        "with average margin of {avg_margin:.1%}. Operates across {n_markets} markets. "
        "Requires low latency and high capital efficiency."
    ),
    "market_making": (
        "Trader acts as a market maker, providing liquidity on both sides of "
        "prediction markets. Earns bid-ask spread across {n_markets} markets "
        "with {freq} trade frequency. Demands continuous position management "
        "and risk hedging."
    ),
    "trend_following": (
        "Trader follows market trends, taking directional positions in markets "
        "showing momentum. Holds positions for average of {avg_hold} and "
        "concentrates on {n_markets} markets. Risk comes from trend reversals."
    ),
    "event_driven": (
        "Trader focuses on specific event categories, concentrating {concentration:.0%} "
        "of portfolio in related markets. Leverages domain expertise in specific topics, "
        "trading {n_markets} event markets."
    ),
    "diversified": (
        "Trader uses a diversified approach, spreading positions across {n_markets} "
        "different markets with {freq} frequency. Largest single position is "
        "{max_position_pct:.0%} of portfolio, suggesting risk-aware strategy."
    ),
    "scalping": (
        "Trader scalps small profits from rapid trades, executing at {freq} frequency "
        "with very short hold times. Average profit per trade is ${avg_pnl_per_trade:.2f}. "
        "Requires constant monitoring and low transaction costs."
    ),
    "unknown": (
        "Strategy does not clearly match common patterns. Traded in {n_markets} markets "
        "with {freq} frequency. Further data needed to classify approach more precisely."
    ),
}

FREQUENCY_LABELS = [
    (0, 1, "very low"),
    (1, 5, "low"),
    (5, 20, "moderate"),
    (20, 50, "high"),
    (50, float("inf"), "very high"),
]


class StrategyAnalyzer:
    """Classify trading strategy using rule-based behavioral profiling."""

    def classify(
        self,
        positions: list[dict[str, Any]],
        trades: list[dict[str, Any]],
        activity: list[dict[str, Any]],
    ) -> StrategyClassification:
        indicators: dict[str, float] = {}

        n_trades = len(trades) + len(activity)
        n_positions = len(positions)
        unique_markets = self._count_unique_markets(positions, trades)

        indicators["n_trades"] = float(n_trades)
        indicators["n_positions"] = float(n_positions)
        indicators["unique_markets"] = float(unique_markets)

        both_sides_ratio = self._both_sides_ratio(trades)
        indicators["both_sides_ratio"] = both_sides_ratio

        avg_hold_hours = self._estimate_avg_hold_hours(trades)
        indicators["avg_hold_hours"] = avg_hold_hours

        concentration = self._market_concentration(positions)
        indicators["concentration"] = concentration

        avg_margin = self._avg_trade_margin(trades)
        indicators["avg_margin"] = avg_margin

        freq = self._trades_per_day(trades, activity)
        indicators["trades_per_day"] = freq

        # Rule-based classification (priority order)
        if both_sides_ratio > 0.3 and freq > 20 and avg_margin < 0.05:
            strategy_type = "arbitrage"
            confidence = min(both_sides_ratio, 0.9)
        elif both_sides_ratio > 0.25 and unique_markets > 5 and n_trades > 100:
            strategy_type = "market_making"
            confidence = 0.7
        elif avg_hold_hours < 2 and freq > 15:
            strategy_type = "scalping"
            confidence = 0.7
        elif concentration > 0.6 and unique_markets < 10:
            strategy_type = "event_driven"
            confidence = min(concentration, 0.9)
        elif avg_hold_hours > 48 and both_sides_ratio < 0.1:
            strategy_type = "trend_following"
            confidence = 0.6
        elif unique_markets > 10 and concentration < 0.3:
            strategy_type = "diversified"
            confidence = 0.6
        else:
            strategy_type = "unknown"
            confidence = 0.3

        result = StrategyClassification(
            strategy_type=strategy_type,
            confidence=confidence,
            indicators=indicators,
        )

        logger.info(
            "strategy_classified",
            strategy_type=strategy_type,
            confidence=confidence,
        )
        return result

    def assess_risk(
        self,
        positions: list[dict[str, Any]],
        classification: StrategyClassification,
    ) -> RiskAssessment:
        concentration = classification.indicators.get("concentration", 0)
        n_positions = len(positions)

        if (
            concentration > 0.7
            or n_positions < 3
            or classification.strategy_type in ("arbitrage", "scalping")
        ):
            level = "High"
        elif concentration > 0.4 or n_positions < 10:
            level = "Medium"
        else:
            level = "Low"

        justification = self._build_risk_justification(
            level, concentration, n_positions, classification
        )
        return RiskAssessment(
            level=level,
            justification=justification,
            concentration_ratio=round(concentration, 3),
            volatility_exposure=round(concentration, 3),
        )

    def calculate_success_score(
        self,
        classification: StrategyClassification,
        is_bot: bool,
        pnl: float,
    ) -> int:
        """Barrier-to-replication score: 1=easy to replicate, 10=very hard."""
        score = 1

        complexity_map = {
            "arbitrage": 3,
            "market_making": 3,
            "scalping": 2,
            "event_driven": 1,
            "trend_following": 1,
            "diversified": 0,
            "unknown": 1,
        }
        score += complexity_map.get(classification.strategy_type, 1)

        if is_bot:
            score += 2

        freq = classification.indicators.get("trades_per_day", 0)
        if freq > 50:
            score += 2
        elif freq > 20:
            score += 1

        if abs(pnl) > 100000:
            score += 1

        return min(max(score, 1), 10)

    def generate_description(
        self,
        classification: StrategyClassification,
        positions: list[dict[str, Any]],
        trades: list[dict[str, Any]],
        pnl: float,
    ) -> str:
        """Generate template-based strategy description (<=500 chars)."""
        template = STRATEGY_TEMPLATES[classification.strategy_type]

        freq = classification.indicators.get("trades_per_day", 0)
        freq_label = "moderate"
        for lo, hi, label in FREQUENCY_LABELS:
            if lo <= freq < hi:
                freq_label = label
                break

        n_markets = int(classification.indicators.get("unique_markets", 0))
        n_trades = int(classification.indicators.get("n_trades", 0))
        avg_margin = classification.indicators.get("avg_margin", 0)
        concentration = classification.indicators.get("concentration", 0)
        avg_hold = self._format_hold_time(
            classification.indicators.get("avg_hold_hours", 0)
        )
        avg_pnl_per_trade = pnl / max(n_trades, 1)

        description = template.format(
            freq=freq_label,
            avg_margin=avg_margin,
            n_markets=n_markets,
            avg_hold=avg_hold,
            concentration=concentration,
            max_position_pct=concentration,
            avg_pnl_per_trade=avg_pnl_per_trade,
        )
        return description[:500]

    # --- Private helpers ---

    def _count_unique_markets(
        self, positions: list[dict[str, Any]], trades: list[dict[str, Any]]
    ) -> int:
        markets: set[str] = set()
        for p in positions:
            cid = p.get("conditionId")
            if cid:
                markets.add(cid)
        for t in trades:
            cid = t.get("conditionId")
            if cid:
                markets.add(cid)
        return len(markets)

    def _both_sides_ratio(self, trades: list[dict[str, Any]]) -> float:
        market_sides: dict[str, set[str]] = {}
        for t in trades:
            cid = t.get("conditionId", "")
            side = t.get("side", "")
            if cid and side:
                market_sides.setdefault(cid, set()).add(side)
        if not market_sides:
            return 0.0
        both = sum(1 for sides in market_sides.values() if len(sides) > 1)
        return both / len(market_sides)

    def _estimate_avg_hold_hours(self, trades: list[dict[str, Any]]) -> float:
        market_times: dict[str, list[int]] = {}
        for t in trades:
            cid = t.get("conditionId", "")
            ts = t.get("timestamp")
            if cid and ts is not None:
                market_times.setdefault(cid, []).append(int(ts))
        if not market_times:
            return 24.0
        spans: list[float] = []
        for times in market_times.values():
            if len(times) >= 2:
                spans.append((max(times) - min(times)) / 3600)
        return statistics.mean(spans) if spans else 24.0

    def _market_concentration(self, positions: list[dict[str, Any]]) -> float:
        values: list[float] = []
        for p in positions:
            cv = p.get("currentValue")
            if cv is not None:
                values.append(abs(float(cv)))
        if not values:
            return 0.0
        return max(values) / max(sum(values), 1)

    def _avg_trade_margin(self, trades: list[dict[str, Any]]) -> float:
        prices = [float(t["price"]) for t in trades if "price" in t and t["price"] is not None]
        if not prices:
            return 0.0
        return statistics.mean(abs(p - 0.5) for p in prices)

    def _trades_per_day(
        self, trades: list[dict[str, Any]], activity: list[dict[str, Any]]
    ) -> float:
        timestamps: list[int] = []
        for t in trades:
            ts = t.get("timestamp")
            if ts is not None:
                timestamps.append(int(ts))
        for a in activity:
            ts = a.get("timestamp")
            if ts is not None:
                timestamps.append(int(ts))
        if len(timestamps) < 2:
            return float(len(timestamps))
        timestamps.sort()
        span_days = max((timestamps[-1] - timestamps[0]) / 86400, 1)
        return len(timestamps) / span_days

    def _build_risk_justification(
        self,
        level: str,
        concentration: float,
        n_positions: int,
        classification: StrategyClassification,
    ) -> str:
        parts = [f"Risk level: {level}."]
        if concentration > 0.5:
            parts.append(f"High concentration ({concentration:.0%}) in top market.")
        if n_positions < 5:
            parts.append(f"Only {n_positions} active positions (low diversification).")
        if classification.strategy_type in ("arbitrage", "scalping"):
            parts.append(
                f"{classification.strategy_type.replace('_', ' ').title()} strategies carry "
                "inherent execution and timing risk."
            )
        if level == "Low":
            parts.append("Well diversified across multiple markets.")
        return " ".join(parts)

    def _format_hold_time(self, hours: float) -> str:
        if hours < 1:
            return f"{int(hours * 60)} minutes"
        if hours < 48:
            return f"{hours:.0f} hours"
        return f"{hours / 24:.0f} days"
