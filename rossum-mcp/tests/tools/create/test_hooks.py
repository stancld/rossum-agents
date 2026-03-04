"""Tests for rossum_mcp.tools.create.hooks module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_hook
from rossum_mcp.tools import base
from rossum_mcp.tools.create.handler import register_create_tools
from rossum_mcp.tools.create.hooks import (
    _validate_events,
)

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


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
class TestCreateHook:
    """Tests for create_hook tool."""

    @pytest.mark.asyncio
    async def test_create_hook_success(self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch) -> None:
        """Test successful hook creation."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("API_TOKEN_OWNER", "https://api.test.rossum.ai/v1/users/1")

        importlib.reload(base)

        register_create_tools(mock_mcp, mock_client)

        mock_hook = create_mock_hook(id=200, name="New Hook", type="function")
        mock_client.create_new_hook.return_value = mock_hook

        create_hook = mock_mcp._tools["create_hook"]
        result = await create_hook(name="New Hook", type="function")

        assert result.id == 200
        assert result.name == "New Hook"

    @pytest.mark.asyncio
    async def test_create_hook_with_config(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test hook creation with configuration."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("API_TOKEN_OWNER", "https://api.test.rossum.ai/v1/users/1")

        importlib.reload(base)

        register_create_tools(mock_mcp, mock_client)

        mock_hook = create_mock_hook(id=200, name="Configured Hook")
        mock_client.create_new_hook.return_value = mock_hook

        create_hook = mock_mcp._tools["create_hook"]
        result = await create_hook(
            name="Configured Hook",
            type="function",
            config={"source": "def rossum_hook(): pass", "runtime": "python3.12"},
            events=["annotation_content.initialize"],
            queues=["https://api.test.rossum.ai/v1/queues/1"],
        )

        assert result.id == 200
        mock_client.create_new_hook.assert_called_once()
        call_args = mock_client.create_new_hook.call_args[0][0]
        assert call_args["name"] == "Configured Hook"
        assert "code" in call_args["config"]  # source converted to code

    @pytest.mark.asyncio
    async def test_create_hook_with_settings_secret_timeout(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test hook creation with settings, secret, and timeout_s capping."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("API_TOKEN_OWNER", "https://api.test.rossum.ai/v1/users/1")

        importlib.reload(base)

        register_create_tools(mock_mcp, mock_client)

        mock_hook = create_mock_hook(id=201, name="Full Config Hook")
        mock_client.create_new_hook.return_value = mock_hook

        create_hook = mock_mcp._tools["create_hook"]
        result = await create_hook(
            name="Full Config Hook",
            type="function",
            config={"timeout_s": 120},
            settings={"key": "value"},
            secret="my-secret",
        )

        assert result.id == 201
        call_args = mock_client.create_new_hook.call_args[0][0]
        assert call_args["config"]["timeout_s"] == 60  # capped at 60
        assert call_args["settings"] == {"key": "value"}
        assert call_args["secret"] == "my-secret"


@pytest.mark.unit
class TestCreateHookFromTemplate:
    """Tests for create_hook_from_template tool."""

    @pytest.mark.asyncio
    async def test_create_hook_from_template_invalid_events(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that invalid event format raises ValueError."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        mock_http_client = AsyncMock()
        mock_http_client.base_url = "https://api.test.rossum.ai/v1"
        mock_client._http_client = mock_http_client

        create_hook_from_template = mock_mcp._tools["create_hook_from_template"]
        with pytest.raises(ValueError, match=r"Invalid event.*annotation_content.*event\.action"):
            await create_hook_from_template(
                name="My Hook",
                hook_template_id=5,
                queues=["https://api.test.rossum.ai/v1/queues/1"],
                events=["annotation_content"],
            )
        mock_http_client.request_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_hook_from_template_webhook_with_external_url(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test creating a hook from template via hooks/create endpoint."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("API_TOKEN_OWNER", "https://api.test.rossum.ai/v1/users/1")

        importlib.reload(base)

        register_create_tools(mock_mcp, mock_client)

        # Mock the HTTP client for hooks/create POST and the base_url property
        mock_http_client = AsyncMock()
        mock_http_client.base_url = "https://api.test.rossum.ai/v1"
        mock_http_client.request_json.return_value = {"id": 300}
        mock_client._http_client = mock_http_client

        mock_hook = create_mock_hook(id=300, name="Template Hook")
        mock_client.retrieve_hook.return_value = mock_hook

        create_hook_from_template = mock_mcp._tools["create_hook_from_template"]
        result = await create_hook_from_template(
            name="My Webhook Hook",
            hook_template_id=5,
            queues=["https://api.test.rossum.ai/v1/queues/1"],
            events=["annotation_content.initialize"],
        )

        assert result.id == 300
        mock_http_client.request_json.assert_called_once_with(
            "POST",
            "hooks/create",
            json={
                "name": "My Webhook Hook",
                "hook_template": "https://api.test.rossum.ai/v1/hook_templates/5",
                "queues": ["https://api.test.rossum.ai/v1/queues/1"],
                "events": ["annotation_content.initialize"],
            },
        )
        mock_client.retrieve_hook.assert_called_once_with(300)

    @pytest.mark.asyncio
    async def test_create_hook_from_template_missing_hook_id(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test error handling when API response doesn't contain hook ID."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("API_TOKEN_OWNER", "https://api.test.rossum.ai/v1/users/1")

        importlib.reload(base)

        register_create_tools(mock_mcp, mock_client)

        # Mock the HTTP client - API returns response without id
        mock_http_client = AsyncMock()
        mock_http_client.base_url = "https://api.test.rossum.ai/v1"
        mock_http_client.request_json.return_value = {}
        mock_client._http_client = mock_http_client

        create_hook_from_template = mock_mcp._tools["create_hook_from_template"]
        result = await create_hook_from_template(
            name="My Webhook Hook",
            hook_template_id=5,
            queues=["https://api.test.rossum.ai/v1/queues/1"],
            events=["annotation_content.initialize"],
        )

        assert "error" in result
        assert "Hook wasn't likely created" in result["error"]
        mock_client.retrieve_hook.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_hook_from_template_with_token_owner(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test creating a hook from template with token_owner parameter."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("API_TOKEN_OWNER", "https://api.test.rossum.ai/v1/users/1")

        importlib.reload(base)

        register_create_tools(mock_mcp, mock_client)

        # Mock the HTTP client for hooks/create POST
        mock_http_client = AsyncMock()
        mock_http_client.base_url = "https://api.test.rossum.ai/v1"
        mock_http_client.request_json.return_value = {"id": 400}
        mock_client._http_client = mock_http_client

        mock_hook = create_mock_hook(id=400, name="Function Template Hook")
        mock_client.retrieve_hook.return_value = mock_hook

        create_hook_from_template = mock_mcp._tools["create_hook_from_template"]
        result = await create_hook_from_template(
            name="My Function Hook",
            hook_template_id=10,
            queues=["https://api.test.rossum.ai/v1/queues/1"],
            events=["annotation_content.initialize"],
            token_owner="https://api.test.rossum.ai/v1/users/42",
        )

        assert result.id == 400
        mock_http_client.request_json.assert_called_once_with(
            "POST",
            "hooks/create",
            json={
                "name": "My Function Hook",
                "hook_template": "https://api.test.rossum.ai/v1/hook_templates/10",
                "queues": ["https://api.test.rossum.ai/v1/queues/1"],
                "events": ["annotation_content.initialize"],
                "token_owner": "https://api.test.rossum.ai/v1/users/42",
            },
        )
        mock_client.retrieve_hook.assert_called_once_with(400)


@pytest.mark.unit
class TestValidateEvents:
    """Tests for _validate_events helper."""

    def test_valid_events(self) -> None:
        result = _validate_events(["annotation_content.initialize", "upload.created"])
        assert result == ["annotation_content.initialize", "upload.created"]

    def test_invalid_event_raises(self) -> None:
        with pytest.raises(ValueError, match=r"Invalid event.*annotation_content.*event\.action"):
            _validate_events(["annotation_content"])

    def test_mixed_valid_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match=r"Invalid event.*bad_event"):
            _validate_events(["annotation_content.initialize", "bad_event"])
