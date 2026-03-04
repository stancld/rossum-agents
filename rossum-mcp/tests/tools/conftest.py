"""Shared fixtures for tools tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def mock_mcp() -> Mock:
    """Create a mock FastMCP instance."""
    mcp = Mock()
    mcp.tool = Mock(side_effect=lambda **kwargs: lambda fn: fn)
    return mcp


@pytest.fixture
def mock_client() -> AsyncMock:
    """Create a mock AsyncRossumAPIClient."""
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._deserializer = Mock()
    return client
