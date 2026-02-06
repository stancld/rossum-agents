"""Tests for rossum_mcp.tools.rules module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.rule import Rule
from rossum_mcp.tools import base

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
class TestGetRule:
    """Tests for get_rule tool."""

    @pytest.mark.asyncio
    async def test_get_rule_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful rule retrieval."""
        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        mock_rule = create_mock_rule(id=123, name="Validation Rule", enabled=True)
        mock_client.retrieve_rule.return_value = mock_rule

        get_rule = mock_mcp._tools["get_rule"]
        result = await get_rule(rule_id=123)

        assert result.id == 123
        assert result.name == "Validation Rule"
        assert result.enabled is True
        mock_client.retrieve_rule.assert_called_once_with(123)


@pytest.mark.unit
class TestListRules:
    """Tests for list_rules tool."""

    @pytest.mark.asyncio
    async def test_list_rules_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful rules listing."""
        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        mock_rule1 = create_mock_rule(id=1, name="Rule 1")
        mock_rule2 = create_mock_rule(id=2, name="Rule 2")

        async def mock_fetch_all(resource, **filters):
            for item in [mock_rule1, mock_rule2]:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all

        list_rules = mock_mcp._tools["list_rules"]
        result = await list_rules()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_rules_with_schema_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test rules listing filtered by schema."""
        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        mock_rule = create_mock_rule(id=1, name="Schema Rule")
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            yield mock_rule

        mock_client._http_client.fetch_all = mock_fetch_all

        list_rules = mock_mcp._tools["list_rules"]
        result = await list_rules(schema_id=50)

        assert len(result) == 1
        assert received_filters["schema"] == 50

    @pytest.mark.asyncio
    async def test_list_rules_with_organization_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test rules listing filtered by organization."""
        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        mock_rule = create_mock_rule(id=1, name="Org Rule")
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            yield mock_rule

        mock_client._http_client.fetch_all = mock_fetch_all

        list_rules = mock_mcp._tools["list_rules"]
        result = await list_rules(organization_id=100)

        assert len(result) == 1
        assert received_filters["organization"] == 100

    @pytest.mark.asyncio
    async def test_list_rules_with_enabled_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test rules listing filtered by enabled status."""
        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        mock_rule = create_mock_rule(id=1, enabled=True)
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            yield mock_rule

        mock_client._http_client.fetch_all = mock_fetch_all

        list_rules = mock_mcp._tools["list_rules"]
        result = await list_rules(enabled=True)

        assert len(result) == 1
        assert received_filters["enabled"] is True

    @pytest.mark.asyncio
    async def test_list_rules_empty(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test rules listing when none exist."""
        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        async def mock_fetch_all(resource, **filters):
            return
            yield

        mock_client._http_client.fetch_all = mock_fetch_all

        list_rules = mock_mcp._tools["list_rules"]
        result = await list_rules()

        assert len(result) == 0
        assert result == []

    @pytest.mark.asyncio
    async def test_list_rules_skips_broken_items(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test list_rules gracefully skips items that fail deserialization."""
        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        good_rule = create_mock_rule(id=1, name="Good Rule")

        def mock_deserializer(resource, raw):
            if raw.get("id") == 2:
                raise ValueError("broken rule")
            return good_rule

        mock_client._deserializer = mock_deserializer

        async def mock_fetch_all(resource, **filters):
            yield {"id": 1, "name": "Good Rule"}
            yield {"id": 2, "name": "Broken Rule"}
            yield {"id": 3, "name": "Another Good Rule"}

        mock_client._http_client.fetch_all = mock_fetch_all

        list_rules = mock_mcp._tools["list_rules"]
        result = await list_rules()

        assert len(result) == 2


@pytest.mark.unit
class TestCreateRule:
    """Tests for create_rule tool."""

    @pytest.mark.asyncio
    async def test_create_rule_success(self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch) -> None:
        """Test successful rule creation."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        importlib.reload(base)

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

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

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

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

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        create_rule = mock_mcp._tools["create_rule"]
        result = await create_rule(
            name="Unscoped Rule",
            trigger_condition="True",
            actions=[],
        )

        assert result["error"] == "Provide at least one of schema_id or queue_ids to scope the rule."
        mock_client.create_new_rule.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_rule_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test create_rule is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        create_rule = mock_mcp._tools["create_rule"]
        result = await create_rule(
            name="Test Rule",
            trigger_condition="True",
            actions=[],
            queue_ids=[1],
        )

        assert result["error"] == "create_rule is not available in read-only mode"
        mock_client.create_new_rule.assert_not_called()

    @pytest.mark.asyncio
    async def test_create_rule_with_disabled(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test creating a disabled rule."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        importlib.reload(base)

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

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

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

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
class TestUpdateRule:
    """Tests for update_rule tool."""

    @pytest.mark.asyncio
    async def test_update_rule_success(self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch) -> None:
        """Test successful rule update (PUT)."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        importlib.reload(base)

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        existing_rule = create_mock_rule(
            id=123,
            name="Old Name",
            schema="https://api.test.rossum.ai/v1/schemas/50",
        )
        updated_rule = create_mock_rule(
            id=123,
            name="Updated Rule",
            trigger_condition="field.total > 5000",
            enabled=False,
        )
        mock_client.retrieve_rule.return_value = existing_rule
        mock_client._http_client.update = AsyncMock()
        mock_client.retrieve_rule.side_effect = [existing_rule, updated_rule]

        test_action = {
            "id": "act1",
            "type": "show_message",
            "event": "validation",
            "payload": {"type": "warning", "content": "Check this", "schema_id": "total"},
        }

        update_rule = mock_mcp._tools["update_rule"]
        result = await update_rule(
            rule_id=123,
            name="Updated Rule",
            trigger_condition="field.total > 5000",
            actions=[test_action],
            enabled=False,
        )

        assert result.id == 123
        assert result.name == "Updated Rule"
        mock_client._http_client.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_rule_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test update_rule is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        update_rule = mock_mcp._tools["update_rule"]
        result = await update_rule(
            rule_id=123,
            name="Test",
            trigger_condition="True",
            actions=[],
            enabled=True,
        )

        assert result["error"] == "update_rule is not available in read-only mode"


@pytest.mark.unit
class TestPatchRule:
    """Tests for patch_rule tool."""

    @pytest.mark.asyncio
    async def test_patch_rule_success(self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch) -> None:
        """Test successful rule patch (PATCH)."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        updated_rule = create_mock_rule(id=123, name="Patched Name", enabled=True)
        mock_client.update_part_rule.return_value = updated_rule

        patch_rule = mock_mcp._tools["patch_rule"]
        result = await patch_rule(rule_id=123, name="Patched Name")

        assert result.id == 123
        assert result.name == "Patched Name"
        mock_client.update_part_rule.assert_called_once_with(123, {"name": "Patched Name"})

    @pytest.mark.asyncio
    async def test_patch_rule_multiple_fields(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test patching multiple fields at once."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        updated_rule = create_mock_rule(id=123, enabled=False, trigger_condition="field.x > 0")
        mock_client.update_part_rule.return_value = updated_rule

        patch_rule = mock_mcp._tools["patch_rule"]
        result = await patch_rule(rule_id=123, enabled=False, trigger_condition="field.x > 0")

        assert result.enabled is False
        mock_client.update_part_rule.assert_called_once_with(
            123, {"trigger_condition": "field.x > 0", "enabled": False}
        )

    @pytest.mark.asyncio
    async def test_patch_rule_no_fields(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test patch_rule with no fields returns error."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        patch_rule = mock_mcp._tools["patch_rule"]
        result = await patch_rule(rule_id=123)

        assert result["error"] == "No fields provided to update"
        mock_client.update_part_rule.assert_not_called()

    @pytest.mark.asyncio
    async def test_patch_rule_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test patch_rule is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        patch_rule = mock_mcp._tools["patch_rule"]
        result = await patch_rule(rule_id=123, name="Test")

        assert result["error"] == "patch_rule is not available in read-only mode"
        mock_client.update_part_rule.assert_not_called()

    @pytest.mark.asyncio
    async def test_patch_rule_with_queue_ids(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test patching rule with queue_ids."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        importlib.reload(base)

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        updated_rule = create_mock_rule(id=123)
        mock_client.update_part_rule.return_value = updated_rule

        patch_rule = mock_mcp._tools["patch_rule"]
        await patch_rule(rule_id=123, queue_ids=[201, 202])

        mock_client.update_part_rule.assert_called_once_with(
            123,
            {
                "queues": [
                    "https://api.test.rossum.ai/v1/queues/201",
                    "https://api.test.rossum.ai/v1/queues/202",
                ]
            },
        )

    @pytest.mark.asyncio
    async def test_patch_rule_clear_queues(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test clearing rule queues with empty list."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        importlib.reload(base)

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        updated_rule = create_mock_rule(id=123)
        mock_client.update_part_rule.return_value = updated_rule

        patch_rule = mock_mcp._tools["patch_rule"]
        await patch_rule(rule_id=123, queue_ids=[])

        mock_client.update_part_rule.assert_called_once_with(123, {"queues": []})


@pytest.mark.unit
class TestDeleteRule:
    """Tests for delete_rule tool."""

    @pytest.mark.asyncio
    async def test_delete_rule_success(self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch) -> None:
        """Test successful rule deletion."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        mock_client.delete_rule.return_value = None

        delete_rule = mock_mcp._tools["delete_rule"]
        result = await delete_rule(rule_id=123)

        assert "deleted successfully" in result["message"]
        assert "123" in result["message"]
        mock_client.delete_rule.assert_called_once_with(123)

    @pytest.mark.asyncio
    async def test_delete_rule_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test delete_rule is blocked in read-only mode."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)

        from rossum_mcp.tools.rules import register_rule_tools

        register_rule_tools(mock_mcp, mock_client)

        delete_rule = mock_mcp._tools["delete_rule"]
        result = await delete_rule(rule_id=123)

        assert result["error"] == "delete_rule is not available in read-only mode"
        mock_client.delete_rule.assert_not_called()
