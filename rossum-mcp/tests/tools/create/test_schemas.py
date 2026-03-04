"""Tests for create_schema operation."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_schema
from fastmcp.exceptions import ToolError
from rossum_mcp.tools.create.handler import register_create_tools


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.fixture
def mock_mcp() -> Mock:
    """Create a mock FastMCP instance that captures registered tools."""
    tools: dict = {}

    def tool_decorator(**kwargs):
        def wrapper(fn):
            tools[fn.__name__] = fn
            return fn

        return wrapper

    mcp = Mock()
    mcp.tool = tool_decorator
    mcp._tools = tools
    return mcp


@pytest.mark.unit
class TestCreateSchema:
    """Tests for create_schema tool."""

    @pytest.mark.asyncio
    async def test_create_schema_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful schema creation."""
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [{"id": "invoice_number", "label": "Invoice Number", "type": "string"}],
            }
        ]

        new_schema = create_mock_schema(id=100, name="New Schema", content=content)
        mock_client.create_new_schema.return_value = new_schema

        create_schema = mock_mcp._tools["create_schema"]
        result = await create_schema(name="New Schema", content=content)

        assert result.id == 100
        assert result.name == "New Schema"
        mock_client.create_new_schema.assert_called_once_with({"name": "New Schema", "content": content})

    @pytest.mark.asyncio
    async def test_create_schema_rejects_empty_content(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        register_create_tools(mock_mcp, mock_client, "https://api.test.rossum.ai/v1")

        create_schema = mock_mcp._tools["create_schema"]
        with pytest.raises(ToolError, match="empty content"):
            await create_schema(name="New Schema", content=[])

        mock_client.create_new_schema.assert_not_called()
