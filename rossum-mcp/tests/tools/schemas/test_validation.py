"""Tests for schema validation functions."""

from __future__ import annotations

import pytest
from rossum_mcp.tools import schemas


@pytest.mark.unit
class TestSchemaValidation:
    """Tests for schema validation functions.

    Note: These tests use schemas.* to access functions/classes dynamically
    because other tests use importlib.reload(schemas) which creates new class objects.
    """

    def test_validate_id_empty_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Node id is required"):
            schemas._validate_id("")

    def test_validate_id_exceeds_max_length_raises_error(self) -> None:
        long_id = "a" * 51
        with pytest.raises(schemas.SchemaValidationError, match="exceeds 50 characters"):
            schemas._validate_id(long_id)

    def test_validate_id_valid_passes(self) -> None:
        schemas._validate_id("valid_id")
        schemas._validate_id("a" * 50)

    def test_validate_datapoint_missing_label_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="missing required 'label'"):
            schemas._validate_datapoint({"type": "string"})

    def test_validate_datapoint_missing_type_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="missing required 'type'"):
            schemas._validate_datapoint({"label": "Test"})

    def test_validate_datapoint_invalid_type_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Invalid datapoint type 'invalid'"):
            schemas._validate_datapoint({"label": "Test", "type": "invalid"})

    def test_validate_datapoint_valid_types_pass(self) -> None:
        for dp_type in ["string", "number", "date", "enum", "button"]:
            schemas._validate_datapoint({"label": "Test", "type": dp_type})

    def test_validate_tuple_missing_label_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Tuple missing required 'label'"):
            schemas._validate_tuple({"id": "test", "children": []}, "test", "")

    def test_validate_tuple_missing_id_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Tuple missing required 'id'"):
            schemas._validate_tuple({"label": "Test", "children": []}, "", "")

    def test_validate_tuple_children_not_list_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="children must be a list"):
            schemas._validate_tuple({"id": "test", "label": "Test", "children": {}}, "test", "")

    def test_validate_tuple_child_without_id_raises_error(self) -> None:
        node = {
            "id": "test",
            "label": "Test",
            "children": [{"category": "datapoint", "label": "Child", "type": "string"}],
        }
        with pytest.raises(schemas.SchemaValidationError, match="must have 'id'"):
            schemas._validate_tuple(node, "test", "")

    def test_validate_multivalue_missing_label_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Multivalue missing required 'label'"):
            schemas._validate_multivalue({"children": {}}, "test", "")

    def test_validate_multivalue_missing_children_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Multivalue missing required 'children'"):
            schemas._validate_multivalue({"label": "Test"}, "test", "")

    def test_validate_multivalue_children_as_list_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="must be a single object"):
            schemas._validate_multivalue({"label": "Test", "children": []}, "test", "")

    def test_validate_section_missing_label_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Section missing required 'label'"):
            schemas._validate_section({"id": "test", "children": []}, "test", "")

    def test_validate_section_missing_id_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="Section missing required 'id'"):
            schemas._validate_section({"label": "Test", "children": []}, "", "")

    def test_validate_section_children_not_list_raises_error(self) -> None:
        with pytest.raises(schemas.SchemaValidationError, match="children must be a list"):
            schemas._validate_section({"id": "test", "label": "Test", "children": {}}, "test", "")

    def test_validate_node_datapoint(self) -> None:
        schemas._validate_node({"category": "datapoint", "id": "field", "label": "Field", "type": "string"})

    def test_validate_node_tuple(self) -> None:
        node = {
            "category": "tuple",
            "id": "row",
            "label": "Row",
            "children": [{"category": "datapoint", "id": "col", "label": "Col", "type": "string"}],
        }
        schemas._validate_node(node)

    def test_validate_node_multivalue(self) -> None:
        node = {
            "category": "multivalue",
            "id": "items",
            "label": "Items",
            "children": {"category": "tuple", "id": "item", "label": "Item", "children": []},
        }
        schemas._validate_node(node)

    def test_validate_node_section(self) -> None:
        node = {
            "category": "section",
            "id": "header",
            "label": "Header",
            "children": [{"category": "datapoint", "id": "field", "label": "Field", "type": "string"}],
        }
        schemas._validate_node(node)

    def test_validate_node_invalid_id_in_nested_child(self) -> None:
        node = {
            "category": "section",
            "id": "header",
            "label": "Header",
            "children": [{"category": "datapoint", "id": "a" * 51, "label": "Field", "type": "string"}],
        }
        with pytest.raises(schemas.SchemaValidationError, match="exceeds 50 characters"):
            schemas._validate_node(node)


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
