"""Unit tests for PnlCalculator."""

from __future__ import annotations

import pytest

from polymarket_mcp.core.pnl_calculator import PnlCalculator
from tests.conftest import make_position, make_trade


@pytest.fixture
def calc() -> PnlCalculator:
    return PnlCalculator()


class TestTotalPnl:
    def test_sums_cash_pnl(self, calc: PnlCalculator) -> None:
        positions = [
            make_position(cash_pnl=500.0),
            make_position(cash_pnl=-200.0),
            make_position(cash_pnl=300.0),
        ]
        assert calc.total_pnl(positions) == 600.0

    def test_empty_positions(self, calc: PnlCalculator) -> None:
        assert calc.total_pnl([]) == 0.0

    def test_none_cash_pnl_skipped(self, calc: PnlCalculator) -> None:
        positions = [{"cashPnl": None}, {"cashPnl": 100}]
        assert calc.total_pnl(positions) == 100.0


class TestTotalVolume:
    def test_sums_volume(self, calc: PnlCalculator) -> None:
        trades = [
            make_trade(size=100, price=0.5),
            make_trade(size=200, price=0.7),
        ]
        assert calc.total_volume(trades) == 190.0

    def test_empty_trades(self, calc: PnlCalculator) -> None:
        assert calc.total_volume([]) == 0.0


class TestWinRate:
    def test_calculates_win_rate(self, calc: PnlCalculator) -> None:
        positions = [
            make_position(cash_pnl=500),
            make_position(cash_pnl=-200),
            make_position(cash_pnl=300),
            make_position(cash_pnl=-100),
        ]
        assert calc.win_rate(positions) == 0.5

    def test_empty_positions(self, calc: PnlCalculator) -> None:
        assert calc.win_rate([]) == 0.0

    def test_all_wins(self, calc: PnlCalculator) -> None:
        positions = [make_position(cash_pnl=100) for _ in range(5)]
        assert calc.win_rate(positions) == 1.0
