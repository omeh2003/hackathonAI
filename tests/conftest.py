"""Shared test fixtures and data factories."""

from __future__ import annotations

import pytest

from polymarket_mcp.config.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        polymarket_data_api_base="https://data-api.polymarket.com",
        polymarket_gamma_api_base="https://gamma-api.polymarket.com",
        request_timeout=5,
        max_concurrency=2,
        cache_ttl=0,
        bot_detection_threshold=0.6,
    )


# --- Data factories ---


def make_leaderboard_entry(
    rank: int = 1,
    wallet: str = "0xabc",
    pnl: float = 10000.0,
    name: str = "testuser",
) -> dict:
    return {
        "rank": str(rank),
        "proxyWallet": wallet,
        "userName": name,
        "vol": 50000.0,
        "pnl": pnl,
        "profileImage": "",
        "xUsername": "",
        "verifiedBadge": False,
    }


def make_trade(
    condition_id: str = "cond1",
    side: str = "BUY",
    price: float = 0.65,
    size: float = 100.0,
    ts: int = 1700000000,
) -> dict:
    return {
        "conditionId": condition_id,
        "side": side,
        "price": price,
        "size": size,
        "timestamp": ts,
        "title": "Test Market",
        "outcome": "Yes",
        "transactionHash": "0xtx",
    }


def make_activity(
    condition_id: str = "cond1",
    side: str = "BUY",
    price: float = 0.65,
    usdc_size: float = 65.0,
    ts: int = 1700000000,
) -> dict:
    return {
        "conditionId": condition_id,
        "side": side,
        "price": price,
        "usdcSize": usdc_size,
        "size": 100.0,
        "timestamp": ts,
        "type": "TRADE",
        "title": "Test Market",
        "outcome": "Yes",
    }


def make_position(
    condition_id: str = "cond1",
    cash_pnl: float = 500.0,
    current_value: float = 1500.0,
) -> dict:
    return {
        "conditionId": condition_id,
        "size": 10.0,
        "avgPrice": 0.5,
        "initialValue": 1000.0,
        "currentValue": current_value,
        "cashPnl": cash_pnl,
        "percentPnl": 50.0,
        "title": "Test Market",
        "outcome": "Yes",
        "endDate": "2025-12-31",
    }


def make_profile(wallet: str = "0xabc", name: str = "testuser") -> dict:
    return {
        "createdAt": "2023-01-01T00:00:00Z",
        "proxyWallet": wallet,
        "name": name,
        "pseudonym": "TestPseudonym",
        "bio": "",
        "displayUsernamePublic": True,
        "verifiedBadge": False,
        "users": [],
    }
