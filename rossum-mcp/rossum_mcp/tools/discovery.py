"""Discovery tools for dynamic tool loading.

Provides MCP tool to explore available tool categories and their metadata.
Tool lists are derived from tags on @mcp.tool decorators rather than a static catalog.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_mcp.tools.catalog import CATEGORY_META

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_discovery_tools(mcp: FastMCP) -> None:
    @mcp.tool(
        description="List tool categories (descriptions, tool names, keywords). Use load_tool_category to load a category. read_only=false indicates write tools."
    )
    async def list_tool_categories() -> list[dict]:
        all_tools = await mcp.local_provider.list_tools()

        # Group tools by category tag.
        # Each tool is assigned to exactly one category: the most specific match.
        # Generic categories ("read", "write") are used only when no domain category matches.
        generic_categories = {"read", "write"}
        categories: dict[str, list[dict]] = {}
        for tool in all_tools:
            tool_tags = tool.tags or set()
            matching = [c for c in CATEGORY_META if c in tool_tags]
            if not matching:
                continue
            # Prefer domain-specific category over generic ones
            domain = [c for c in matching if c not in generic_categories]
            chosen = domain[0] if domain else matching[0]
            categories.setdefault(chosen, []).append(
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "read_only": "write" not in tool_tags,
                }
            )

        return [
            {
                "name": cat_name,
                "description": meta.description,
                "tool_count": len(categories.get(cat_name, [])),
                "tools": categories.get(cat_name, []),
                "keywords": meta.keywords,
            }
            for cat_name, meta in CATEGORY_META.items()
        ]
