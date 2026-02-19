"""Tests for schema CRUD operations."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rossum_api import APIClientError
from rossum_mcp.tools import base, schemas
from rossum_mcp.tools.schemas import register_schema_tools
from rossum_mcp.tools.schemas.models import SchemaListItem

from .conftest import create_mock_schema

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


@pytest.mark.unit
class TestGetSchema:
    """Tests for get_schema tool."""

    @pytest.mark.asyncio
    async def test_get_schema_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful schema retrieval."""
        register_schema_tools(mock_mcp, mock_client)

        mock_schema = create_mock_schema(
            id=50,
            name="Invoice Schema",
            content=[
                {
                    "id": "header_section",
                    "label": "Header",
                    "children": [{"id": "invoice_number", "label": "Invoice Number"}],
                }
            ],
        )
        mock_client.retrieve_schema.return_value = mock_schema

        get_schema = mock_mcp._tools["get_schema"]
        result = await get_schema(schema_id=50)

        assert result.id == 50
        assert result.name == "Invoice Schema"
        assert len(result.content) == 1
        mock_client.retrieve_schema.assert_called_once_with(50)

    @pytest.mark.asyncio
    async def test_get_schema_not_found(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test schema not found returns error dict instead of raising exception."""
        register_schema_tools(mock_mcp, mock_client)

        mock_client.retrieve_schema.side_effect = APIClientError(
            method="GET",
            url="https://api.test/schemas/999",
            status_code=404,
            error=Exception("Not found"),
        )

        get_schema = mock_mcp._tools["get_schema"]
        result = await get_schema(schema_id=999)

        assert isinstance(result, dict)
        assert "error" in result
        assert "999" in result["error"]
        assert "not found" in result["error"]


@pytest.mark.unit
class TestListSchemas:
    """Tests for list_schemas tool."""

    @pytest.mark.asyncio
    async def test_list_schemas_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful schema listing."""
        register_schema_tools(mock_mcp, mock_client)

        mock_schemas = [
            create_mock_schema(id=1, name="Schema 1"),
            create_mock_schema(id=2, name="Schema 2"),
        ]

        async def mock_fetch_all(resource, **filters):
            for schema in mock_schemas:
                yield schema

        mock_client._http_client.fetch_all = mock_fetch_all

        list_schemas = mock_mcp._tools["list_schemas"]
        result = await list_schemas()

        assert len(result) == 2
        assert result[0].id == 1
        assert result[1].id == 2

    @pytest.mark.asyncio
    async def test_list_schemas_with_name_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test schema listing with name filter."""
        register_schema_tools(mock_mcp, mock_client)

        mock_schemas = [create_mock_schema(id=1, name="Invoice Schema")]
        filters_received = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal filters_received
            filters_received = filters
            for schema in mock_schemas:
                yield schema

        mock_client._http_client.fetch_all = mock_fetch_all

        list_schemas = mock_mcp._tools["list_schemas"]
        result = await list_schemas(name="Invoice Schema")

        assert len(result) == 1
        assert filters_received["name"] == "Invoice Schema"

    @pytest.mark.asyncio
    async def test_list_schemas_with_queue_filter(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test schema listing with queue filter."""
        register_schema_tools(mock_mcp, mock_client)

        mock_schemas = [create_mock_schema(id=1, name="Schema 1")]
        filters_received = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal filters_received
            filters_received = filters
            for schema in mock_schemas:
                yield schema

        mock_client._http_client.fetch_all = mock_fetch_all

        list_schemas = mock_mcp._tools["list_schemas"]
        result = await list_schemas(queue_id=5)

        assert len(result) == 1
        assert filters_received["queue"] == 5

    @pytest.mark.asyncio
    async def test_list_schemas_with_all_filters(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test schema listing with all filters."""
        register_schema_tools(mock_mcp, mock_client)

        mock_schemas = [create_mock_schema(id=1, name="Test Schema")]
        filters_received = {}

        async def mock_fetch_all(resource, **filters):
            nonlocal filters_received
            filters_received = filters
            for schema in mock_schemas:
                yield schema

        mock_client._http_client.fetch_all = mock_fetch_all

        list_schemas = mock_mcp._tools["list_schemas"]
        result = await list_schemas(name="Test Schema", queue_id=3)

        assert len(result) == 1
        assert filters_received["name"] == "Test Schema"
        assert filters_received["queue"] == 3

    @pytest.mark.asyncio
    async def test_list_schemas_empty_result(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test schema listing with no results."""
        register_schema_tools(mock_mcp, mock_client)

        async def mock_fetch_all(resource, **filters):
            return
            yield

        mock_client._http_client.fetch_all = mock_fetch_all

        list_schemas = mock_mcp._tools["list_schemas"]
        result = await list_schemas()

        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_schemas_truncates_content(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test that content field is truncated in list response."""
        register_schema_tools(mock_mcp, mock_client)

        mock_schema = create_mock_schema(
            id=1,
            name="Schema 1",
            content=[
                {
                    "id": "header_section",
                    "label": "Header",
                    "children": [{"id": "invoice_number", "label": "Invoice Number"}],
                }
            ],
        )

        async def mock_fetch_all(resource, **filters):
            yield mock_schema

        mock_client._http_client.fetch_all = mock_fetch_all

        list_schemas = mock_mcp._tools["list_schemas"]
        result = await list_schemas()

        assert len(result) == 1
        item = result[0]
        assert isinstance(item, SchemaListItem)
        assert item.content == "<omitted>"
        assert item.name == "Schema 1"
        assert item.id == 1

    @pytest.mark.asyncio
    async def test_list_schemas_skips_broken_items(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test list_schemas gracefully skips items that fail deserialization."""
        register_schema_tools(mock_mcp, mock_client)

        good_schema = create_mock_schema(id=1, name="Good Schema")

        def mock_deserializer(resource, raw):
            if raw.get("id") == 2:
                raise ValueError("broken schema")
            return good_schema

        mock_client._deserializer = mock_deserializer

        async def mock_fetch_all(resource, **filters):
            yield {"id": 1, "name": "Good Schema"}
            yield {"id": 2, "name": "Broken Schema"}
            yield {"id": 3, "name": "Another Good Schema"}

        mock_client._http_client.fetch_all = mock_fetch_all

        list_schemas = mock_mcp._tools["list_schemas"]
        result = await list_schemas()

        assert len(result) == 2


@pytest.mark.unit
class TestUpdateSchema:
    """Tests for update_schema tool."""

    @pytest.mark.asyncio
    async def test_update_schema_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful schema update."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        register_schema_tools(mock_mcp, mock_client)

        updated_schema = create_mock_schema(id=50, name="Updated Schema")
        mock_client._http_client.update.return_value = {"id": 50}
        mock_client.retrieve_schema.return_value = updated_schema

        update_schema = mock_mcp._tools["update_schema"]
        result = await update_schema(schema_id=50, schema_data={"name": "Updated Schema"})

        assert result.id == 50
        assert result.name == "Updated Schema"

    @pytest.mark.asyncio
    async def test_update_schema_allows_empty_content(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        register_schema_tools(mock_mcp, mock_client)

        updated_schema = create_mock_schema(id=50, name="Empty Schema", content=[])
        mock_client._http_client.update.return_value = {"id": 50}
        mock_client.retrieve_schema.return_value = updated_schema

        update_schema = mock_mcp._tools["update_schema"]
        result = await update_schema(schema_id=50, schema_data={"content": []})

        assert result.id == 50
        mock_client._http_client.update.assert_called_once()


@pytest.mark.unit
class TestCreateSchema:
    """Tests for create_schema tool."""

    @pytest.mark.asyncio
    async def test_create_schema_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful schema creation."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        register_schema_tools(mock_mcp, mock_client)

        content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [{"id": "invoice_number", "label": "Invoice Number", "type": "string"}],
            }
        ]

        new_schema = create_mock_schema(id=100, name="New Schema", content=content)
        mock_client.create_new_schema.return_value = new_schema

        create_schema = mock_mcp._tools["create_schema"]
        result = await create_schema(name="New Schema", content=content)

        assert result.id == 100
        assert result.name == "New Schema"
        mock_client.create_new_schema.assert_called_once_with({"name": "New Schema", "content": content})

    @pytest.mark.asyncio
    async def test_create_schema_rejects_empty_content(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)

        register_schema_tools(mock_mcp, mock_client)

        create_schema = mock_mcp._tools["create_schema"]
        result = await create_schema(name="New Schema", content=[])

        assert isinstance(result, dict)
        assert "empty content" in result["error"]
        mock_client.create_new_schema.assert_not_called()


@pytest.mark.unit
class TestPatchSchema:
    """Tests for patch_schema tool."""

    @pytest.mark.asyncio
    async def test_patch_schema_add_datapoint(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test adding a datapoint to a section."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        existing_content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [{"id": "invoice_number", "label": "Invoice Number", "category": "datapoint"}],
            }
        ]

        mock_schema = create_mock_schema(id=50, content=existing_content)
        mock_client.retrieve_schema.return_value = mock_schema
        mock_client._http_client.request_json.return_value = {"content": existing_content}
        mock_client._http_client.update.return_value = {}

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="add",
            node_id="vendor_name",
            parent_id="header_section",
            node_data={"label": "Vendor Name", "type": "string", "category": "datapoint"},
        )

        assert result["status"] == "success"
        assert result["schema_id"] == 50
        assert result["node_id"] == "vendor_name"
        assert result["node"]["label"] == "Vendor Name"
        mock_client._http_client.update.assert_called_once()
        call_args = mock_client._http_client.update.call_args
        updated_content = call_args[1]["content"] if "content" in call_args[1] else call_args[0][2]["content"]
        header_section = updated_content[0]
        assert len(header_section["children"]) == 2
        assert header_section["children"][1]["id"] == "vendor_name"

    @pytest.mark.asyncio
    async def test_patch_schema_update_datapoint(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test updating properties of an existing datapoint."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        existing_content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [
                    {
                        "id": "invoice_number",
                        "label": "Invoice Number",
                        "category": "datapoint",
                        "score_threshold": 0.5,
                    }
                ],
            }
        ]

        mock_schema = create_mock_schema(id=50, content=existing_content)
        mock_client.retrieve_schema.return_value = mock_schema
        mock_client._http_client.request_json.return_value = {"content": existing_content}
        mock_client._http_client.update.return_value = {}

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="update",
            node_id="invoice_number",
            node_data={"label": "Invoice #", "score_threshold": 0.9},
        )

        assert result["status"] == "success"
        assert result["schema_id"] == 50
        assert result["node"]["label"] == "Invoice #"
        call_args = mock_client._http_client.update.call_args
        updated_content = call_args[1]["content"] if "content" in call_args[1] else call_args[0][2]["content"]
        datapoint = updated_content[0]["children"][0]
        assert datapoint["label"] == "Invoice #"
        assert datapoint["score_threshold"] == 0.9

    @pytest.mark.asyncio
    async def test_patch_schema_remove_datapoint(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test removing a datapoint from a section."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        existing_content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [
                    {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint"},
                    {"id": "old_field", "label": "Old Field", "category": "datapoint"},
                ],
            }
        ]

        mock_schema = create_mock_schema(id=50, content=existing_content)
        mock_client.retrieve_schema.return_value = mock_schema
        mock_client._http_client.request_json.return_value = {"content": existing_content}
        mock_client._http_client.update.return_value = {}

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="remove",
            node_id="old_field",
        )

        assert result["status"] == "success"
        assert result["schema_id"] == 50
        assert result["node"] is None
        call_args = mock_client._http_client.update.call_args
        updated_content = call_args[1]["content"] if "content" in call_args[1] else call_args[0][2]["content"]
        header_section = updated_content[0]
        assert len(header_section["children"]) == 1
        assert header_section["children"][0]["id"] == "invoice_number"

    @pytest.mark.asyncio
    async def test_patch_schema_retries_on_412(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that patch_schema retries on 412 Precondition Failed."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        existing_content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [{"id": "invoice_number", "label": "Invoice Number", "category": "datapoint"}],
            }
        ]

        mock_schema = create_mock_schema(id=50, content=existing_content)
        mock_client.retrieve_schema.return_value = mock_schema
        mock_client._http_client.request_json.return_value = {"content": existing_content}
        mock_client._http_client.update.side_effect = [
            APIClientError("PATCH", "schemas/50", 412, "Precondition Failed"),
            {},
        ]

        patch_schema = mock_mcp._tools["patch_schema"]
        with patch("rossum_mcp.tools.schemas.operations.asyncio.sleep", new_callable=AsyncMock):
            result = await patch_schema(
                schema_id=50,
                operation="add",
                node_id="vendor_name",
                parent_id="header_section",
                node_data={"label": "Vendor Name", "type": "string", "category": "datapoint"},
            )

        assert result["status"] == "success"
        assert result["schema_id"] == 50
        assert mock_client._http_client.update.call_count == 2
        assert mock_client._http_client.request_json.call_count == 2

    @pytest.mark.asyncio
    async def test_patch_schema_raises_after_max_retries_on_412(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that patch_schema raises after exhausting retries on 412."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        existing_content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [{"id": "invoice_number", "label": "Invoice Number", "category": "datapoint"}],
            }
        ]

        mock_client._http_client.request_json.return_value = {"content": existing_content}
        mock_client._http_client.update.side_effect = APIClientError("PATCH", "schemas/50", 412, "Precondition Failed")

        patch_schema = mock_mcp._tools["patch_schema"]
        with patch("rossum_mcp.tools.schemas.operations.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(APIClientError, match="412"):
                await patch_schema(
                    schema_id=50,
                    operation="add",
                    node_id="vendor_name",
                    parent_id="header_section",
                    node_data={"label": "Vendor Name", "type": "string", "category": "datapoint"},
                )

    @pytest.mark.asyncio
    async def test_patch_schema_invalid_operation(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that invalid operation returns error."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="invalid",
            node_id="some_field",
        )

        assert result["error"] == "Invalid operation 'invalid'. Must be 'add', 'update', or 'remove'."

    @pytest.mark.asyncio
    async def test_patch_schema_unexpected_content_format(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test patch_schema when schema content is not a list."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_client._http_client.request_json.return_value = {"content": "not_a_list"}

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="add",
            node_id="new_field",
            parent_id="section1",
            node_data={"label": "New Field"},
        )

        assert result["error"] == "Unexpected schema content format"
        mock_client._http_client.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_patch_schema_node_not_found(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that updating a non-existent node returns error."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        existing_content = [
            {
                "id": "header_section",
                "label": "Header",
                "category": "section",
                "children": [],
            }
        ]

        mock_schema = create_mock_schema(id=50, content=existing_content)
        mock_client.retrieve_schema.return_value = mock_schema
        mock_client._http_client.request_json.return_value = {"content": existing_content}

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="update",
            node_id="nonexistent_field",
            node_data={"label": "Updated Label"},
        )

        assert "not found" in result["error"]


@pytest.mark.unit
class TestGetSchemaTreeStructure:
    """Tests for get_schema_tree_structure tool."""

    @pytest.mark.asyncio
    async def test_get_schema_tree_structure_success(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test successful tree structure extraction."""
        register_schema_tools(mock_mcp, mock_client)

        mock_schema = create_mock_schema(
            id=50,
            content=[
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint", "type": "string"},
                        {"id": "invoice_date", "label": "Invoice Date", "category": "datapoint", "type": "date"},
                    ],
                },
                {
                    "id": "line_items_section",
                    "label": "Line Items",
                    "category": "section",
                    "children": [
                        {
                            "id": "line_items",
                            "label": "Line Items",
                            "category": "multivalue",
                            "children": {
                                "id": "line_item",
                                "label": "Line Item",
                                "category": "tuple",
                                "children": [
                                    {
                                        "id": "description",
                                        "label": "Description",
                                        "category": "datapoint",
                                        "type": "string",
                                    },
                                    {"id": "amount", "label": "Amount", "category": "datapoint", "type": "number"},
                                ],
                            },
                        }
                    ],
                },
            ],
        )
        mock_client.retrieve_schema.return_value = mock_schema

        get_schema_tree_structure = mock_mcp._tools["get_schema_tree_structure"]
        result = await get_schema_tree_structure(schema_id=50)

        assert len(result) == 2
        assert result[0]["id"] == "header_section"
        assert result[0]["label"] == "Header"
        assert len(result[0]["children"]) == 2
        assert result[0]["children"][0]["id"] == "invoice_number"
        assert result[0]["children"][0]["type"] == "string"
        assert result[1]["children"][0]["id"] == "line_items"
        assert result[1]["children"][0]["children"][0]["id"] == "line_item"

    @pytest.mark.asyncio
    async def test_get_schema_tree_structure_not_found(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test tree structure returns error dict when schema not found."""
        register_schema_tools(mock_mcp, mock_client)

        mock_client.retrieve_schema.side_effect = APIClientError(
            method="GET",
            url="https://api.test/schemas/999",
            status_code=404,
            error=Exception("Not found"),
        )

        get_schema_tree_structure = mock_mcp._tools["get_schema_tree_structure"]
        result = await get_schema_tree_structure(schema_id=999)

        assert isinstance(result, dict)
        assert "error" in result
        assert "999" in result["error"]
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_get_schema_tree_structure_by_queue_id(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test tree structure via queue_id resolves schema automatically."""
        register_schema_tools(mock_mcp, mock_client)

        mock_queue = Mock()
        mock_queue.schema = "https://api.test/v1/schemas/50"
        mock_client.retrieve_queue.return_value = mock_queue

        mock_schema = create_mock_schema(
            id=50,
            content=[
                {
                    "id": "section",
                    "label": "Section",
                    "category": "section",
                    "children": [{"id": "field1", "label": "Field 1", "category": "datapoint", "type": "string"}],
                }
            ],
        )
        mock_client.retrieve_schema.return_value = mock_schema

        get_schema_tree_structure = mock_mcp._tools["get_schema_tree_structure"]
        result = await get_schema_tree_structure(queue_id=100)

        mock_client.retrieve_queue.assert_called_once_with(100)
        mock_client.retrieve_schema.assert_called_once_with(50)
        assert len(result) == 1
        assert result[0]["id"] == "section"

    @pytest.mark.asyncio
    async def test_get_schema_tree_structure_no_args(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test tree structure returns error when neither schema_id nor queue_id provided."""
        register_schema_tools(mock_mcp, mock_client)

        get_schema_tree_structure = mock_mcp._tools["get_schema_tree_structure"]
        result = await get_schema_tree_structure()

        assert isinstance(result, dict)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_schema_tree_structure_both_args(self, mock_mcp: Mock, mock_client: AsyncMock) -> None:
        """Test tree structure returns error when both schema_id and queue_id provided."""
        register_schema_tools(mock_mcp, mock_client)

        get_schema_tree_structure = mock_mcp._tools["get_schema_tree_structure"]
        result = await get_schema_tree_structure(schema_id=50, queue_id=100)

        assert isinstance(result, dict)
        assert "error" in result


@pytest.mark.unit
class TestDeleteSchema:
    """Tests for delete_schema tool."""

    @pytest.mark.asyncio
    async def test_delete_schema_success(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test successful schema deletion."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_client.delete_schema.return_value = None

        delete_schema = mock_mcp._tools["delete_schema"]
        result = await delete_schema(schema_id=50)

        assert "deleted successfully" in result["message"]
        assert "50" in result["message"]
        mock_client.delete_schema.assert_called_once_with(50)
