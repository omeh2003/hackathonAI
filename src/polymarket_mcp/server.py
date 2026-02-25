"""FastMCP server setup and tool registration."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastmcp import FastMCP

from polymarket_mcp.adapters.polymarket_client import PolymarketClient
from polymarket_mcp.config.settings import get_settings
from polymarket_mcp.core.bot_detector import BotDetector
from polymarket_mcp.core.pnl_calculator import PnlCalculator
from polymarket_mcp.core.strategy_analyzer import StrategyAnalyzer
from polymarket_mcp.logging.setup import setup_logging
from polymarket_mcp.services.trader_service import TraderService
from polymarket_mcp.tools import register_all_tools


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Initialize and teardown application resources."""
    settings = get_settings()
    setup_logging(settings.log_level)

    client = PolymarketClient(settings)
    trader_service = TraderService(
        client=client,
        bot_detector=BotDetector(threshold=settings.bot_detection_threshold),
        strategy_analyzer=StrategyAnalyzer(),
        pnl_calculator=PnlCalculator(),
        settings=settings,
    )

    yield {"trader_service": trader_service, "settings": settings}

    await client.close()


mcp = FastMCP(
    name="Polymarket AI Analyst",
    instructions=(
        "MCP server for finding and analyzing successful trading bots on Polymarket. "
        "Provides tools to discover top traders, analyze strategies, and generate reports."
    ),
    lifespan=lifespan,
)

register_all_tools(mcp)


def main() -> None:
    """Entry point respecting MCP_TRANSPORT env var."""
    settings = get_settings()
    if settings.mcp_transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport="http", host=settings.mcp_host, port=settings.mcp_port)


if __name__ == "__main__":
    main()
