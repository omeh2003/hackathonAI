"""Pydantic schemas for all MCP tool inputs and outputs."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field


# --- find_top_traders ---


class TopTraderResult(BaseModel):
    profile_id: str = Field(description="Wallet address (0x...)")
    pnl: float = Field(description="Profit/Loss in USD")
    is_bot: bool = Field(description="Whether heuristics classify as bot")


# --- analyze_trader_strategy ---


class StrategyAnalysisResult(BaseModel):
    strategy_description: Annotated[
        str, Field(max_length=500, description="Template-generated strategy description")
    ]
    risk_level: Literal["Low", "Medium", "High"]
    risk_justification: str
    success_score: Annotated[
        int, Field(ge=1, le=10, description="Barrier to replication: 1=easy, 10=very hard")
    ]
    is_bot: bool


# --- generate_batch_report ---


class BatchReportItem(BaseModel):
    profile_id: str
    pnl: float
    risk_level: Literal["Low", "Medium", "High"]
    success_score: Annotated[int, Field(ge=1, le=10)]
    is_bot: bool


# --- Internal models ---


class StrategyClassification(BaseModel):
    """Result of rule-based strategy classification."""

    strategy_type: Literal[
        "arbitrage",
        "market_making",
        "trend_following",
        "event_driven",
        "diversified",
        "scalping",
        "unknown",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    indicators: dict[str, float]


class RiskAssessment(BaseModel):
    """Risk level with justification."""

    level: Literal["Low", "Medium", "High"]
    justification: str
    concentration_ratio: float
    volatility_exposure: float
