"""Tests for rossum_mcp.tools.base module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture(autouse=True)
def reset_mcp_mode():
    """Reset MCP mode to read-write after each test."""
    yield
    from rossum_mcp.tools.base import set_mcp_mode

    set_mcp_mode("read-write")


@pytest.mark.unit
class TestMCPMode:
    """Tests for MCP mode functions."""

    def test_default_mode_is_read_write(self, monkeypatch: MonkeyPatch) -> None:
        """Test that default mode is read-write when env var not set."""
        monkeypatch.delenv("ROSSUM_MCP_MODE", raising=False)
        from rossum_mcp.tools import base

        importlib.reload(base)
        assert base.get_mcp_mode() == "read-write"

    def test_initializes_from_env_var(self, monkeypatch: MonkeyPatch) -> None:
        """Test mode initializes from env var."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        from rossum_mcp.tools import base

        importlib.reload(base)
        assert base.get_mcp_mode() == "read-only"

    def test_set_and_get_mode(self) -> None:
        """Test setting and getting mode."""
        from rossum_mcp.tools.base import get_mcp_mode, set_mcp_mode

        set_mcp_mode("read-only")
        assert get_mcp_mode() == "read-only"

        set_mcp_mode("read-write")
        assert get_mcp_mode() == "read-write"

    def test_set_mode_case_insensitive(self) -> None:
        """Test set_mcp_mode is case-insensitive."""
        from rossum_mcp.tools.base import get_mcp_mode, set_mcp_mode

        set_mcp_mode("READ-ONLY")
        assert get_mcp_mode() == "read-only"

        set_mcp_mode("Read-Write")
        assert get_mcp_mode() == "read-write"

    def test_set_mode_invalid_raises_error(self) -> None:
        """Test set_mcp_mode with invalid value raises ValueError."""
        from rossum_mcp.tools.base import set_mcp_mode

        with pytest.raises(ValueError, match="Invalid mode"):
            set_mcp_mode("invalid-mode")

    def test_invalid_env_var_raises_error(self, monkeypatch: MonkeyPatch) -> None:
        """Test invalid ROSSUM_MCP_MODE env var raises ValueError."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "invalid-mode")
        from rossum_mcp.tools import base

        with pytest.raises(ValueError, match="Invalid ROSSUM_MCP_MODE"):
            importlib.reload(base)


@pytest.mark.unit
class TestBuildResourceUrl:
    """Tests for build_resource_url function."""

    def test_build_resource_url_with_base_url(self, monkeypatch: MonkeyPatch) -> None:
        """Test building resource URL with configured base URL."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        from rossum_mcp.tools import base

        importlib.reload(base)

        result = base.build_resource_url("queues", 123)
        assert result == "https://api.test.rossum.ai/v1/queues/123"

    def test_build_resource_url_different_resources(self, monkeypatch: MonkeyPatch) -> None:
        """Test building URLs for different resource types."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        from rossum_mcp.tools import base

        importlib.reload(base)

        assert base.build_resource_url("schemas", 456) == "https://api.test.rossum.ai/v1/schemas/456"
        assert base.build_resource_url("workspaces", 789) == "https://api.test.rossum.ai/v1/workspaces/789"


@pytest.mark.unit
class TestIsReadWriteMode:
    """Tests for is_read_write_mode function."""

    def test_returns_true_when_read_write(self) -> None:
        """Test is_read_write_mode returns True when mode is read-write."""
        from rossum_mcp.tools.base import is_read_write_mode, set_mcp_mode

        set_mcp_mode("read-write")
        assert is_read_write_mode() is True

    def test_returns_false_when_read_only(self) -> None:
        """Test is_read_write_mode returns False when mode is read-only."""
        from rossum_mcp.tools.base import is_read_write_mode, set_mcp_mode

        set_mcp_mode("read-only")
        assert is_read_write_mode() is False


@pytest.mark.unit
class TestDeleteResource:
    """Tests for delete_resource function."""

    @pytest.mark.asyncio
    async def test_delete_resource_success(self) -> None:
        """Test successful resource deletion."""
        from rossum_mcp.tools.base import delete_resource, set_mcp_mode

        set_mcp_mode("read-write")

        mock_delete_fn = AsyncMock()
        result = await delete_resource("queue", 123, mock_delete_fn)

        assert result == {"message": "Queue 123 deleted successfully"}
        mock_delete_fn.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_delete_resource_custom_message(self) -> None:
        """Test deletion with custom success message."""
        from rossum_mcp.tools.base import delete_resource, set_mcp_mode

        set_mcp_mode("read-write")

        mock_delete_fn = AsyncMock()
        result = await delete_resource("queue", 123, mock_delete_fn, "Queue 123 scheduled for deletion")

        assert result == {"message": "Queue 123 scheduled for deletion"}

    @pytest.mark.asyncio
    async def test_delete_resource_read_only_mode(self) -> None:
        """Test deletion is blocked in read-only mode."""
        from rossum_mcp.tools.base import delete_resource, set_mcp_mode

        set_mcp_mode("read-only")

        mock_delete_fn = AsyncMock()
        result = await delete_resource("queue", 123, mock_delete_fn)

        assert result == {"error": "delete_queue is not available in read-only mode"}
        mock_delete_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_resource_propagates_exception(self) -> None:
        """Test that API exceptions are propagated."""
        from rossum_mcp.tools.base import delete_resource, set_mcp_mode

        set_mcp_mode("read-write")

        mock_delete_fn = AsyncMock(side_effect=ValueError("Not Found"))
        with pytest.raises(ValueError, match="Not Found"):
            await delete_resource("queue", 99999, mock_delete_fn)
