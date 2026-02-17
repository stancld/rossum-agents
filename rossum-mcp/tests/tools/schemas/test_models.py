"""Tests for schema dataclass models."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock  # noqa: TC003 - needed at runtime for fixtures

import pytest
from rossum_mcp.tools import base, schemas
from rossum_mcp.tools.schemas import (
    SchemaDatapoint,
    SchemaMultivalue,
    SchemaNodeUpdate,
    SchemaTuple,
)

from .conftest import create_mock_schema

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


@pytest.mark.unit
class TestSchemaDataclasses:
    """Tests for schema dataclass types."""

    def test_schema_datapoint_to_dict(self) -> None:
        """Test SchemaDatapoint converts to dict excluding None values."""
        datapoint = SchemaDatapoint(label="Invoice Number", type="string", score_threshold=0.8)
        result = datapoint.to_dict()

        assert result["label"] == "Invoice Number"
        assert result["type"] == "string"
        assert result["category"] == "datapoint"
        assert result["score_threshold"] == 0.8
        assert "rir_field_names" not in result
        assert "formula" not in result

    def test_schema_datapoint_with_formula(self) -> None:
        """Test SchemaDatapoint with formula field."""
        datapoint = SchemaDatapoint(label="Total", type="number", formula="field_a + field_b")
        result = datapoint.to_dict()

        assert result["formula"] == "field_a + field_b"
        assert result["type"] == "number"

    def test_schema_tuple_to_dict(self) -> None:
        """Test SchemaTuple converts to dict with nested children."""
        tuple_node = SchemaTuple(
            id="line_item",
            label="Line Item",
            children=[
                SchemaDatapoint(label="Description", type="string"),
                SchemaDatapoint(label="Amount", type="number"),
            ],
        )
        result = tuple_node.to_dict()

        assert result["id"] == "line_item"
        assert result["label"] == "Line Item"
        assert result["category"] == "tuple"
        assert len(result["children"]) == 2
        assert result["children"][0]["label"] == "Description"
        assert result["children"][1]["label"] == "Amount"

    def test_schema_multivalue_with_tuple(self) -> None:
        """Test SchemaMultivalue with tuple children (table structure)."""
        multivalue = SchemaMultivalue(
            label="Line Items",
            children=SchemaTuple(
                id="line_item",
                label="Line Item",
                children=[
                    SchemaDatapoint(label="Description", type="string"),
                    SchemaDatapoint(label="Amount", type="number"),
                ],
            ),
        )
        result = multivalue.to_dict()

        assert result["label"] == "Line Items"
        assert result["category"] == "multivalue"
        assert result["children"]["id"] == "line_item"
        assert result["children"]["label"] == "Line Item"
        assert result["children"]["category"] == "tuple"

    def test_schema_multivalue_with_datapoint(self) -> None:
        """Test SchemaMultivalue with single datapoint (repeating field)."""
        multivalue = SchemaMultivalue(
            label="PO Numbers",
            children=SchemaDatapoint(label="PO Number", type="string"),
        )
        result = multivalue.to_dict()

        assert result["label"] == "PO Numbers"
        assert result["category"] == "multivalue"
        assert result["children"]["label"] == "PO Number"
        assert result["children"]["category"] == "datapoint"

    def test_schema_node_update_to_dict(self) -> None:
        """Test SchemaNodeUpdate only includes set fields."""
        update = SchemaNodeUpdate(label="Updated Label", score_threshold=0.9)
        result = update.to_dict()

        assert result == {"label": "Updated Label", "score_threshold": 0.9}
        assert "type" not in result
        assert "hidden" not in result

    def test_schema_tuple_with_hidden_true(self) -> None:
        """Test SchemaTuple with hidden=True includes hidden field in output."""
        tuple_node = SchemaTuple(
            id="hidden_tuple",
            label="Hidden Tuple",
            children=[SchemaDatapoint(label="Field", type="string")],
            hidden=True,
        )
        result = tuple_node.to_dict()

        assert result["id"] == "hidden_tuple"
        assert result["hidden"] is True
        assert result["category"] == "tuple"

    def test_schema_multivalue_all_optional_fields(self) -> None:
        """Test SchemaMultivalue with all optional fields set."""
        multivalue = SchemaMultivalue(
            label="Line Items",
            children=SchemaDatapoint(label="Item", type="string"),
            id="line_items_mv",
            rir_field_names=["line_items"],
            min_occurrences=1,
            max_occurrences=10,
            hidden=True,
        )
        result = multivalue.to_dict()

        assert result["id"] == "line_items_mv"
        assert result["rir_field_names"] == ["line_items"]
        assert result["min_occurrences"] == 1
        assert result["max_occurrences"] == 10
        assert result["hidden"] is True
        assert result["category"] == "multivalue"

    def test_schema_node_update_with_stretch(self) -> None:
        """Test SchemaNodeUpdate with stretch field."""
        update = SchemaNodeUpdate(label="Column", width=100, stretch=True)
        result = update.to_dict()

        assert result["label"] == "Column"
        assert result["width"] == 100
        assert result["stretch"] is True

    @pytest.mark.asyncio
    async def test_patch_schema_with_dataclass(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test patch_schema accepts dataclass node_data."""
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
        mock_client._http_client.update.return_value = {}

        patch_schema = mock_mcp._tools["patch_schema"]
        result = await patch_schema(
            schema_id=50,
            operation="add",
            node_id="vendor_name",
            parent_id="header_section",
            node_data=SchemaDatapoint(label="Vendor Name", type="string"),
        )

        assert result["status"] == "success"
        assert result["schema_id"] == 50
        assert result["node"]["label"] == "Vendor Name"
        call_args = mock_client._http_client.update.call_args
        updated_content = call_args[1]["content"] if "content" in call_args[1] else call_args[0][2]["content"]
        header_section = updated_content[0]
        assert len(header_section["children"]) == 1
        assert header_section["children"][0]["id"] == "vendor_name"
        assert header_section["children"][0]["label"] == "Vendor Name"

    @pytest.mark.asyncio
    async def test_patch_schema_update_with_dataclass(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test patch_schema update operation with SchemaNodeUpdate dataclass."""
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
            operation="update",
            node_id="invoice_number",
            node_data=SchemaNodeUpdate(label="Invoice #", score_threshold=0.95),
        )

        assert result["status"] == "success"
        assert result["schema_id"] == 50
        assert result["node"]["label"] == "Invoice #"
        call_args = mock_client._http_client.update.call_args
        updated_content = call_args[1]["content"] if "content" in call_args[1] else call_args[0][2]["content"]
        datapoint = updated_content[0]["children"][0]
        assert datapoint["label"] == "Invoice #"
        assert datapoint["score_threshold"] == 0.95
