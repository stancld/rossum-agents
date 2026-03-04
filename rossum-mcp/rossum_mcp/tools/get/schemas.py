"""Get operations for schemas (tree structure)."""

from __future__ import annotations

from rossum_mcp.tools.get.models import SchemaTreeNode


def _build_tree_node(node: dict) -> SchemaTreeNode:
    """Build a lightweight tree node from a schema node."""
    category = node.get("category", "")
    node_id = node.get("id", "")
    label = node.get("label", "")
    node_type = node.get("type") if category == "datapoint" else None

    children_data = node.get("children")
    children: list[SchemaTreeNode] | None = None

    if children_data is not None:
        if isinstance(children_data, list):
            children = [_build_tree_node(child) for child in children_data]
        elif isinstance(children_data, dict):
            children = [_build_tree_node(children_data)]

    return SchemaTreeNode(id=node_id, label=label, category=category, type=node_type, children=children)


def _extract_schema_tree(content: list[dict]) -> list[dict]:
    """Extract lightweight tree structure from schema content."""
    return [_build_tree_node(section).to_dict() for section in content]
