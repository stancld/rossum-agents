"""Schema validation utilities for Rossum MCP Server."""

from __future__ import annotations

VALID_UI_CONFIGURATION_TYPES = {"captured", "data", "manual", "formula", "reasoning", "lookup", None}
VALID_UI_CONFIGURATION_EDIT = {"enabled", "enabled_without_warning", "disabled"}
# These attributes are only valid on datapoints inside a multivalue's tuple (table columns)
MULTIVALUE_TUPLE_ONLY_FIELDS = {"width", "stretch", "can_collapse", "width_chars"}


def _sanitize_ui_configuration(node: dict) -> None:
    """Remove invalid ui_configuration.type values to prevent API errors."""
    ui_config = node.get("ui_configuration")
    if not isinstance(ui_config, dict):
        return
    if "type" in ui_config and ui_config["type"] not in VALID_UI_CONFIGURATION_TYPES:
        del ui_config["type"]
    if "edit" in ui_config and ui_config["edit"] not in VALID_UI_CONFIGURATION_EDIT:
        del ui_config["edit"]
    if not ui_config:
        del node["ui_configuration"]


def _strip_tuple_only_fields(node: dict) -> None:
    """Remove multivalue-tuple-only attributes (stretch, width, etc.) from a node."""
    for field in MULTIVALUE_TUPLE_ONLY_FIELDS:
        node.pop(field, None)


def _strip_none_values(node: dict) -> None:
    """Strip None values from a node, preserving conditionally-required fields.

    The API rejects explicit nulls for optional fields like score_threshold, description, grid.
    Formula nodes require "formula"; reasoning nodes require "prompt" and "context".
    """
    preserve_none: set[str] = set()
    ui_config = node.get("ui_configuration")
    if isinstance(ui_config, dict):
        ui_type = ui_config.get("type")
        if ui_type == "formula":
            preserve_none.add("formula")
        if ui_type == "reasoning":
            preserve_none |= {"prompt", "context"}

    none_keys = [k for k, v in node.items() if v is None and k not in preserve_none]
    for k in none_keys:
        del node[k]


def _coerce_type_field(node: dict) -> None:
    """Coerce the type field to a string and ensure datapoints have a valid type."""
    # LLM may produce {"type": {"type": "number"}} — unwrap it
    if "type" in node and not isinstance(node["type"], str):
        raw = node["type"]
        if isinstance(raw, dict) and isinstance(raw.get("type"), str):
            node["type"] = raw["type"]
        else:
            del node["type"]

    # Ensure datapoint nodes have a valid type — the API requires it.
    if node.get("category") == "datapoint" and "type" not in node:
        node["type"] = "string"


def _traverse_schema_node(
    node: dict, *, in_multivalue_tuple: bool = False, parent_is_multivalue: bool = False
) -> None:
    """Recursively sanitize a single schema node and its children."""
    _strip_none_values(node)
    _coerce_type_field(node)
    _sanitize_ui_configuration(node)
    if not in_multivalue_tuple:
        _strip_tuple_only_fields(node)

    is_multivalue = node.get("category") == "multivalue"
    children = node.get("children")
    if children is not None:
        if isinstance(children, dict):
            _traverse_schema_node(children, parent_is_multivalue=is_multivalue)
        elif isinstance(children, list):
            child_in_tuple = parent_is_multivalue or in_multivalue_tuple
            for child in children:
                _traverse_schema_node(child, in_multivalue_tuple=child_in_tuple)


def sanitize_schema_content(content: list[dict]) -> list[dict]:
    """Sanitize schema content to prevent API errors.

    Strips invalid ui_configuration values and removes stretch/width/can_collapse/width_chars
    from fields not inside a multivalue-tuple (the API only allows them on table columns).
    """
    for section in content:
        _traverse_schema_node(section)
    return content
