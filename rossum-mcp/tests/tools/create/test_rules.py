"""Tests for rossum_mcp.tools.create.rules module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from fastmcp.exceptions import ToolError
from rossum_api.models.rule import Rule, RuleAction, ShowMessagePayload
from rossum_mcp.tools import base
from rossum_mcp.tools.create.handler import register_create_tools
from rossum_mcp.tools.validation import actions_to_dicts

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def create_mock_rule(**kwargs) -> Rule:
    """Create a mock Rule dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/rules/1",
        "name": "Test Rule",
        "enabled": True,
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "schema": "https://api.test.rossum.ai/v1/schemas/1",
        "trigger_condition": "True",
        "created_by": "https://api.test.rossum.ai/v1/users/1",
        "created_at": "2025-01-01T00:00:00Z",
        "modified_by": None,
        "modified_at": "2025-01-01T00:00:00Z",
        "rule_template": None,
        "synchronized_from_template": False,
        "actions": [],
    }
    defaults.update(kwargs)
    return Rule(**defaults)


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
class TestCreateRule:
    """Tests for create_rule tool."""

    @pytest.mark.asyncio
    async def test_create_rule_success(self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch) -> None:
        """Test successful rule creation."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        test_action = {
            "id": "action1",
            "type": "show_message",
            "event": "validation",
            "payload": {"type": "error", "content": "High value!", "schema_id": "amount"},
        }
        mock_rule = create_mock_rule(
            id=456,
            name="New Validation Rule",
            enabled=True,
            trigger_condition="field.amount > 1000",
            actions=[test_action],
        )
        mock_client.create_new_rule.return_value = mock_rule

        create_rule = mock_mcp._tools["create_rule"]
        result = await create_rule(
            name="New Validation Rule",
            schema_id=100,
            trigger_condition="field.amount > 1000",
            actions=[test_action],
            enabled=True,
        )

        assert result.id == 456
        assert result.name == "New Validation Rule"
        assert result.enabled is True
        mock_client.create_new_rule.assert_called_once()

        call_args = mock_client.create_new_rule.call_args[0][0]
        assert call_args["name"] == "New Validation Rule"
        assert call_args["schema"] == "https://api.test.rossum.ai/v1/schemas/100"
        assert call_args["trigger_condition"] == "field.amount > 1000"
        assert call_args["actions"] == [test_action]
        assert call_args["enabled"] is True

    @pytest.mark.asyncio
    async def test_create_rule_without_schema_id(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test creating a rule with only queue_ids (no schema_id)."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        mock_rule = create_mock_rule(id=457, name="Queue-only Rule", enabled=True)
        mock_client.create_new_rule.return_value = mock_rule

        create_rule = mock_mcp._tools["create_rule"]
        result = await create_rule(
            name="Queue-only Rule",
            trigger_condition="field.amount > 500",
            actions=[],
            queue_ids=[101],
        )

        assert result.id == 457
        call_args = mock_client.create_new_rule.call_args[0][0]
        assert "schema" not in call_args
        assert call_args["queues"] == ["https://api.test.rossum.ai/v1/queues/101"]

    @pytest.mark.asyncio
    async def test_create_rule_requires_scope(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_rule fails when neither schema_id nor queue_ids provided."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        create_rule = mock_mcp._tools["create_rule"]
        with pytest.raises(ToolError, match="Provide at least one of schema_id or queue_ids"):
            await create_rule(
                name="Unscoped Rule",
                trigger_condition="True",
                actions=[],
            )

        mock_client.create_new_rule.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_rule_with_disabled(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test creating a disabled rule."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        mock_rule = create_mock_rule(id=789, name="Disabled Rule", enabled=False)
        mock_client.create_new_rule.return_value = mock_rule

        create_rule = mock_mcp._tools["create_rule"]
        result = await create_rule(
            name="Disabled Rule",
            schema_id=200,
            trigger_condition="field.vendor_name.changed",
            actions=[],
            enabled=False,
        )

        assert result.id == 789
        assert result.enabled is False

        call_args = mock_client.create_new_rule.call_args[0][0]
        assert call_args["enabled"] is False

    @pytest.mark.asyncio
    async def test_create_rule_with_queue_ids(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test creating a rule with queue_ids."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        importlib.reload(base)
        register_create_tools(mock_mcp, mock_client)

        mock_rule = create_mock_rule(id=999, name="Queue Rule")
        mock_client.create_new_rule.return_value = mock_rule

        create_rule = mock_mcp._tools["create_rule"]
        result = await create_rule(
            name="Queue Rule",
            schema_id=100,
            trigger_condition="True",
            actions=[],
            queue_ids=[101, 102],
        )

        assert result.id == 999
        call_args = mock_client.create_new_rule.call_args[0][0]
        assert call_args["queues"] == [
            "https://api.test.rossum.ai/v1/queues/101",
            "https://api.test.rossum.ai/v1/queues/102",
        ]


@pytest.mark.unit
class TestActionsToDict:
    """Tests for actions_to_dicts helper."""

    def test_converts_dataclass_instances(self) -> None:
        action = RuleAction(
            id="act1",
            type="show_message",
            event="validation",
            payload=ShowMessagePayload(type="error", content="Bad value", schema_id="amount"),
        )
        result = actions_to_dicts([action])

        assert result == [
            {
                "id": "act1",
                "type": "show_message",
                "event": "validation",
                "enabled": True,
                "payload": {"type": "error", "content": "Bad value", "schema_id": "amount"},
            }
        ]

    def test_passes_through_raw_dicts(self) -> None:
        raw = {
            "id": "act1",
            "type": "show_message",
            "event": "validation",
            "payload": {"type": "error", "content": "X"},
        }
        result = actions_to_dicts([raw])

        assert result == [raw]

    def test_handles_mixed_list(self) -> None:
        dataclass_action = RuleAction(
            id="act1",
            type="show_message",
            event="validation",
            payload=ShowMessagePayload(type="info", content="OK"),
        )
        dict_action = {"id": "act2", "type": "custom", "event": "validation", "payload": {}}
        result = actions_to_dicts([dataclass_action, dict_action])

        assert len(result) == 2
        assert result[0] == {
            "id": "act1",
            "type": "show_message",
            "event": "validation",
            "enabled": True,
            "payload": {"type": "info", "content": "OK", "schema_id": None},
        }
        assert result[1] is dict_action
