"""Tests for rossum_mcp.tools.document_relations module."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from rossum_api.models.document_relation import DocumentRelation


def create_mock_document_relation(**kwargs) -> DocumentRelation:
    """Create a mock DocumentRelation dataclass instance with default values."""
    defaults = {
        "id": 1,
        "url": "https://api.test.rossum.ai/v1/document_relations/1",
        "type": "export",
        "annotation": "https://api.test.rossum.ai/v1/annotations/100",
        "key": "export_key",
        "documents": [
            "https://api.test.rossum.ai/v1/documents/200",
            "https://api.test.rossum.ai/v1/documents/201",
        ],
    }
    defaults.update(kwargs)
    return DocumentRelation(**defaults)


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
class TestGetDocumentRelation:
    """Tests for get_document_relation tool."""

    @pytest.mark.asyncio
    async def test_get_document_relation_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful document relation retrieval."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        mock_doc_relation = create_mock_document_relation(id=100, type="export", key="exported_file_key")
        mock_client.retrieve_document_relation.return_value = mock_doc_relation

        get_document_relation = mock_mcp._tools["get_document_relation"]
        result = await get_document_relation(document_relation_id=100)

        assert result.id == 100
        assert result.type == "export"
        assert result.key == "exported_file_key"
        mock_client.retrieve_document_relation.assert_called_once_with(100)

    @pytest.mark.asyncio
    async def test_get_document_relation_einvoice_type(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test retrieving an einvoice-type document relation."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        mock_doc_relation = create_mock_document_relation(id=200, type="einvoice", key=None)
        mock_client.retrieve_document_relation.return_value = mock_doc_relation

        get_document_relation = mock_mcp._tools["get_document_relation"]
        result = await get_document_relation(document_relation_id=200)

        assert result.id == 200
        assert result.type == "einvoice"
        assert result.key is None


@pytest.mark.unit
class TestListDocumentRelations:
    """Tests for list_document_relations tool."""

    @pytest.mark.asyncio
    async def test_list_document_relations_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful document relations listing."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        mock_dr1 = create_mock_document_relation(id=1, type="export")
        mock_dr2 = create_mock_document_relation(id=2, type="einvoice")

        async def mock_fetch_all(resource, **filters):
            for item in [mock_dr1, mock_dr2]:
                yield item

        mock_client._http_client.fetch_all = mock_fetch_all

        list_document_relations = mock_mcp._tools["list_document_relations"]
        result = await list_document_relations()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_document_relations_with_type_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test document relations listing filtered by type."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        mock_dr = create_mock_document_relation(id=1, type="export")
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            yield mock_dr

        mock_client._http_client.fetch_all = mock_fetch_all

        list_document_relations = mock_mcp._tools["list_document_relations"]
        result = await list_document_relations(type="export")

        assert len(result) == 1
        assert received_filters["type"] == "export"

    @pytest.mark.asyncio
    async def test_list_document_relations_with_annotation_filter(
        self, mock_mcp: Mock, mock_client: AsyncMock
    ) -> None:
        """Test document relations listing filtered by annotation."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        mock_dr = create_mock_document_relation(id=1)
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            yield mock_dr

        mock_client._http_client.fetch_all = mock_fetch_all

        list_document_relations = mock_mcp._tools["list_document_relations"]
        result = await list_document_relations(annotation=500)

        assert len(result) == 1
        assert received_filters["annotation"] == 500

    @pytest.mark.asyncio
    async def test_list_document_relations_with_documents_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test document relations listing filtered by documents."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        mock_dr = create_mock_document_relation(id=1)
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            yield mock_dr

        mock_client._http_client.fetch_all = mock_fetch_all

        list_document_relations = mock_mcp._tools["list_document_relations"]
        result = await list_document_relations(documents=700)

        assert len(result) == 1
        assert received_filters["documents"] == 700

    @pytest.mark.asyncio
    async def test_list_document_relations_with_key_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test document relations listing filtered by key."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        mock_dr = create_mock_document_relation(id=1, key="specific_key")
        received_filters: dict = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal received_filters
            received_filters = filters
            yield mock_dr

        mock_client._http_client.fetch_all = mock_fetch_all

        list_document_relations = mock_mcp._tools["list_document_relations"]
        result = await list_document_relations(key="specific_key")

        assert len(result) == 1
        assert received_filters["key"] == "specific_key"

    @pytest.mark.asyncio
    async def test_list_document_relations_empty(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test document relations listing when none exist."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        async def mock_fetch_all(resource, **filters):
            return
            yield

        mock_client._http_client.fetch_all = mock_fetch_all

        list_document_relations = mock_mcp._tools["list_document_relations"]
        result = await list_document_relations()

        assert len(result) == 0
        assert result == []

    @pytest.mark.asyncio
    async def test_list_document_relations_skips_broken_items(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test list_document_relations gracefully skips items that fail deserialization."""
        from rossum_mcp.tools.document_relations import register_document_relation_tools

        register_document_relation_tools(mock_mcp, mock_client)

        mock_dr = create_mock_document_relation(id=1, type="export")

        def mock_deserializer(resource, raw):
            if raw.get("id") == 2:
                raise ValueError("broken document relation")
            return mock_dr

        mock_client._deserializer = mock_deserializer

        async def mock_fetch_all(resource, **filters):
            yield {"id": 1, "type": "export"}
            yield {"id": 2, "type": "broken"}
            yield {"id": 3, "type": "einvoice"}

        mock_client._http_client.fetch_all = mock_fetch_all

        list_document_relations = mock_mcp._tools["list_document_relations"]
        result = await list_document_relations()

        assert len(result) == 2
