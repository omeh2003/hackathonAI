"""MCP tool: generate_batch_report."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field


def register(mcp):  # noqa: ANN001
    @mcp.tool(
        name="generate_batch_report",
        description=(
            "Generate a batch analysis report for multiple Polymarket traders. "
            "Processes traders in parallel with concurrency control."
        ),
    )
    async def generate_batch_report(
        profile_ids: Annotated[
            list[str],
            Field(
                min_length=1,
                max_length=20,
                description="List of wallet addresses (0x...) or @usernames",
            ),
        ],
        ctx=None,
    ) -> dict:
        """Generate batch analysis report for multiple traders."""
        service = ctx.deps["trader_service"]
        items, latency_ms = await service.generate_batch_report(profile_ids)
        return {
            "results": [item.model_dump() for item in items],
            "total_latency_ms": round(latency_ms, 1),
        }
