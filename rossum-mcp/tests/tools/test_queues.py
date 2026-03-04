"""Tests for rossum_mcp.tools.queues module."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rossum_api import APIClientError
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.engine import Engine
from rossum_api.models.queue import Queue
from rossum_api.models.schema import Schema
from rossum_mcp.tools import base
from rossum_mcp.tools.queues import (
    QueueListItem,
    _create_queue_from_template,
    _get_engine_url,
    _get_queue,
    _get_queue_engine,
    _list_queues,
    register_queue_tools,
)
from rossum_mcp.tools.resource_tracking import TRACKED_RESOURCES_KEY

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def create_mock_queue(**kwargs) -> Queue:
    """Create a mock Queue dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/queues/1",
        "name": "Test Queue",
        "workspace": "https://api.test.rossum.ai/v1/workspaces/1",
        "connector": None,
        "schema": "https://api.test.rossum.ai/v1/schemas/1",
        "inbox": "https://api.test.rossum.ai/v1/inboxes/1",
        "hooks": [],
        "users": [],
        "use_confirmed_state": True,
        "default_score_threshold": 0.8,
        "locale": "en_GB",
        "training_enabled": True,
        "automation_enabled": True,
        "automation_level": "never",
        "generic_engine": None,
        "dedicated_engine": None,
        "engine": "https://api.test.rossum.ai/v1/engines/1",
        "counts": {},
        "metadata": {},
        "settings": {},
        "status": "active",
        "document_lifetime": None,
        "delete_after": None,
    }
    defaults.update(kwargs)
    return Queue(**defaults)


def create_mock_schema(**kwargs) -> Schema:
    """Create a mock Schema dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/schemas/1",
        "name": "Test Schema",
        "queues": [],
        "content": [{"id": "section1", "label": "Section 1", "children": []}],
        "metadata": {},
        "modified_by": None,
        "modified_at": "2025-01-01T00:00:00Z",
    }
    defaults.update(kwargs)
    return Schema(**defaults)


def create_mock_engine(**kwargs) -> Engine:
    """Create a mock Engine dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/engines/1",
        "name": "Test Engine",
        "type": "extractor",
        "organization": "https://api.test.rossum.ai/v1/organizations/1",
        "learning_enabled": True,
        "training_queues": [],
        "description": "",
        "agenda_id": "test-agenda-id",
    }
    defaults.update(kwargs)
    return Engine(**defaults)


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
class TestGetQueue:
    """Tests for get_queue tool."""

    @pytest.mark.asyncio
    async def test_get_queue_success(self, mock_client: AsyncMock) -> None:
        """Test successful queue retrieval."""
        mock_queue = create_mock_queue(id=100, name="Production Queue")
        mock_client.retrieve_queue.return_value = mock_queue

        result = await _get_queue(mock_client, 100)

        assert result.id == 100
        assert result.name == "Production Queue"
        assert result.schema == mock_queue.schema
        assert result.workspace == mock_queue.workspace
        mock_client.retrieve_queue.assert_called_once_with(100)


@pytest.mark.unit
class TestListQueues:
    """Tests for list_queues tool."""

    @pytest.mark.asyncio
    async def test_list_queues_success(self, mock_client: AsyncMock) -> None:
        """Test successful queue listing."""
        mock_queues = [
            create_mock_queue(id=1, name="Queue 1"),
            create_mock_queue(id=2, name="Queue 2"),
        ]

        async def mock_fetch_all(resource, **filters):
            for queue in mock_queues:
                yield queue

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_queues(mock_client)

        assert len(result) == 2
        assert isinstance(result[0], QueueListItem)
        assert result[0].id == 1
        assert result[1].id == 2

    @pytest.mark.asyncio
    async def test_list_queues_with_workspace_filter(self, mock_client: AsyncMock) -> None:
        """Test queue listing with workspace filter."""
        mock_queues = [create_mock_queue(id=1, name="Queue 1")]
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            for queue in mock_queues:
                yield queue

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_queues(mock_client, workspace_id=5)

        assert len(result) == 1
        assert received_filters["workspace"] == 5

    @pytest.mark.asyncio
    async def test_list_queues_with_name_filter(self, mock_client: AsyncMock) -> None:
        """Test queue listing with name filter."""
        mock_queues = [create_mock_queue(id=1, name="Test Queue")]
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            for queue in mock_queues:
                yield queue

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_queues(mock_client, name="Test Queue")

        assert len(result) == 1
        assert received_filters["name"] == "Test Queue"

    @pytest.mark.asyncio
    async def test_list_queues_with_all_filters(self, mock_client: AsyncMock) -> None:
        """Test queue listing with all filters."""
        mock_queues = [create_mock_queue(id=1, name="Test Queue")]
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            for queue in mock_queues:
                yield queue

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_queues(mock_client, workspace_id=3, name="Test Queue")

        assert len(result) == 1
        assert received_filters["workspace"] == 3
        assert received_filters["name"] == "Test Queue"

    @pytest.mark.asyncio
    async def test_list_queues_empty_result(self, mock_client: AsyncMock) -> None:
        """Test queue listing with no results."""

        async def mock_fetch_all(resource, **filters):
            return
            yield

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_queues(mock_client)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_queues_omits_settings(self, mock_client: AsyncMock) -> None:
        """Test that settings are omitted in list response."""
        mock_queue = create_mock_queue(
            id=1,
            name="Queue 1",
            settings={
                "columns": [{"schema_id": "doc_id"}],
                "accepted_mime_types": ["image/*", "application/pdf", "application/zip"],
                "annotation_list_table": {"columns": [{"visible": True, "column_type": "meta"}]},
                "ui_upload_enabled": True,
            },
        )

        async def mock_fetch_all(resource, **filters):
            yield mock_queue

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_queues(mock_client)

        assert len(result) == 1
        assert isinstance(result[0], QueueListItem)
        assert result[0].settings == "<omitted>"

    @pytest.mark.asyncio
    async def test_list_queues_skips_broken_items(self, mock_client: AsyncMock) -> None:
        """Test list_queues gracefully skips items that fail deserialization."""
        mock_queue = create_mock_queue(id=1, name="Good Queue")

        def mock_deserializer(resource, raw):
            if raw.get("id") == 2:
                raise ValueError("broken queue")
            return mock_queue

        mock_client._deserializer = mock_deserializer

        async def mock_fetch_all(resource, **filters):
            yield {"id": 1, "name": "Good Queue"}
            yield {"id": 2, "name": "Broken Queue"}
            yield {"id": 3, "name": "Another Good Queue"}

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_queues(mock_client)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_queues_with_regex_name_filter(self, mock_client: AsyncMock) -> None:
        """Test that use_regex=True filters queues client-side by regex pattern."""
        mock_queues = [
            create_mock_queue(id=1, name="Invoice Queue"),
            create_mock_queue(id=2, name="Receipt Queue"),
            create_mock_queue(id=3, name="invoice_training"),
        ]
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            for queue in mock_queues:
                yield queue

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_queues(mock_client, name="invoice", use_regex=True)

        assert len(result) == 2
        assert result[0].name == "Invoice Queue"
        assert result[1].name == "invoice_training"
        assert "name" not in received_filters

    @pytest.mark.asyncio
    async def test_list_queues_with_regex_no_match(self, mock_client: AsyncMock) -> None:
        """Test that use_regex=True returns empty list when no queues match pattern."""
        mock_queues = [create_mock_queue(id=1, name="Receipt Queue")]

        async def mock_fetch_all(resource, **filters):
            for queue in mock_queues:
                yield queue

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_queues(mock_client, name="^invoice$", use_regex=True)

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_queues_with_regex_no_name_returns_all(self, mock_client: AsyncMock) -> None:
        """Test that use_regex=True without name returns all queues."""
        mock_queues = [create_mock_queue(id=1, name="Queue A"), create_mock_queue(id=2, name="Queue B")]

        async def mock_fetch_all(resource, **filters):
            for queue in mock_queues:
                yield queue

        mock_client._http_client.fetch_all = mock_fetch_all

        result = await _list_queues(mock_client, use_regex=True)

        assert len(result) == 2


@pytest.mark.unit
class TestGetQueueEngine:
    """Tests for get_queue_engine tool."""

    @pytest.mark.asyncio
    async def test_get_queue_engine_from_engine_field(self, mock_client: AsyncMock) -> None:
        """Test queue engine retrieval from engine field."""
        mock_queue = create_mock_queue(
            id=100,
            engine="https://api.test.rossum.ai/v1/engines/15",
            dedicated_engine=None,
            generic_engine=None,
        )
        mock_engine = create_mock_engine(id=15, name="Custom Engine")

        mock_client.retrieve_queue.return_value = mock_queue
        mock_client.retrieve_engine.return_value = mock_engine

        result = await _get_queue_engine(mock_client, 100)

        assert result.id == 15
        assert result.name == "Custom Engine"
        mock_client.retrieve_engine.assert_called_once_with(15)

    @pytest.mark.asyncio
    async def test_get_queue_engine_from_dedicated_engine(self, mock_client: AsyncMock) -> None:
        """Test queue engine retrieval prefers dedicated_engine."""
        mock_queue = create_mock_queue(
            id=100,
            engine="https://api.test.rossum.ai/v1/engines/10",
            dedicated_engine="https://api.test.rossum.ai/v1/engines/20",
            generic_engine=None,
        )
        mock_engine = create_mock_engine(id=20, name="Dedicated Engine")

        mock_client.retrieve_queue.return_value = mock_queue
        mock_client.retrieve_engine.return_value = mock_engine

        result = await _get_queue_engine(mock_client, 100)

        assert result.id == 20
        mock_client.retrieve_engine.assert_called_once_with(20)

    @pytest.mark.asyncio
    async def test_get_queue_engine_no_engine_assigned(self, mock_client: AsyncMock) -> None:
        """Test queue engine retrieval when no engine is assigned."""
        mock_queue = create_mock_queue(
            id=100,
            engine=None,
            dedicated_engine=None,
            generic_engine=None,
        )
        mock_client.retrieve_queue.return_value = mock_queue

        result = await _get_queue_engine(mock_client, 100)

        assert result["message"] == "No engine assigned to this queue"
        mock_client.retrieve_engine.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_queue_engine_engine_not_found(self, mock_client: AsyncMock) -> None:
        """Test queue engine retrieval when engine returns 404."""
        mock_queue = create_mock_queue(
            id=100,
            engine="https://api.test.rossum.ai/v1/engines/999",
            dedicated_engine=None,
            generic_engine=None,
        )
        mock_client.retrieve_queue.return_value = mock_queue
        mock_client.retrieve_engine.side_effect = APIClientError(
            method="GET",
            url="https://api.test.rossum.ai/v1/engines/999",
            status_code=404,
            error=Exception("Not found"),
        )

        result = await _get_queue_engine(mock_client, 100)

        assert "Engine not found" in result["message"]
        assert "engines/999" in result["message"]

    @pytest.mark.asyncio
    async def test_get_queue_engine_from_generic_engine(self, mock_client: AsyncMock) -> None:
        """Test queue engine retrieval from generic_engine field."""
        mock_queue = create_mock_queue(
            id=100,
            engine="https://api.test.rossum.ai/v1/engines/10",
            dedicated_engine=None,
            generic_engine="https://api.test.rossum.ai/v1/engines/30",
        )
        mock_engine = create_mock_engine(id=30, name="Generic Engine")

        mock_client.retrieve_queue.return_value = mock_queue
        mock_client.retrieve_engine.return_value = mock_engine

        result = await _get_queue_engine(mock_client, 100)

        assert result.id == 30
        assert result.name == "Generic Engine"
        mock_client.retrieve_engine.assert_called_once_with(30)

    @pytest.mark.asyncio
    async def test_get_queue_engine_dict_engine(self, mock_client: AsyncMock) -> None:
        """Test queue engine retrieval when engine_url is a dict (uses deserialize_default)."""
        engine_dict = {
            "id": 42,
            "url": "https://api.test.rossum.ai/v1/engines/42",
            "name": "Inline Engine",
            "type": "extractor",
        }
        mock_queue = create_mock_queue(
            id=100,
            engine=engine_dict,
            dedicated_engine=None,
            generic_engine=None,
        )
        mock_engine = create_mock_engine(id=42, name="Inline Engine")

        mock_client.retrieve_queue.return_value = mock_queue

        with patch("rossum_mcp.tools.queues.deserialize_default", return_value=mock_engine) as mock_deserialize:
            result = await _get_queue_engine(mock_client, 100)

            mock_deserialize.assert_called_once_with(Resource.Engine, engine_dict)
            assert result.id == 42
            assert result.name == "Inline Engine"
            mock_client.retrieve_engine.assert_not_called()


@pytest.mark.unit
class TestUpdateQueue:
    """Tests for update_queue tool."""

    @pytest.mark.asyncio
    async def test_update_queue_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful queue update."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=100, name="Updated Queue")
        mock_client._http_client.update.return_value = {"id": 100, "name": "Updated Queue"}
        mock_client._deserializer = Mock(return_value=mock_queue)

        update_queue = mock_mcp._tools["update_queue"]
        result = await update_queue(queue_id=100, queue_data={"name": "Updated Queue"})

        assert result.id == 100
        assert result.name == "Updated Queue"
        mock_client._http_client.update.assert_called_once_with(Resource.Queue, 100, {"name": "Updated Queue"})

    @pytest.mark.asyncio
    async def test_update_queue_rejects_invalid_meta_name(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        update_queue = mock_mcp._tools["update_queue"]
        result = await update_queue(
            queue_id=100,
            queue_data={
                "settings": {
                    "annotation_list_table": {
                        "columns": [
                            {"column_type": "meta", "meta_name": "created_by", "visible": True},
                        ]
                    }
                }
            },
        )

        assert "error" in result
        assert "created_by" in result["error"]
        assert "Invalid meta_name" in result["error"]
        mock_client._http_client.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_queue_allows_valid_meta_names(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=100, name="Test Queue")
        mock_client._http_client.update.return_value = {"id": 100}
        mock_client._deserializer = Mock(return_value=mock_queue)

        update_queue = mock_mcp._tools["update_queue"]
        result = await update_queue(
            queue_id=100,
            queue_data={
                "settings": {
                    "annotation_list_table": {
                        "columns": [
                            {"column_type": "meta", "meta_name": "created_at", "visible": True},
                            {"column_type": "meta", "meta_name": "modifier", "visible": True},
                        ]
                    }
                }
            },
        )

        assert result.id == 100
        mock_client._http_client.update.assert_called_once()


@pytest.mark.unit
class TestCreateQueueFromTemplate:
    """Tests for create_queue_from_template tool."""

    @pytest.mark.asyncio
    async def test_create_queue_from_template_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful queue creation from template."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=300, name="New Template Queue")
        mock_client._http_client.request_json.return_value = {"id": 300, "name": "New Template Queue"}
        mock_client._deserializer = Mock(return_value=mock_queue)

        create_queue_from_template = mock_mcp._tools["create_queue_from_template"]
        result = await create_queue_from_template(
            name="New Template Queue",
            template_name="EU Demo Template",
            workspace_id=1,
        )

        assert result.id == 300
        assert result.name == "New Template Queue"
        mock_client._http_client.request_json.assert_called_once()
        call_kwargs = mock_client._http_client.request_json.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["url"] == "queues/from_template"
        assert call_kwargs["json"]["name"] == "New Template Queue"
        assert call_kwargs["json"]["template_name"] == "EU Demo Template"
        assert call_kwargs["json"]["workspace"] == "https://api.test.rossum.ai/v1/workspaces/1"
        assert call_kwargs["json"]["include_documents"] is False

    @pytest.mark.asyncio
    async def test_create_queue_from_template_with_engine(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test queue creation from template with custom engine."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        mock_queue = create_mock_queue(id=300, name="New Template Queue")
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer = Mock(return_value=mock_queue)

        create_queue_from_template = mock_mcp._tools["create_queue_from_template"]
        await create_queue_from_template(
            name="New Template Queue",
            template_name="US Demo Template",
            workspace_id=1,
            engine_id=42,
        )

        call_kwargs = mock_client._http_client.request_json.call_args[1]
        assert call_kwargs["json"]["engine"] == "https://api.test.rossum.ai/v1/engines/42"

    @pytest.mark.asyncio
    async def test_create_queue_from_template_invalid_template(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test queue creation from template with invalid template name."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        register_queue_tools(mock_mcp, mock_client)

        create_queue_from_template = mock_mcp._tools["create_queue_from_template"]
        result = await create_queue_from_template(
            name="New Queue",
            template_name="Invalid Template",
            workspace_id=1,
        )

        assert "error" in result
        assert "Invalid template_name" in result["error"]
        assert "available_templates" in result
        mock_client._http_client.request_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_tracks_schema_and_engine(self, mock_client: AsyncMock, monkeypatch: MonkeyPatch) -> None:
        """Test that _create_queue_from_template tracks side-effect schema and engine."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        mock_queue = create_mock_queue(
            id=300,
            name="Template Queue",
            schema="https://api.test.rossum.ai/v1/schemas/50",
            engine="https://api.test.rossum.ai/v1/engines/60",
        )
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer = Mock(return_value=mock_queue)
        mock_client.retrieve_schema.return_value = create_mock_schema(id=50, name="Template Schema")
        mock_client.retrieve_engine.return_value = create_mock_engine(id=60, name="Template Engine")

        result = await _create_queue_from_template(mock_client, "Template Queue", "EU Demo Template", workspace_id=1)

        assert isinstance(result, dict)
        assert result["id"] == 300
        tracked = result[TRACKED_RESOURCES_KEY]
        assert len(tracked) == 2
        assert tracked[0]["entity_type"] == "schema"
        assert tracked[0]["entity_id"] == "50"
        assert tracked[0]["data"]["name"] == "Template Schema"
        assert tracked[1]["entity_type"] == "engine"
        assert tracked[1]["entity_id"] == "60"
        assert tracked[1]["data"]["name"] == "Template Engine"

    @pytest.mark.asyncio
    async def test_tracks_engine_even_when_engine_id_provided(
        self, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that engine is tracked even when engine_id is explicitly provided (pre-existing engine)."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        mock_queue = create_mock_queue(
            id=300,
            schema="https://api.test.rossum.ai/v1/schemas/50",
            engine="https://api.test.rossum.ai/v1/engines/42",
        )
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer = Mock(return_value=mock_queue)
        mock_client.retrieve_schema.return_value = create_mock_schema(id=50)
        mock_client.retrieve_engine.return_value = create_mock_engine(id=42, name="Existing Engine")

        result = await _create_queue_from_template(
            mock_client, "Template Queue", "EU Demo Template", workspace_id=1, engine_id=42
        )

        assert isinstance(result, dict)
        tracked = result[TRACKED_RESOURCES_KEY]
        engine_tracked = [t for t in tracked if t["entity_type"] == "engine"]
        assert len(engine_tracked) == 1
        assert engine_tracked[0]["entity_id"] == "42"

    @pytest.mark.asyncio
    async def test_schema_fetch_failure_is_logged_and_skipped(
        self, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that schema fetch failure doesn't break queue creation."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        mock_queue = create_mock_queue(
            id=300,
            schema="https://api.test.rossum.ai/v1/schemas/50",
            engine="https://api.test.rossum.ai/v1/engines/60",
        )
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer = Mock(return_value=mock_queue)
        mock_client.retrieve_schema.side_effect = Exception("Schema not found")
        mock_client.retrieve_engine.return_value = create_mock_engine(id=60, name="Template Engine")

        result = await _create_queue_from_template(mock_client, "Queue", "EU Demo Template", workspace_id=1)

        assert isinstance(result, dict)
        tracked = result[TRACKED_RESOURCES_KEY]
        assert len(tracked) == 1
        assert tracked[0]["entity_type"] == "engine"

    @pytest.mark.asyncio
    async def test_engine_fetch_failure_is_logged_and_skipped(
        self, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that engine fetch failure doesn't break queue creation."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        mock_queue = create_mock_queue(
            id=300,
            schema="https://api.test.rossum.ai/v1/schemas/50",
            engine="https://api.test.rossum.ai/v1/engines/60",
        )
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer = Mock(return_value=mock_queue)
        mock_client.retrieve_schema.return_value = create_mock_schema(id=50, name="Template Schema")
        mock_client.retrieve_engine.side_effect = Exception("Engine not found")

        result = await _create_queue_from_template(mock_client, "Queue", "EU Demo Template", workspace_id=1)

        assert isinstance(result, dict)
        tracked = result[TRACKED_RESOURCES_KEY]
        assert len(tracked) == 1
        assert tracked[0]["entity_type"] == "schema"

    @pytest.mark.asyncio
    async def test_both_fetches_fail_returns_queue_without_tracked(
        self, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """When both schema and engine fetch fail, result has empty tracked list."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        mock_queue = create_mock_queue(
            id=300,
            schema="https://api.test.rossum.ai/v1/schemas/50",
            engine="https://api.test.rossum.ai/v1/engines/60",
        )
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer = Mock(return_value=mock_queue)
        mock_client.retrieve_schema.side_effect = Exception("Schema fetch failed")
        mock_client.retrieve_engine.side_effect = Exception("Engine fetch failed")

        result = await _create_queue_from_template(mock_client, "Queue", "EU Demo Template", workspace_id=1)

        # No tracked resources → embed_tracked_resources returns the original Queue dataclass
        assert isinstance(result, Queue)
        assert result.id == 300

    @pytest.mark.asyncio
    async def test_queue_with_no_engine_only_tracks_schema(
        self, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that queue with no engine URL only tracks schema."""
        monkeypatch.setenv("ROSSUM_API_BASE_URL", "https://api.test.rossum.ai/v1")
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        mock_queue = create_mock_queue(
            id=300,
            schema="https://api.test.rossum.ai/v1/schemas/50",
            engine=None,
            dedicated_engine=None,
            generic_engine=None,
        )
        mock_client._http_client.request_json.return_value = {"id": 300}
        mock_client._deserializer = Mock(return_value=mock_queue)
        mock_client.retrieve_schema.return_value = create_mock_schema(id=50, name="Template Schema")

        result = await _create_queue_from_template(mock_client, "Queue", "EU Demo Template", workspace_id=1)

        assert isinstance(result, dict)
        tracked = result[TRACKED_RESOURCES_KEY]
        assert len(tracked) == 1
        assert tracked[0]["entity_type"] == "schema"
        mock_client.retrieve_engine.assert_not_called()


@pytest.mark.unit
class TestGetEngineUrl:
    """Tests for _get_engine_url helper."""

    def test_dedicated_engine_takes_priority(self) -> None:
        queue = create_mock_queue(
            dedicated_engine="https://api.test.rossum.ai/v1/engines/20",
            generic_engine="https://api.test.rossum.ai/v1/engines/30",
            engine="https://api.test.rossum.ai/v1/engines/10",
        )
        assert _get_engine_url(queue) == "https://api.test.rossum.ai/v1/engines/20"

    def test_generic_engine_fallback(self) -> None:
        queue = create_mock_queue(
            dedicated_engine=None,
            generic_engine="https://api.test.rossum.ai/v1/engines/30",
            engine="https://api.test.rossum.ai/v1/engines/10",
        )
        assert _get_engine_url(queue) == "https://api.test.rossum.ai/v1/engines/30"

    def test_engine_fallback(self) -> None:
        queue = create_mock_queue(
            dedicated_engine=None,
            generic_engine=None,
            engine="https://api.test.rossum.ai/v1/engines/10",
        )
        assert _get_engine_url(queue) == "https://api.test.rossum.ai/v1/engines/10"

    def test_all_none_returns_none(self) -> None:
        queue = create_mock_queue(
            dedicated_engine=None,
            generic_engine=None,
            engine=None,
        )
        assert _get_engine_url(queue) is None
