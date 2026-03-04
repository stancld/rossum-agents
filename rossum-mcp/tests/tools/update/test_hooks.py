"""Tests for rossum_mcp.tools.update.hooks module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from conftest import create_mock_hook
from rossum_mcp.tools import base
from rossum_mcp.tools.update.handler import register_update_tools
from rossum_mcp.tools.update.hooks import (
    _generate_hook_payload,
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
class TestUpdateHook:
    """Tests for update_hook tool."""

    @pytest.mark.asyncio
    async def test_update_hook_success(self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch) -> None:
        """Test successful hook update."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")

        importlib.reload(base)

        register_update_tools(mock_mcp, mock_client)

        existing_hook = create_mock_hook(
            id=100,
            name="Old Name",
            queues=["https://api.test.rossum.ai/v1/queues/1"],
            events=["annotation_content.initialize"],
            config={"runtime": "python3.12"},
        )
        mock_client.retrieve_hook.return_value = existing_hook

        updated_hook = create_mock_hook(id=100, name="New Name")
        mock_client.update_part_hook.return_value = updated_hook

        update_hook = mock_mcp._tools["update_hook"]
        result = await update_hook(hook_id=100, name="New Name")

        assert result.id == 100
        assert result.name == "New Name"
        mock_client.retrieve_hook.assert_called_once_with(100)
        mock_client.update_part_hook.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_hook_with_all_fields(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test hook update with all optional fields."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")

        importlib.reload(base)

        register_update_tools(mock_mcp, mock_client)

        existing_hook = create_mock_hook(id=100, name="Old Name", config=None)
        mock_client.retrieve_hook.return_value = existing_hook

        updated_hook = create_mock_hook(id=100, name="Updated")
        mock_client.update_part_hook.return_value = updated_hook

        update_hook = mock_mcp._tools["update_hook"]
        result = await update_hook(
            hook_id=100,
            name="Updated",
            queues=["https://api.test.rossum.ai/v1/queues/2"],
            events=["annotation_content.export"],
            config={"new": "config"},
            settings={"setting": "value"},
            active=False,
        )

        assert result.id == 100
        call_args = mock_client.update_part_hook.call_args[0][1]
        assert call_args["name"] == "Updated"
        assert call_args["queues"] == ["https://api.test.rossum.ai/v1/queues/2"]
        assert call_args["events"] == ["annotation_content.export"]
        assert call_args["config"] == {"new": "config"}
        assert call_args["settings"] == {"setting": "value"}
        assert call_args["active"] is False


@pytest.mark.unit
class TestTestHook:
    """Tests for test_hook tool."""

    @pytest.mark.asyncio
    async def test_test_hook_success(self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch) -> None:
        """Test successful hook test execution with auto-resolved annotation."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_update_tools(mock_mcp, mock_client)

        mock_hook = create_mock_hook(id=123, queues=["https://api.test.rossum.ai/v1/queues/100"])
        mock_client.retrieve_hook.return_value = mock_hook

        mock_annotation = Mock()
        mock_annotation.url = "https://api.test.rossum.ai/v1/annotations/789"

        async def mock_list_all(**kwargs):
            yield mock_annotation

        mock_client.list_annotations = mock_list_all

        generated_payload = {"payload": {"annotation": {}}}
        test_response = {"response": {"status_code": 200}}
        mock_client._http_client.request_json.side_effect = [generated_payload, test_response]

        test_hook = mock_mcp._tools["test_hook"]
        result = await test_hook(hook_id=123, event="annotation_content", action="initialize")

        assert result == {"response": {"status_code": 200}}
        assert mock_client._http_client.request_json.call_count == 2
        mock_client._http_client.request_json.assert_any_call(
            "POST",
            "hooks/123/generate_payload",
            json={
                "event": "annotation_content",
                "action": "initialize",
                "annotation": "https://api.test.rossum.ai/v1/annotations/789",
                "status": "to_review",
                "previous_status": "importing",
            },
        )
        mock_client._http_client.request_json.assert_any_call(
            "POST",
            "hooks/123/test",
            json={"payload": generated_payload},
        )

    @pytest.mark.asyncio
    async def test_test_hook_with_config(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test hook test with optional config override."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_update_tools(mock_mcp, mock_client)

        generated_payload = {"payload": {"annotation": {"id": 456}}}
        test_response = {"response": {"status_code": 200}}
        mock_client._http_client.request_json.side_effect = [generated_payload, test_response]

        test_hook = mock_mcp._tools["test_hook"]
        result = await test_hook(
            hook_id=123,
            event="annotation_content",
            action="initialize",
            annotation="https://api.test.rossum.ai/v1/annotations/456",
            status="confirmed",
            previous_status="to_review",
            config={"timeout_s": 30},
        )

        assert result == {"response": {"status_code": 200}}
        mock_client._http_client.request_json.assert_any_call(
            "POST",
            "hooks/123/test",
            json={
                "payload": generated_payload,
                "config": {"timeout_s": 30},
            },
        )


@pytest.mark.unit
class TestGenerateHookPayload:
    """Tests for _generate_hook_payload internal function."""

    @pytest.mark.asyncio
    async def test_generate_payload_auto_resolves_annotation(self, mock_client: AsyncMock) -> None:
        """Test that annotation_content events auto-resolve annotation and status from hook's queues."""
        mock_hook = create_mock_hook(id=123, queues=["https://api.test.rossum.ai/v1/queues/100"])
        mock_client.retrieve_hook.return_value = mock_hook

        mock_annotation = Mock()
        mock_annotation.url = "https://api.test.rossum.ai/v1/annotations/789"

        async def mock_list_all(**kwargs):
            yield mock_annotation

        mock_client.list_annotations = mock_list_all
        mock_client._http_client.request_json.return_value = {"payload": {"annotation": {}}}

        result = await _generate_hook_payload(
            mock_client, hook_id=123, event="annotation_content", action="initialize"
        )

        assert "payload" in result
        mock_client._http_client.request_json.assert_called_once_with(
            "POST",
            "hooks/123/generate_payload",
            json={
                "event": "annotation_content",
                "action": "initialize",
                "annotation": "https://api.test.rossum.ai/v1/annotations/789",
                "status": "to_review",
                "previous_status": "importing",
            },
        )

    @pytest.mark.asyncio
    async def test_generate_payload_with_explicit_annotation(self, mock_client: AsyncMock) -> None:
        """Test payload generation with explicitly provided annotation URL."""
        mock_client._http_client.request_json.return_value = {"payload": {"annotation": {"id": 456}}}

        result = await _generate_hook_payload(
            mock_client,
            hook_id=123,
            event="annotation_content",
            action="initialize",
            annotation="https://api.test.rossum.ai/v1/annotations/456",
            status="confirmed",
            previous_status="to_review",
        )

        assert "payload" in result
        mock_client._http_client.request_json.assert_called_once_with(
            "POST",
            "hooks/123/generate_payload",
            json={
                "event": "annotation_content",
                "action": "initialize",
                "annotation": "https://api.test.rossum.ai/v1/annotations/456",
                "status": "confirmed",
                "previous_status": "to_review",
            },
        )

    @pytest.mark.asyncio
    async def test_generate_payload_no_annotations_found(self, mock_client: AsyncMock) -> None:
        """Test error when no annotations found on hook's queues."""
        mock_hook = create_mock_hook(id=123, queues=["https://api.test.rossum.ai/v1/queues/100"])
        mock_client.retrieve_hook.return_value = mock_hook

        async def mock_list_empty(**kwargs):
            return
            yield

        mock_client.list_annotations = mock_list_empty

        result = await _generate_hook_payload(
            mock_client, hook_id=123, event="annotation_content", action="initialize"
        )

        assert "error" in result

    @pytest.mark.asyncio
    async def test_generate_payload_non_annotation_event(self, mock_client: AsyncMock) -> None:
        """Test that non-annotation events skip auto-resolution."""
        mock_client._http_client.request_json.return_value = {"payload": {}}

        result = await _generate_hook_payload(mock_client, hook_id=123, event="invocation", action="scheduled")

        assert "payload" in result
        mock_client._http_client.request_json.assert_called_once_with(
            "POST",
            "hooks/123/generate_payload",
            json={"event": "invocation", "action": "scheduled"},
        )
