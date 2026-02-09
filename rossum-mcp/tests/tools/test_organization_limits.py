"""Tests for rossum_mcp.tools.organization_limits module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.organization_limit import EmailLimits, OrganizationLimit


def create_mock_organization_limit(**kwargs) -> OrganizationLimit:
    """Create a mock OrganizationLimit dataclass instance with default values."""
    email_defaults = {
        "count_today": 5,
        "count_today_notification": 2,
        "count_total": 100,
        "email_per_day_limit": 50,
        "email_per_day_limit_notification": 20,
        "email_total_limit": 10000,
        "last_sent_at": "2026-02-09T10:00:00Z",
        "last_sent_at_notification": "2026-02-09T09:00:00Z",
    }
    email_overrides = kwargs.pop("email_limits", {})
    if isinstance(email_overrides, dict):
        email_defaults.update(email_overrides)
        email_limits = EmailLimits(**email_defaults)
    else:
        email_limits = email_overrides

    defaults = {"email_limits": email_limits}
    defaults.update(kwargs)
    return OrganizationLimit(**defaults)


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    return AsyncMock()


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
class TestGetOrganizationLimit:
    """Tests for get_organization_limit tool."""

    @pytest.mark.asyncio
    async def test_get_organization_limit_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful organization limit retrieval."""
        from rossum_mcp.tools.organization_limits import register_organization_limit_tools

        register_organization_limit_tools(mock_mcp, mock_client)

        mock_limit = create_mock_organization_limit(email_limits={"count_today": 10, "email_per_day_limit": 100})
        mock_client.retrieve_organization_limit.return_value = mock_limit

        get_organization_limit = mock_mcp._tools["get_organization_limit"]
        result = await get_organization_limit(organization_id=42)

        assert result.email_limits.count_today == 10
        assert result.email_limits.email_per_day_limit == 100
        mock_client.retrieve_organization_limit.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_get_organization_limit_returns_full_email_limits(
        self, mock_mcp: Mock, mock_client: AsyncMock
    ) -> None:
        """Test that all EmailLimits fields are returned."""
        from rossum_mcp.tools.organization_limits import register_organization_limit_tools

        register_organization_limit_tools(mock_mcp, mock_client)

        mock_limit = create_mock_organization_limit()
        mock_client.retrieve_organization_limit.return_value = mock_limit

        get_organization_limit = mock_mcp._tools["get_organization_limit"]
        result = await get_organization_limit(organization_id=1)

        email_limits = result.email_limits
        assert email_limits.count_today == 5
        assert email_limits.count_today_notification == 2
        assert email_limits.count_total == 100
        assert email_limits.email_per_day_limit == 50
        assert email_limits.email_per_day_limit_notification == 20
        assert email_limits.email_total_limit == 10000
        assert email_limits.last_sent_at == "2026-02-09T10:00:00Z"
        assert email_limits.last_sent_at_notification == "2026-02-09T09:00:00Z"
