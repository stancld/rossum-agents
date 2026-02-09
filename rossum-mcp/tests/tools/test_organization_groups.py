"""Tests for rossum_mcp.tools.organization_groups module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.organization_group import OrganizationGroup


def create_mock_organization_group(**kwargs) -> OrganizationGroup:
    """Create a mock OrganizationGroup dataclass instance with default values."""
    defaults = {
        "id": 1,
        "name": "Test Organization Group",
        "is_trial": False,
        "is_production": True,
        "deployment_location": "eu",
        "modified_by": None,
        "modified_at": None,
        "features": None,
        "usage": {},
    }
    defaults.update(kwargs)
    return OrganizationGroup(**defaults)


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
class TestGetOrganizationGroup:
    """Tests for get_organization_group tool."""

    @pytest.mark.asyncio
    async def test_get_organization_group_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful organization group retrieval."""
        from rossum_mcp.tools.organization_groups import register_organization_group_tools

        register_organization_group_tools(mock_mcp, mock_client)

        mock_org_group = create_mock_organization_group(id=100, name="Production Organization Group")
        mock_client.retrieve_organization_group.return_value = mock_org_group

        get_organization_group = mock_mcp._tools["get_organization_group"]
        result = await get_organization_group(organization_group_id=100)

        assert result.id == 100
        assert result.name == "Production Organization Group"
        mock_client.retrieve_organization_group.assert_called_once_with(100)


@pytest.mark.unit
class TestListOrganizationGroups:
    """Tests for list_organization_groups tool."""

    @pytest.mark.asyncio
    async def test_list_organization_groups_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful organization groups listing."""
        from rossum_mcp.tools.organization_groups import register_organization_group_tools

        register_organization_group_tools(mock_mcp, mock_client)

        mock_og1 = create_mock_organization_group(id=1, name="Organization Group 1")
        mock_og2 = create_mock_organization_group(id=2, name="Organization Group 2")

        async def mock_fetch_all(resource, **filters):
            yield mock_og1
            yield mock_og2

        mock_client._http_client.fetch_all = mock_fetch_all

        list_organization_groups = mock_mcp._tools["list_organization_groups"]
        result = await list_organization_groups()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_organization_groups_with_name_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test organization groups listing filtered by name."""
        from rossum_mcp.tools.organization_groups import register_organization_group_tools

        register_organization_group_tools(mock_mcp, mock_client)

        mock_og = create_mock_organization_group(id=1, name="Production")
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            received_filters.update(filters)
            yield mock_og

        mock_client._http_client.fetch_all = mock_fetch_all

        list_organization_groups = mock_mcp._tools["list_organization_groups"]
        result = await list_organization_groups(name="Production")

        assert len(result) == 1
        assert received_filters["name"] == "Production"

    @pytest.mark.asyncio
    async def test_list_organization_groups_skips_broken_items(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test list_organization_groups gracefully skips items that fail deserialization."""
        from rossum_mcp.tools.organization_groups import register_organization_group_tools

        register_organization_group_tools(mock_mcp, mock_client)

        mock_og = create_mock_organization_group(id=1, name="Good Organization Group")

        call_count = 0

        def mock_deserializer(resource, raw):
            nonlocal call_count
            call_count += 1
            if raw.get("id") == 2:
                raise ValueError("broken organization group")
            return mock_og

        mock_client._deserializer = mock_deserializer

        async def mock_fetch_all(resource, **filters):
            yield {"id": 1}
            yield {"id": 2}
            yield {"id": 3}

        mock_client._http_client.fetch_all = mock_fetch_all

        list_organization_groups = mock_mcp._tools["list_organization_groups"]
        result = await list_organization_groups()

        assert len(result) == 2
