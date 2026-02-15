"""Schema validation utilities for Rossum MCP Server."""

from __future__ import annotations

MAX_ID_LENGTH = 50
VALID_DATAPOINT_TYPES = {"string", "number", "date", "enum", "button"}
VALID_UI_CONFIGURATION_TYPES = {"captured", "data", "manual", "formula", "reasoning", None}
VALID_UI_CONFIGURATION_EDIT = {"enabled", "enabled_without_warning", "disabled"}
# These attributes are only valid on datapoints inside a multivalue's tuple (table columns)
MULTIVALUE_TUPLE_ONLY_FIELDS = {"width", "stretch", "can_collapse", "width_chars"}


class SchemaValidationError(ValueError):
    """Raised when schema validation fails."""


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


def _validate_id(node_id: str, context: str = "") -> None:
    """Validate node ID constraints."""
    if not node_id:
        raise SchemaValidationError(f"Node id is required{context}")
    if len(node_id) > MAX_ID_LENGTH:
        raise SchemaValidationError(f"Node id '{node_id}' exceeds {MAX_ID_LENGTH} characters{context}")


def _validate_datapoint(node: dict, context: str = "") -> None:
    """Validate a datapoint node has required fields."""
    if "label" not in node:
        raise SchemaValidationError(f"Datapoint missing required 'label'{context}")
    if "type" not in node:
        raise SchemaValidationError(f"Datapoint missing required 'type'{context}")
    if node["type"] not in VALID_DATAPOINT_TYPES:
        raise SchemaValidationError(
            f"Invalid datapoint type '{node['type']}'. Must be one of: {', '.join(VALID_DATAPOINT_TYPES)}{context}"
        )


def _validate_tuple(node: dict, node_id: str, context: str) -> None:
    """Validate a tuple node."""
    if "label" not in node:
        raise SchemaValidationError(f"Tuple missing required 'label'{context}")
    if "id" not in node:
        raise SchemaValidationError(f"Tuple missing required 'id'{context}")
    children = node.get("children", [])
    if not isinstance(children, list):
        raise SchemaValidationError(f"Tuple children must be a list{context}")
    for i, child in enumerate(children):
        child_id = child.get("id", f"index {i}")
        _validate_node(child, f" in tuple '{node_id}' child '{child_id}'")
        if "id" not in child:
            raise SchemaValidationError(f"Datapoint inside tuple must have 'id'{context} child index {i}")


def _validate_multivalue(node: dict, node_id: str, context: str) -> None:
    """Validate a multivalue node."""
    if "label" not in node:
        raise SchemaValidationError(f"Multivalue missing required 'label'{context}")
    children = node.get("children")
    if children is None:
        raise SchemaValidationError(f"Multivalue missing required 'children'{context}")
    if isinstance(children, list):
        raise SchemaValidationError(f"Multivalue 'children' must be a single object (dict), not a list{context}")
    if isinstance(children, dict):
        _validate_node(children, f" in multivalue '{node_id}' children")


def _validate_section(node: dict, node_id: str, context: str) -> None:
    """Validate a section node."""
    if "label" not in node:
        raise SchemaValidationError(f"Section missing required 'label'{context}")
    if "id" not in node:
        raise SchemaValidationError(f"Section missing required 'id'{context}")
    children = node.get("children", [])
    if not isinstance(children, list):
        raise SchemaValidationError(f"Section children must be a list{context}")
    for child in children:
        child_id = child.get("id", "unknown")
        _validate_node(child, f" in section '{node_id}' child '{child_id}'")


def _validate_node(node: dict, context: str = "") -> None:
    """Validate a schema node recursively."""
    category = node.get("category")
    node_id = node.get("id", "")

    if node_id:
        _validate_id(node_id, context)

    if category == "datapoint":
        _validate_datapoint(node, context)
    elif category == "tuple":
        _validate_tuple(node, node_id, context)
    elif category == "multivalue":
        _validate_multivalue(node, node_id, context)
    elif category == "section":
        _validate_section(node, node_id, context)
