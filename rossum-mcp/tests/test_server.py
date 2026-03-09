from __future__ import annotations

import pytest
from rossum_mcp.server import create_app


@pytest.fixture
def setup_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
    monkeypatch.setenv("ROSSUM_API_TOKEN", "test-token-123")
    monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mode_tools_are_exposed_under_documented_names(setup_env: None) -> None:
    app = create_app()

    tools = await app.local_provider.list_tools()
    tool_names = {tool.name for tool in tools}

    assert "get_mcp_mode" in tool_names
    assert "set_mcp_mode" in tool_names
    assert "get_mcp_mode_tool" not in tool_names
    assert "set_mcp_mode_tool" not in tool_names


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_tool_categories_includes_mode_category(setup_env: None) -> None:
    app = create_app()
    list_categories_tool = await app.get_tool("list_tool_categories")

    categories = await list_categories_tool.fn()

    category_names = {category["name"] for category in categories}
    assert "mcp_mode" in category_names

    mode_category = next(category for category in categories if category["name"] == "mcp_mode")
    assert {tool["name"] for tool in mode_category["tools"]} == {"get_mcp_mode", "set_mcp_mode"}
