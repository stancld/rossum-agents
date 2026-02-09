"""Tests for schema pruning functions."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rossum_api import APIClientError
from rossum_mcp.tools import base, schemas
from rossum_mcp.tools.schemas.pruning import (
    _collect_all_field_ids,
    _remove_fields_from_content,
)

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


@pytest.mark.unit
class TestFieldPruning:
    """Tests for field collection and pruning functions."""

    def test_collect_all_field_ids_with_dict_children(self) -> None:
        """Test _collect_all_field_ids traverses dict children (multivalue case)."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "multivalue1",
                        "category": "multivalue",
                        "children": {
                            "id": "tuple1",
                            "category": "tuple",
                            "children": [
                                {"id": "field1", "category": "datapoint"},
                                {"id": "field2", "category": "datapoint"},
                            ],
                        },
                    }
                ],
            }
        ]

        result = _collect_all_field_ids(content)

        assert result == {"section1", "multivalue1", "tuple1", "field1", "field2"}

    def test_remove_fields_from_nested_list_children(self) -> None:
        """Test _remove_fields_from_content removes field from nested list children."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "parent1",
                        "category": "tuple",
                        "children": [
                            {"id": "keep_field", "category": "datapoint"},
                            {"id": "remove_field", "category": "datapoint"},
                        ],
                    }
                ],
            }
        ]

        result, removed = _remove_fields_from_content(content, {"remove_field"})

        assert removed == ["remove_field"]
        parent_children = result[0]["children"][0]["children"]
        assert len(parent_children) == 1
        assert parent_children[0]["id"] == "keep_field"

    def test_remove_fields_from_dict_children_inner_tuple(self) -> None:
        """Test _remove_fields_from_content removes entire multivalue when tuple is removed."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "multivalue1",
                        "category": "multivalue",
                        "children": {
                            "id": "tuple1",
                            "category": "tuple",
                            "children": [
                                {"id": "keep_me", "category": "datapoint"},
                                {"id": "remove_me", "category": "datapoint"},
                            ],
                        },
                    }
                ],
            }
        ]

        result, removed = _remove_fields_from_content(content, {"tuple1"})

        assert "tuple1" in removed
        assert "multivalue1" in removed
        assert "section1" in removed
        assert result == []

    def test_remove_fields_filters_inside_dict_children_nested(self) -> None:
        """Test _remove_fields_from_content filters children inside dict children's nested list."""
        content = [
            {
                "id": "section1",
                "category": "section",
                "children": [
                    {
                        "id": "multivalue1",
                        "category": "multivalue",
                        "children": {
                            "id": "tuple1",
                            "category": "tuple",
                            "children": [
                                {"id": "desc", "category": "datapoint"},
                                {"id": "amount", "category": "datapoint"},
                                {"id": "unit_price", "category": "datapoint"},
                            ],
                        },
                    }
                ],
            }
        ]

        result, removed = _remove_fields_from_content(content, {"amount", "unit_price"})

        assert sorted(removed) == ["amount", "unit_price"]
        tuple_children = result[0]["children"][0]["children"]["children"]
        assert len(tuple_children) == 1
        assert tuple_children[0]["id"] == "desc"


@pytest.mark.unit
class TestPruneSchemaFields:
    """Tests for prune_schema_fields tool."""

    @pytest.mark.asyncio
    async def test_prune_schema_fields_with_fields_to_keep(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test pruning with fields_to_keep."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_schema_dict = {
            "id": 50,
            "content": [
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint", "type": "string"},
                        {"id": "invoice_date", "label": "Invoice Date", "category": "datapoint", "type": "date"},
                        {"id": "vendor_name", "label": "Vendor Name", "category": "datapoint", "type": "string"},
                    ],
                }
            ],
        }
        mock_client._http_client.request_json.return_value = mock_schema_dict
        mock_client._http_client.update.return_value = {}

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_keep=["invoice_number"])

        assert "invoice_date" in result["removed_fields"]
        assert "vendor_name" in result["removed_fields"]
        assert "invoice_number" in result["remaining_fields"]
        assert "header_section" in result["remaining_fields"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_with_fields_to_remove(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test pruning with fields_to_remove."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_schema_dict = {
            "id": 50,
            "content": [
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint", "type": "string"},
                        {"id": "invoice_date", "label": "Invoice Date", "category": "datapoint", "type": "date"},
                    ],
                }
            ],
        }
        mock_client._http_client.request_json.return_value = mock_schema_dict
        mock_client._http_client.update.return_value = {}

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_remove=["invoice_date"])

        assert "invoice_date" in result["removed_fields"]
        assert "invoice_number" in result["remaining_fields"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_read_only_mode(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test pruning in read-only mode returns error."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-only")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_keep=["invoice_number"])

        assert "error" in result
        assert "read-only" in result["error"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_both_params_error(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test error when both fields_to_keep and fields_to_remove provided."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_keep=["a"], fields_to_remove=["b"])

        assert "error" in result
        assert "not both" in result["error"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_no_params_error(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test error when neither parameter provided."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50)

        assert "error" in result
        assert "Must specify" in result["error"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_preserves_parent_containers_for_nested_fields(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that keeping a nested field preserves its parent containers (multivalue, section)."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_schema_dict = {
            "id": 50,
            "content": [
                {
                    "id": "197466",
                    "category": "section",
                    "schema_id": "invoice_info_section",
                    "children": [
                        {
                            "id": "197467",
                            "category": "datapoint",
                            "schema_id": "invoice_number",
                            "type": "string",
                        },
                        {
                            "id": "197468",
                            "category": "datapoint",
                            "schema_id": "date_due",
                            "type": "date",
                        },
                        {
                            "id": "197469",
                            "category": "datapoint",
                            "schema_id": "amount_due",
                            "type": "number",
                        },
                    ],
                },
                {
                    "id": "197500",
                    "category": "section",
                    "schema_id": "line_items_section",
                    "children": [
                        {
                            "id": "197501",
                            "category": "multivalue",
                            "schema_id": "line_items",
                            "children": [
                                {
                                    "id": "198139",
                                    "category": "tuple",
                                    "schema_id": "line_item",
                                    "children": [
                                        {
                                            "id": "198140",
                                            "category": "datapoint",
                                            "schema_id": "item_desc",
                                            "type": "string",
                                        },
                                        {
                                            "id": "198142",
                                            "category": "datapoint",
                                            "schema_id": "item_net_unit_price",
                                            "type": "number",
                                        },
                                    ],
                                }
                            ],
                        }
                    ],
                },
            ],
        }
        mock_client._http_client.request_json.return_value = mock_schema_dict
        mock_client._http_client.update.return_value = {}

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_keep=["198140"])

        assert "197501" in result["remaining_fields"]
        assert "197500" in result["remaining_fields"]
        assert "198139" in result["remaining_fields"]
        assert "198140" in result["remaining_fields"]

        assert "198142" in result["removed_fields"]
        assert "197467" in result["removed_fields"]
        assert "197468" in result["removed_fields"]
        assert "197469" in result["removed_fields"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_all_fields_kept(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test prune when fields_to_keep matches all fields so remove_set is empty."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_schema_dict = {
            "id": 50,
            "content": [
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint", "type": "string"}
                    ],
                }
            ],
        }
        mock_client._http_client.request_json.return_value = mock_schema_dict

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_keep=["header_section", "invoice_number"])

        assert result["removed_fields"] == []
        assert sorted(result["remaining_fields"]) == ["header_section", "invoice_number"]
        mock_client._http_client.update.assert_not_called()

    def _setup_multivalue_schema(
        self,
        mock_mcp: Mock,
        mock_client: AsyncMock,
        monkeypatch: MonkeyPatch,
        tuple_children: list[dict],
    ) -> None:
        """Set up read-write mode and configure mock with a multivalue schema."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)
        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_schema_dict = {
            "id": 50,
            "content": [
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint", "type": "string"},
                        {
                            "id": "line_items",
                            "label": "Line Items",
                            "category": "multivalue",
                            "children": {
                                "id": "line_item",
                                "label": "Line Item",
                                "category": "tuple",
                                "children": tuple_children,
                            },
                        },
                    ],
                }
            ],
        }
        mock_client._http_client.request_json.return_value = mock_schema_dict
        mock_client._http_client.update.return_value = {}

    @pytest.mark.asyncio
    async def test_prune_schema_fields_removes_multivalue_when_tuple_removed(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that removing tuple also removes parent multivalue (no stub left)."""
        self._setup_multivalue_schema(
            mock_mcp,
            mock_client,
            monkeypatch,
            tuple_children=[{"id": "item_desc", "label": "Description", "category": "datapoint", "type": "string"}],
        )

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_remove=["line_item"])

        assert "line_item" in result["removed_fields"]
        assert "line_items" in result["removed_fields"]
        assert "invoice_number" in result["remaining_fields"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_removes_multivalue_when_all_tuple_children_removed(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that removing all tuple children also removes multivalue."""
        self._setup_multivalue_schema(
            mock_mcp,
            mock_client,
            monkeypatch,
            tuple_children=[
                {"id": "item_desc", "label": "Description", "category": "datapoint", "type": "string"},
                {"id": "item_qty", "label": "Quantity", "category": "datapoint", "type": "number"},
            ],
        )

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_remove=["item_desc", "item_qty"])

        assert "item_desc" in result["removed_fields"]
        assert "item_qty" in result["removed_fields"]
        assert "line_item" in result["removed_fields"]
        assert "line_items" in result["removed_fields"]
        assert "invoice_number" in result["remaining_fields"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_removes_empty_sections(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that sections with no remaining children are removed (API rejects empty sections)."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_schema_dict = {
            "id": 50,
            "content": [
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint", "type": "string"}
                    ],
                },
                {
                    "id": "payment_section",
                    "label": "Payment",
                    "category": "section",
                    "children": [
                        {"id": "bank_account", "label": "Bank Account", "category": "datapoint", "type": "string"}
                    ],
                },
            ],
        }
        mock_client._http_client.request_json.return_value = mock_schema_dict
        mock_client._http_client.update.return_value = {}

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_keep=["invoice_number"])

        assert "bank_account" in result["removed_fields"]
        assert "payment_section" in result["removed_fields"]
        assert "invoice_number" in result["remaining_fields"]
        assert "header_section" in result["remaining_fields"]
        assert "payment_section" not in result["remaining_fields"]

    @pytest.mark.asyncio
    async def test_prune_schema_fields_rejects_empty_result(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that pruning all fields raises ValueError instead of emptying the schema."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_schema_dict = {
            "id": 50,
            "content": [
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint", "type": "string"}
                    ],
                }
            ],
        }
        mock_client._http_client.request_json.return_value = mock_schema_dict

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        result = await prune_schema_fields(schema_id=50, fields_to_remove=["invoice_number"])

        assert isinstance(result, dict)
        assert "error" in result
        assert "empty content" in result["error"]
        mock_client._http_client.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_prune_schema_fields_retries_on_412(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that prune_schema_fields retries on 412 Precondition Failed."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_schema_dict = {
            "id": 50,
            "content": [
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint", "type": "string"},
                        {"id": "invoice_date", "label": "Invoice Date", "category": "datapoint", "type": "date"},
                    ],
                }
            ],
        }
        mock_client._http_client.request_json.return_value = mock_schema_dict
        mock_client._http_client.update.side_effect = [
            APIClientError("PATCH", "schemas/50", 412, "Precondition Failed"),
            {},
        ]

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        with patch("rossum_mcp.tools.schemas.operations.asyncio.sleep", new_callable=AsyncMock):
            result = await prune_schema_fields(schema_id=50, fields_to_remove=["invoice_date"])

        assert "invoice_date" in result["removed_fields"]
        assert mock_client._http_client.update.call_count == 2
        assert mock_client._http_client.request_json.call_count == 2

    @pytest.mark.asyncio
    async def test_prune_schema_fields_raises_after_max_retries_on_412(
        self, mock_mcp: Mock, mock_client: AsyncMock, monkeypatch: MonkeyPatch
    ) -> None:
        """Test that prune_schema_fields raises after exhausting retries on 412."""
        monkeypatch.setenv("ROSSUM_MCP_MODE", "read-write")
        importlib.reload(base)
        importlib.reload(schemas)

        schemas.register_schema_tools(mock_mcp, mock_client)

        mock_schema_dict = {
            "id": 50,
            "content": [
                {
                    "id": "header_section",
                    "label": "Header",
                    "category": "section",
                    "children": [
                        {"id": "invoice_number", "label": "Invoice Number", "category": "datapoint", "type": "string"},
                        {"id": "invoice_date", "label": "Invoice Date", "category": "datapoint", "type": "date"},
                    ],
                }
            ],
        }
        mock_client._http_client.request_json.return_value = mock_schema_dict
        mock_client._http_client.update.side_effect = APIClientError("PATCH", "schemas/50", 412, "Precondition Failed")

        prune_schema_fields = mock_mcp._tools["prune_schema_fields"]
        with patch("rossum_mcp.tools.schemas.operations.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(APIClientError, match="412"):
                await prune_schema_fields(schema_id=50, fields_to_remove=["invoice_date"])
