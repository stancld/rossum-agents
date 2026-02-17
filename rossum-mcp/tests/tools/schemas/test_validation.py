"""Tests for schema validation functions."""

from __future__ import annotations

import pytest
from rossum_mcp.tools import schemas
from rossum_mcp.tools.schemas.validation import (
    _validate_datapoint,
    _validate_id,
    _validate_multivalue,
    _validate_node,
    _validate_section,
    _validate_tuple,
)


@pytest.mark.unit
class TestSchemaValidation:
    """Tests for schema validation functions."""

    def test_validate_id_empty_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Node id is required"):
            _validate_id("")

    def test_validate_id_exceeds_max_length_raises_error(self) -> None:
        long_id = "a" * 51
        with pytest.raises(schemas.SchemaValidationError, match="exceeds 50 characters"):
            _validate_id(long_id)

    def test_validate_id_valid_passes(self) -> None:
        _validate_id("valid_id")
        _validate_id("a" * 50)

    def test_validate_datapoint_missing_label_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="missing required 'label'"):
            _validate_datapoint({"type": "string"})

    def test_validate_datapoint_missing_type_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="missing required 'type'"):
            _validate_datapoint({"label": "Test"})

    def test_validate_datapoint_invalid_type_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Invalid datapoint type 'invalid'"):
            _validate_datapoint({"label": "Test", "type": "invalid"})

    def test_validate_datapoint_valid_types_pass(self) -> None:
        for dp_type in ["string", "number", "date", "enum", "button"]:
            _validate_datapoint({"label": "Test", "type": dp_type})

    def test_validate_tuple_missing_label_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Tuple missing required 'label'"):
            _validate_tuple({"id": "test", "children": []}, "test", "")

    def test_validate_tuple_missing_id_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Tuple missing required 'id'"):
            _validate_tuple({"label": "Test", "children": []}, "", "")

    def test_validate_tuple_children_not_list_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="children must be a list"):
            _validate_tuple({"id": "test", "label": "Test", "children": {}}, "test", "")

    def test_validate_tuple_child_without_id_raises_error(self) -> None:
        node = {
            "id": "test",
            "label": "Test",
            "children": [{"category": "datapoint", "label": "Child", "type": "string"}],
        }
        with pytest.raises(schemas.SchemaValidationError, match="must have 'id'"):
            _validate_tuple(node, "test", "")

    def test_validate_multivalue_missing_label_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Multivalue missing required 'label'"):
            _validate_multivalue({"children": {}}, "test", "")

    def test_validate_multivalue_missing_children_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Multivalue missing required 'children'"):
            _validate_multivalue({"label": "Test"}, "test", "")

    def test_validate_multivalue_children_as_list_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="must be a single object"):
            _validate_multivalue({"label": "Test", "children": []}, "test", "")

    def test_validate_section_missing_label_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Section missing required 'label'"):
            _validate_section({"id": "test", "children": []}, "test", "")

    def test_validate_section_missing_id_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Section missing required 'id'"):
            _validate_section({"label": "Test", "children": []}, "", "")

    def test_validate_section_children_not_list_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="children must be a list"):
            _validate_section({"id": "test", "label": "Test", "children": {}}, "test", "")

    def test_validate_node_datapoint(self) -> None:
        _validate_node({"category": "datapoint", "id": "field", "label": "Field", "type": "string"})

    def test_validate_node_tuple(self) -> None:
        node = {
            "category": "tuple",
            "id": "row",
            "label": "Row",
            "children": [{"category": "datapoint", "id": "col", "label": "Col", "type": "string"}],
        }
        _validate_node(node)

    def test_validate_node_multivalue(self) -> None:
        node = {
            "category": "multivalue",
            "id": "items",
            "label": "Items",
            "children": {"category": "tuple", "id": "item", "label": "Item", "children": []},
        }
        _validate_node(node)

    def test_validate_node_section(self) -> None:
        node = {
            "category": "section",
            "id": "header",
            "label": "Header",
            "children": [{"category": "datapoint", "id": "field", "label": "Field", "type": "string"}],
        }
        _validate_node(node)

    def test_validate_node_invalid_id_in_nested_child(self) -> None:
        node = {
            "category": "section",
            "id": "header",
            "label": "Header",
            "children": [{"category": "datapoint", "id": "a" * 51, "label": "Field", "type": "string"}],
        }
        with pytest.raises(schemas.SchemaValidationError, match="exceeds 50 characters"):
            _validate_node(node)


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

    def test_removes_non_string_type_without_type_key(self) -> None:
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
        assert "type" not in result[0]["children"][0]

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
