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
from rossum_mcp.tools import base
from rossum_mcp.tools.queues import (
    QueueListItem,
    _get_engine_url,
    _get_queue,
    _get_queue_engine,
    _list_queues,
    register_queue_tools,
)

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
