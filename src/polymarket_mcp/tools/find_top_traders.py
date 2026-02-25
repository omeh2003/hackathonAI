"""MCP tool: find_top_traders."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field


def register(mcp):  # noqa: ANN001
    @mcp.tool(
        name="find_top_traders",
        description=(
            "Find the top performing traders on Polymarket by PnL. "
            "Returns each trader's wallet, PnL, and bot detection status."
        ),
    )
    async def find_top_traders(
        limit: Annotated[int, Field(ge=1, le=50, description="Number of traders (1-50)")] = 10,
        timeframe: Annotated[
            Literal["7d", "30d", "all_time"],
            Field(description="Leaderboard timeframe"),
        ] = "all_time",
        ctx=None,
    ) -> list[dict]:
        """Find top Polymarket traders by PnL with bot detection."""
        service = ctx.deps["trader_service"]
        results = await service.find_top_traders(limit=limit, timeframe=timeframe)
        return [r.model_dump() for r in results]
