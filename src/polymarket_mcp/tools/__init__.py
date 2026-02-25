"""MCP tool registration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_all_tools(mcp: FastMCP) -> None:
    from polymarket_mcp.tools.find_top_traders import register as reg_find
    from polymarket_mcp.tools.analyze_trader_strategy import register as reg_analyze
    from polymarket_mcp.tools.generate_batch_report import register as reg_batch

    reg_find(mcp)
    reg_analyze(mcp)
    reg_batch(mcp)
