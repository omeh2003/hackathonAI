"""MCP tool: analyze_trader_strategy."""

from __future__ import annotations

from typing import Annotated

from fastmcp import Context
from pydantic import Field


def register(mcp):  # noqa: ANN001
    @mcp.tool(
        name="analyze_trader_strategy",
        description=(
            "Analyze a specific Polymarket trader's strategy, risk level, "
            "and determine if they are a bot. Accepts wallet address (0x...) or @username."
        ),
    )
    async def analyze_trader_strategy(
        profile_id: Annotated[
            str, Field(description="Wallet address (0x...) or @username")
        ],
        ctx: Context = None,
    ) -> dict:
        """Analyze a Polymarket trader's strategy and bot status."""
        service = ctx.lifespan_context["trader_service"]
        result = await service.analyze_trader(profile_id=profile_id)
        return result.model_dump()
