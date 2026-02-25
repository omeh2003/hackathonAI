"""PnL aggregation from positions and trade data."""

from __future__ import annotations

from typing import Any


class PnlCalculator:
    """Calculate aggregate PnL metrics from position data."""

    def total_pnl(self, positions: list[dict[str, Any]]) -> float:
        total = 0.0
        for p in positions:
            cash_pnl = p.get("cashPnl")
            if cash_pnl is not None:
                total += float(cash_pnl)
        return round(total, 2)

    def total_volume(self, trades: list[dict[str, Any]]) -> float:
        total = 0.0
        for t in trades:
            size = t.get("size")
            price = t.get("price")
            if size is not None and price is not None:
                total += float(size) * float(price)
        return round(total, 2)

    def win_rate(self, positions: list[dict[str, Any]]) -> float:
        if not positions:
            return 0.0
        wins = sum(
            1
            for p in positions
            if p.get("cashPnl") is not None and float(p["cashPnl"]) > 0
        )
        return round(wins / len(positions), 3)
