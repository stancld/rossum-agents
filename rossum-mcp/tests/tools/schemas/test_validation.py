"""Tests for schema validation functions."""

from __future__ import annotations

import pytest
from rossum_mcp.tools import schemas


@pytest.mark.unit
class TestSanitizeSchemaContent:
    """Tests for sanitize_schema_content function."""

    def test_removes_invalid_ui_configuration_type(self) -> None:
        content = [
            {
                "category": "section",
                "id": "header",
                "label": "Header",
                "children": [
                    {
                        "category": "datapoint",
                        "id": "notes",
                        "label": "Notes",
                        "type": "string",
                        "ui_configuration": {"type": "area"},
                    }
                ],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        assert "ui_configuration" not in result[0]["children"][0]

    def test_removes_invalid_textarea_type(self) -> None:
        content = [
            {
                "category": "section",
                "id": "header",
                "label": "Header",
                "children": [
                    {
                        "category": "datapoint",
                        "id": "notes",
                        "label": "Notes",
                        "type": "string",
                        "ui_configuration": {"type": "textarea"},
                    }
                ],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        assert "ui_configuration" not in result[0]["children"][0]

    def test_preserves_valid_ui_configuration_type(self) -> None:
        for valid_type in ["captured", "data", "manual", "formula", "reasoning"]:
            content = [
                {
                    "category": "section",
                    "id": "header",
                    "label": "Header",
                    "children": [
                        {
                            "category": "datapoint",
                            "id": "field",
                            "label": "Field",
                            "type": "string",
                            "ui_configuration": {"type": valid_type, "edit": "disabled"},
                        }
                    ],
                }
            ]
            result = schemas.sanitize_schema_content(content)
            assert result[0]["children"][0]["ui_configuration"]["type"] == valid_type

    def test_preserves_valid_edit_removes_invalid_type(self) -> None:
        content = [
            {
                "category": "section",
                "id": "header",
                "label": "Header",
                "children": [
                    {
                        "category": "datapoint",
                        "id": "notes",
                        "label": "Notes",
                        "type": "string",
                        "ui_configuration": {"type": "area", "edit": "disabled"},
                    }
                ],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        assert result[0]["children"][0]["ui_configuration"] == {"edit": "disabled"}

    def test_strips_stretch_from_section_datapoint(self) -> None:
        content = [
            {
                "category": "section",
                "id": "header",
                "label": "Header",
                "children": [
                    {
                        "category": "datapoint",
                        "id": "invoice_id",
                        "label": "Invoice ID",
                        "type": "string",
                        "stretch": True,
                        "width": 100,
                    }
                ],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        dp = result[0]["children"][0]
        assert "stretch" not in dp
        assert "width" not in dp

    def test_preserves_stretch_on_multivalue_tuple_children(self) -> None:
        content = [
            {
                "category": "section",
                "id": "items_section",
                "label": "Items",
                "children": [
                    {
                        "category": "multivalue",
                        "id": "line_items",
                        "label": "Line Items",
                        "children": {
                            "category": "tuple",
                            "id": "line_item",
                            "label": "Line Item",
                            "children": [
                                {
                                    "category": "datapoint",
                                    "id": "item_desc",
                                    "label": "Description",
                                    "type": "string",
                                    "stretch": True,
                                    "width": 200,
                                },
                                {
                                    "category": "datapoint",
                                    "id": "item_amount",
                                    "label": "Amount",
                                    "type": "number",
                                    "width": 80,
                                },
                            ],
                        },
                    }
                ],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        tuple_children = result[0]["children"][0]["children"]["children"]
        assert tuple_children[0]["stretch"] is True
        assert tuple_children[0]["width"] == 200
        assert tuple_children[1]["width"] == 80

    def test_strips_stretch_from_multivalue_and_tuple_nodes(self) -> None:
        """stretch/width should be stripped from the multivalue and tuple nodes themselves."""
        content = [
            {
                "category": "section",
                "id": "items_section",
                "label": "Items",
                "children": [
                    {
                        "category": "multivalue",
                        "id": "line_items",
                        "label": "Line Items",
                        "stretch": True,
                        "children": {
                            "category": "tuple",
                            "id": "line_item",
                            "label": "Line Item",
                            "width": 100,
                            "children": [
                                {
                                    "category": "datapoint",
                                    "id": "col",
                                    "label": "Col",
                                    "type": "string",
                                    "stretch": True,
                                }
                            ],
                        },
                    }
                ],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        mv = result[0]["children"][0]
        assert "stretch" not in mv
        tuple_node = mv["children"]
        assert "width" not in tuple_node
        assert tuple_node["children"][0]["stretch"] is True

    def test_strips_all_tuple_only_fields(self) -> None:
        content = [
            {
                "category": "section",
                "id": "header",
                "label": "Header",
                "children": [
                    {
                        "category": "datapoint",
                        "id": "field",
                        "label": "Field",
                        "type": "string",
                        "stretch": True,
                        "width": 100,
                        "can_collapse": True,
                        "width_chars": 20,
                    }
                ],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        dp = result[0]["children"][0]
        for field in ("stretch", "width", "can_collapse", "width_chars"):
            assert field not in dp

    def test_sanitizes_nested_multivalue_tuple_children(self) -> None:
        content = [
            {
                "category": "section",
                "id": "items_section",
                "label": "Items",
                "children": [
                    {
                        "category": "multivalue",
                        "id": "line_items",
                        "label": "Line Items",
                        "children": {
                            "category": "tuple",
                            "id": "line_item",
                            "label": "Line Item",
                            "children": [
                                {
                                    "category": "datapoint",
                                    "id": "description",
                                    "label": "Description",
                                    "type": "string",
                                    "ui_configuration": {"type": "textarea"},
                                }
                            ],
                        },
                    }
                ],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        tuple_children = result[0]["children"][0]["children"]["children"]
        assert "ui_configuration" not in tuple_children[0]

    def test_coerces_dict_type_to_string(self) -> None:
        content = [
            {
                "category": "section",
                "id": "header",
                "label": "Header",
                "children": [
                    {
                        "category": "datapoint",
                        "id": "amount",
                        "label": "Amount",
                        "type": {"type": "number"},
                    }
                ],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        assert result[0]["children"][0]["type"] == "number"

    def test_defaults_type_when_non_string_type_without_type_key(self) -> None:
        """When type is a bad dict (no 'type' key), it's removed and defaults to 'string'."""
        content = [
            {
                "category": "section",
                "id": "header",
                "label": "Header",
                "children": [
                    {
                        "category": "datapoint",
                        "id": "field",
                        "label": "Field",
                        "type": {"foo": "bar"},
                    }
                ],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        assert result[0]["children"][0]["type"] == "string"

    def test_strips_none_values_from_nodes(self) -> None:
        content = [
            {
                "category": "section",
                "id": "header",
                "label": "Header",
                "children": [
                    {
                        "category": "datapoint",
                        "id": "field",
                        "label": "Field",
                        "type": "string",
                        "score_threshold": None,
                        "description": None,
                        "formula": None,
                        "prompt": None,
                        "context": None,
                    }
                ],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        dp = result[0]["children"][0]
        for field in ("score_threshold", "description", "formula", "prompt", "context"):
            assert field not in dp
        # Non-None values are preserved
        assert dp["id"] == "field"
        assert dp["label"] == "Field"

    def test_strips_null_required_fields(self) -> None:
        """None values for id/type/category/label are stripped.

        The API rejects explicit nulls ("id may not be null") and also rejects
        absence for some fields ("type is required"). For id/category/label,
        absence in a PATCH payload means "keep existing value". For type on
        datapoints, we add a "string" default after stripping.
        """
        content = [
            {
                "category": "section",
                "id": "header",
                "label": "Header",
                "children": [
                    {
                        "category": "datapoint",
                        "id": None,
                        "label": None,
                        "type": None,
                    },
                    {
                        "category": None,
                        "id": "field2",
                        "label": "Field 2",
                        "type": "string",
                        "formula": None,
                    },
                ],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        dp1 = result[0]["children"][0]
        assert "id" not in dp1
        assert "label" not in dp1
        # type defaults to "string" for datapoints
        assert dp1["type"] == "string"
        dp2 = result[0]["children"][1]
        assert "category" not in dp2
        assert "formula" not in dp2

    def test_defaults_type_on_datapoint_with_null_type(self) -> None:
        """Datapoint nodes with type=None get type="string" as a safe default."""
        content = [
            {
                "category": "section",
                "id": "header",
                "label": "Header",
                "children": [
                    {
                        "category": "datapoint",
                        "id": "field",
                        "label": "Field",
                        "type": None,
                    }
                ],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        assert result[0]["children"][0]["type"] == "string"

    def test_no_default_type_on_non_datapoint(self) -> None:
        """Non-datapoint nodes (sections, multivalues, tuples) don't get a default type."""
        content = [
            {
                "category": "section",
                "id": "header",
                "label": "Header",
                "type": None,
                "children": [],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        assert "type" not in result[0]

    def test_preserves_formula_on_formula_type_node(self) -> None:
        """formula field must not be stripped on formula-type nodes.

        The API requires 'formula' to be present on datapoints with
        ui_configuration.type == "formula", even if it's null.
        """
        content = [
            {
                "category": "section",
                "id": "header",
                "label": "Header",
                "children": [
                    {
                        "category": "datapoint",
                        "id": "formula_field",
                        "label": "Total",
                        "type": "number",
                        "ui_configuration": {"type": "formula"},
                        "formula": None,
                    },
                    {
                        "category": "datapoint",
                        "id": "regular_field",
                        "label": "Name",
                        "type": "string",
                        "formula": None,
                    },
                ],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        formula_node = result[0]["children"][0]
        assert "formula" in formula_node and formula_node["formula"] is None
        regular_node = result[0]["children"][1]
        assert "formula" not in regular_node

    def test_preserves_prompt_and_context_on_reasoning_type_node(self) -> None:
        """prompt/context fields must not be stripped on reasoning-type nodes."""
        content = [
            {
                "category": "section",
                "id": "header",
                "label": "Header",
                "children": [
                    {
                        "category": "datapoint",
                        "id": "reasoning_field",
                        "label": "Reasoning",
                        "type": "string",
                        "ui_configuration": {"type": "reasoning"},
                        "prompt": None,
                        "context": None,
                    },
                    {
                        "category": "datapoint",
                        "id": "regular_field",
                        "label": "Name",
                        "type": "string",
                        "prompt": None,
                        "context": None,
                    },
                ],
            }
        ]
        result = schemas.sanitize_schema_content(content)
        reasoning_node = result[0]["children"][0]
        assert "prompt" in reasoning_node and reasoning_node["prompt"] is None
        assert "context" in reasoning_node and reasoning_node["context"] is None
        regular_node = result[0]["children"][1]
        assert "prompt" not in regular_node
        assert "context" not in regular_node
