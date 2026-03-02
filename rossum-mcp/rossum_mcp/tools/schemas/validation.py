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


def sanitize_schema_content(content: list[dict]) -> list[dict]:
    """Sanitize schema content to prevent API errors.

    Strips invalid ui_configuration values and removes stretch/width/can_collapse/width_chars
    from fields not inside a multivalue-tuple (the API only allows them on table columns).
    """

    def _traverse(node: dict, *, in_multivalue_tuple: bool = False, parent_is_multivalue: bool = False) -> None:
        # Strip None values — the API rejects explicit nulls for optional fields
        # like score_threshold, description, formula, prompt, context, grid
        none_keys = [k for k, v in node.items() if v is None]
        for k in none_keys:
            del node[k]

        # Coerce type to string — LLM may produce {"type": {"type": "number"}}
        if "type" in node and not isinstance(node["type"], str):
            raw = node["type"]
            if isinstance(raw, dict) and isinstance(raw.get("type"), str):
                node["type"] = raw["type"]
            else:
                del node["type"]

        _sanitize_ui_configuration(node)
        if not in_multivalue_tuple:
            _strip_tuple_only_fields(node)

        is_multivalue = node.get("category") == "multivalue"
        children = node.get("children")
        if children is not None:
            if isinstance(children, dict):
                # Multivalue's children is a dict (the tuple container)
                _traverse(children, parent_is_multivalue=is_multivalue)
            elif isinstance(children, list):
                # If parent was multivalue, we're in the tuple → list children can have stretch
                child_in_tuple = parent_is_multivalue or in_multivalue_tuple
                for child in children:
                    _traverse(child, in_multivalue_tuple=child_in_tuple)

    for section in content:
        _traverse(section)
    return content
