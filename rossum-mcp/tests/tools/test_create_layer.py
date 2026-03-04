"""Tests for rossum_mcp.tools.generic.create — unified create tool."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.engine import Engine, EngineField
from rossum_api.models.hook import Hook
from rossum_api.models.queue import Queue
from rossum_api.models.rule import Rule
from rossum_api.models.schema import Schema
from rossum_api.models.user import User
from rossum_api.models.workspace import Workspace
from rossum_mcp.tools.generic.create import register_create_tools
from rossum_mcp.tools.generic.create.models import CREATE_MODELS, ENTITY_NOTES
from rossum_mcp.tools.generic.create.registry import build_create_registry

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


@pytest.fixture
def mock_client() -> AsyncMock:
    client = AsyncMock()
    client._http_client = AsyncMock()
    client._http_client.base_url = "https://api.test.rossum.ai/v1"
    client._deserializer = Mock(side_effect=lambda resource, raw: raw)
    return client


@pytest.fixture
def mock_mcp() -> Mock:
    """Create a mock FastMCP that captures registered tools by name."""
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


@pytest.fixture
def setup_env(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
    monkeypatch.setenv("ROSSUM_API_TOKEN", "test-token-123")
    monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")

    import importlib

    from rossum_mcp.tools import base

    importlib.reload(base)


def _workspace(**kw) -> Workspace:
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/workspaces/1",
        "name": "Test",
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "queues": [],
        "autopilot": False,
        "metadata": {},
    }
    defaults.update(kw)
    return Workspace(**defaults)


def _queue(**kw) -> Queue:
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/queues/1",
        "name": "Test",
        "workspace": "https://api.test.rossum.ai/v1/workspaces/1",
        "schema": "https://api.test.rossum.ai/v1/schemas/1",
        "inbox": None,
        "connector": None,
        "hooks": [],
        "counts": {},
        "users": [],
        "automation_enabled": False,
        "automation_level": "never",
        "locale": "en_GB",
        "status": "active",
        "dedicated_engine": None,
        "generic_engine": None,
        "engine": None,
        "training_enabled": True,
        "settings": {},
        "metadata": {},
        "use_confirmed_state": True,
        "default_score_threshold": 0.0,
        "document_lifetime": None,
        "delete_after": None,
    }
    defaults.update(kw)
    return Queue(**defaults)


def _schema(**kw) -> Schema:
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/schemas/1",
        "name": "Test",
        "queues": [],
        "content": [],
        "metadata": {},
    }
    defaults.update(kw)
    return Schema(**defaults)


def _user(**kw) -> User:
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/users/1",
        "username": "test@example.com",
        "email": "test@example.com",
        "first_name": "",
        "last_name": "",
        "date_joined": "2024-01-01T00:00:00Z",
        "queues": [],
        "groups": [],
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "oidc_id": None,
        "ui_settings": {},
        "metadata": {},
        "is_active": True,
        "auth_type": "password",
        "last_login": None,
    }
    defaults.update(kw)
    return User(**defaults)


def _hook(**kw) -> Hook:
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/hooks/1",
        "name": "Test Hook",
        "type": "function",
        "queues": [],
        "events": [],
        "config": {},
        "metadata": {},
        "active": True,
        "sideload": [],
        "token_owner": None,
        "settings": {},
        "secrets": {},
        "extension_source": "custom",
        "extension_image_url": None,
        "guide": None,
        "read_more_url": None,
        "run_after": [],
        "test": {},
    }
    defaults.update(kw)
    return Hook(**defaults)


def _engine(**kw) -> Engine:
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/engines/1",
        "name": "Test Engine",
        "type": "extractor",
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "learning_enabled": True,
        "description": "",
        "agenda_id": None,
        "training_queues": [],
    }
    defaults.update(kw)
    return Engine(**defaults)


def _engine_field(**kw) -> EngineField:
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/engine_fields/1",
        "name": "field_1",
        "label": "Field 1",
        "type": "string",
        "engine": "https://api.test.rossum.ai/v1/engines/1",
        "tabular": False,
        "multiline": False,
        "subtype": None,
        "pre_trained_field_id": None,
    }
    defaults.update(kw)
    return EngineField(**defaults)


def _rule(**kw) -> Rule:
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/rules/1",
        "name": "Test Rule",
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "trigger_condition": "True",
        "actions": [],
        "enabled": True,
        "schema": None,
    }
    defaults.update(kw)
    return Rule(**defaults)


@pytest.mark.unit
class TestToolRegistration:
    def test_registers_create(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        register_create_tools(mock_mcp, mock_client)
        assert "create" in mock_mcp._tools

    def test_registers_get_create_schema(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        register_create_tools(mock_mcp, mock_client)
        assert "get_create_schema" in mock_mcp._tools

    def test_registers_exactly_two_tools(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        register_create_tools(mock_mcp, mock_client)
        assert len(mock_mcp._tools) == 2


@pytest.mark.unit
class TestCreateRouting:
    @pytest.mark.asyncio
    async def test_create_workspace(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.create_new_workspace.return_value = _workspace(id=200, name="New WS")
        register_create_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["create"](entity="workspace", data={"name": "New WS", "organization_id": 1})
        assert result["id"] == 200
        assert result["name"] == "New WS"
        mock_client.create_new_workspace.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_queue_from_template(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_q = _queue(id=300, name="Template Q", schema="https://api.test.rossum.ai/v1/schemas/50")
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer = Mock(return_value=mock_q)
        mock_client.retrieve_schema.return_value = _schema(id=50)
        register_create_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["create"](
            entity="queue_from_template",
            data={"name": "Template Q", "template_name": "EU Demo Template", "workspace_id": 1},
        )
        assert result["id"] == 300
        mock_client._http_client.request_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_schema(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        content = [{"id": "sec", "label": "Section", "category": "section", "children": []}]
        mock_client.create_new_schema.return_value = _schema(id=100, name="New S", content=content)
        register_create_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["create"](entity="schema", data={"name": "New S", "content": content})
        assert result["id"] == 100
        mock_client.create_new_schema.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.create_new_user.return_value = _user(id=100, username="new@example.com")
        register_create_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["create"](
            entity="user", data={"username": "new@example.com", "email": "new@example.com"}
        )
        assert result["id"] == 100
        mock_client.create_new_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_hook(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.create_new_hook.return_value = _hook(id=200, name="New Hook")
        register_create_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["create"](entity="hook", data={"name": "New Hook", "type": "function"})
        assert result["id"] == 200
        mock_client.create_new_hook.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_hook_from_template(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client.retrieve_hook.return_value = _hook(id=300, name="Template Hook")
        register_create_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["create"](
            entity="hook_from_template",
            data={
                "name": "Template Hook",
                "hook_template_id": 5,
                "queues": ["https://api.test.rossum.ai/v1/queues/1"],
            },
        )
        assert result["id"] == 300

    @pytest.mark.asyncio
    async def test_create_engine(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_engine = _engine(id=200, name="New Engine")
        mock_client._http_client.create.return_value = {"id": 200}
        mock_client._deserializer = Mock(return_value=mock_engine)
        register_create_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["create"](
            entity="engine", data={"name": "New Engine", "organization_id": 1, "engine_type": "extractor"}
        )
        assert result["id"] == 200

    @pytest.mark.asyncio
    async def test_create_engine_field(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_field = _engine_field(id=500, label="Invoice Number")
        mock_client._http_client.create.return_value = {"id": 500}
        mock_client._deserializer = Mock(return_value=mock_field)
        register_create_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["create"](
            entity="engine_field",
            data={
                "engine_id": 123,
                "name": "invoice_number",
                "label": "Invoice Number",
                "field_type": "string",
                "schema_ids": [1, 2],
            },
        )
        assert result["id"] == 500

    @pytest.mark.asyncio
    async def test_create_rule(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        mock_client.create_new_rule.return_value = _rule(id=456, name="New Rule")
        register_create_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["create"](
            entity="rule",
            data={
                "name": "New Rule",
                "trigger_condition": "field.amount > 1000",
                "actions": [],
                "schema_id": 100,
            },
        )
        assert result["id"] == 456
        mock_client.create_new_rule.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_email_template(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        from rossum_api.models.email_template import EmailTemplate

        mock_template = EmailTemplate(
            id=200,
            url="https://api.test.rossum.ai/v1/email_templates/200",
            name="New Template",
            queue="https://api.test.rossum.ai/v1/queues/1",
            organization="https://api.test.rossum.ai/v1/organizations/1",
            subject="Welcome",
            message="<p>Hello</p>",
            type="custom",
            enabled=True,
            automate=False,
            to=[],
            cc=[],
            bcc=[],
            triggers=[],
        )
        mock_client.create_new_email_template.return_value = mock_template
        register_create_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["create"](
            entity="email_template",
            data={"name": "New Template", "queue": 1, "subject": "Welcome", "message": "<p>Hello</p>"},
        )
        assert result["id"] == 200
        mock_client.create_new_email_template.assert_called_once()


@pytest.mark.unit
class TestCreateErrors:
    @pytest.mark.asyncio
    async def test_unknown_entity_returns_error(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        register_create_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["create"](entity="nonexistent", data={"name": "test"})
        assert "error" in result
        assert "Unknown entity" in result["error"]

    @pytest.mark.asyncio
    async def test_validation_error_returns_schema(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        register_create_tools(mock_mcp, mock_client)

        # Missing required 'name' field for workspace
        result = await mock_mcp._tools["create"](entity="workspace", data={"organization_id": 1})
        assert "error" in result
        assert result["error"] == "Validation failed"
        assert "details" in result
        assert "expected_schema" in result
        # Schema should have workspace-specific fields
        assert "organization_id" in result["expected_schema"]["properties"]


@pytest.mark.unit
class TestGetCreateSchema:
    @pytest.mark.asyncio
    async def test_returns_schema_for_each_entity(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        register_create_tools(mock_mcp, mock_client)

        for entity_name in CREATE_MODELS:
            result = await mock_mcp._tools["get_create_schema"](entity=entity_name)
            assert "properties" in result, f"No properties for {entity_name}"
            # entity field should be stripped
            assert "entity" not in result["properties"], f"entity field not stripped for {entity_name}"

    @pytest.mark.asyncio
    async def test_includes_notes_when_available(
        self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None
    ) -> None:
        register_create_tools(mock_mcp, mock_client)

        for entity_name, note in ENTITY_NOTES.items():
            result = await mock_mcp._tools["get_create_schema"](entity=entity_name)
            assert result["note"] == note

    @pytest.mark.asyncio
    async def test_no_note_for_workspace(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        register_create_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get_create_schema"](entity="workspace")
        assert "note" not in result

    @pytest.mark.asyncio
    async def test_unknown_entity_returns_error(self, mock_mcp: Mock, mock_client: AsyncMock, setup_env: None) -> None:
        register_create_tools(mock_mcp, mock_client)

        result = await mock_mcp._tools["get_create_schema"](entity="nonexistent")
        assert "error" in result


@pytest.mark.unit
class TestCreateRegistry:
    def test_all_entities_in_registry(self, mock_client: AsyncMock, setup_env: None) -> None:
        registry = build_create_registry(mock_client)
        expected = {
            "workspace",
            "queue_from_template",
            "schema",
            "user",
            "hook",
            "hook_from_template",
            "engine",
            "engine_field",
            "rule",
            "email_template",
        }
        assert set(registry.keys()) == expected

    def test_all_entities_have_create_fn(self, mock_client: AsyncMock, setup_env: None) -> None:
        registry = build_create_registry(mock_client)
        for entity_name, create_fn in registry.items():
            assert create_fn is not None, f"Entity '{entity_name}' has no create_fn"
