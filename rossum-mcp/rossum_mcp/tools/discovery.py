"""Discovery tools for dynamic tool loading.

Provides MCP tool to explore available tool categories and their metadata.
The agent uses this to fetch the catalog and load tools on-demand.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from rossum_mcp.tools.catalog import TOOL_CATALOG

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_discovery_tools(mcp: FastMCP) -> None:
    """Register discovery tools with the FastMCP server."""

    @mcp.tool(
        description="List tool categories (descriptions, tool names, keywords). Use load_tool_category to load a category. read_only=false indicates write tools."
    )
    async def list_tool_categories() -> list[dict]:
        return [
            {
                "name": category.name,
                "description": category.description,
                "tool_count": len(category.tools),
                "tools": [asdict(tool) for tool in category.tools],
                "keywords": category.keywords,
            }
            for category in TOOL_CATALOG.values()
        ]
