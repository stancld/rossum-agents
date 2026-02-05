"""Schema validation utilities for Rossum MCP Server."""

from __future__ import annotations

MAX_ID_LENGTH = 50
VALID_DATAPOINT_TYPES = {"string", "number", "date", "enum", "button"}


class SchemaValidationError(ValueError):
    """Raised when schema validation fails."""


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
