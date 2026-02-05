"""Schema tools for Rossum MCP Server."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_api.models.schema import Schema

from rossum_mcp.tools.schemas.models import (
    DatapointType,
    NodeCategory,
    SchemaDatapoint,
    SchemaMultivalue,
    SchemaNode,
    SchemaNodeUpdate,
    SchemaTreeNode,
    SchemaTuple,
)
from rossum_mcp.tools.schemas.operations import (
    create_schema,
    delete_schema,
    get_schema,
    get_schema_tree_structure,
    list_schemas,
    patch_schema,
    prune_schema_fields,
    update_schema,
)
from rossum_mcp.tools.schemas.patching import (
    PatchOperation,
    _apply_add_operation,
    _apply_remove_operation,
    _apply_update_operation,
    _find_node_anywhere,
    _find_node_in_children,
    _find_parent_children_list,
    _get_section_children_as_list,
    apply_schema_patch,
)
from rossum_mcp.tools.schemas.pruning import (
    _collect_all_field_ids,
    _collect_ancestor_ids,
    _extract_schema_tree,
    _remove_fields_from_content,
)
from rossum_mcp.tools.schemas.validation import (
    MAX_ID_LENGTH,
    VALID_DATAPOINT_TYPES,
    VALID_UI_CONFIGURATION_EDIT,
    VALID_UI_CONFIGURATION_TYPES,
    SchemaValidationError,
    _validate_datapoint,
    _validate_id,
    _validate_multivalue,
    _validate_node,
    _validate_section,
    _validate_tuple,
    sanitize_schema_content,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

__all__ = [
    "MAX_ID_LENGTH",
    "VALID_DATAPOINT_TYPES",
    "VALID_UI_CONFIGURATION_EDIT",
    "VALID_UI_CONFIGURATION_TYPES",
    "DatapointType",
    "NodeCategory",
    "PatchOperation",
    "SchemaDatapoint",
    "SchemaMultivalue",
    "SchemaNode",
    "SchemaNodeUpdate",
    "SchemaTreeNode",
    "SchemaTuple",
    "SchemaValidationError",
    "_apply_add_operation",
    "_apply_remove_operation",
    "_apply_update_operation",
    "_collect_all_field_ids",
    "_collect_ancestor_ids",
    "_extract_schema_tree",
    "_find_node_anywhere",
    "_find_node_in_children",
    "_find_parent_children_list",
    "_get_section_children_as_list",
    "_remove_fields_from_content",
    "_validate_datapoint",
    "_validate_id",
    "_validate_multivalue",
    "_validate_node",
    "_validate_section",
    "_validate_tuple",
    "apply_schema_patch",
    "create_schema",
    "delete_schema",
    "get_schema",
    "get_schema_tree_structure",
    "list_schemas",
    "patch_schema",
    "prune_schema_fields",
    "register_schema_tools",
    "sanitize_schema_content",
    "update_schema",
]


def register_schema_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    """Register schema-related tools with the FastMCP server."""
    from rossum_mcp.tools.schemas import operations as ops  # noqa: PLC0415 - avoid circular import

    @mcp.tool(description="Retrieve schema details.")
    async def get_schema(schema_id: int) -> Schema | dict:
        return await ops.get_schema(client, schema_id)

    @mcp.tool(description="List all schemas with optional filters.")
    async def list_schemas(name: str | None = None, queue_id: int | None = None) -> list[Schema]:
        return await ops.list_schemas(client, name, queue_id)

    @mcp.tool(description="Update schema, typically for field-level thresholds.")
    async def update_schema(schema_id: int, schema_data: dict) -> Schema | dict:
        return await ops.update_schema(client, schema_id, schema_data)

    @mcp.tool(description="Create a schema. Must have ≥1 section with children (datapoints).")
    async def create_schema(name: str, content: list[dict]) -> Schema | dict:
        return await ops.create_schema(client, name, content)

    @mcp.tool(
        description="""Patch schema nodes (add/update/remove fields in a schema).

You MUST load `schema-patching` skill first to avoid errors.

Operations:
- add: Create new field. Requires parent_id (section or tuple id) and node_data.
- update: Modify existing field. Requires node_data with fields to change.
- remove: Delete field. Only requires node_id.

Node types for add:
- Datapoint (simple field): {"label": "Field Name", "category": "datapoint", "type": "string|number|date|enum"}
- Enum field: Include "options": [{"value": "v1", "label": "Label 1"}, ...]
- Multivalue (table): {"label": "Table", "category": "multivalue", "children": <tuple>}
- Tuple (table row): {"id": "row_id", "label": "Row", "category": "tuple", "children": [<datapoints with id>]}

Important: Datapoints inside a tuple MUST have an "id" field. Section-level datapoints get id from node_id parameter.
"""
    )
    async def patch_schema(
        schema_id: int,
        operation: PatchOperation,
        node_id: str,
        node_data: SchemaNode | SchemaNodeUpdate | None = None,
        parent_id: str | None = None,
        position: int | None = None,
    ) -> Schema | dict:
        return await ops.patch_schema(client, schema_id, operation, node_id, node_data, parent_id, position)

    @mcp.tool(
        description="Get lightweight tree structure of schema with only ids, labels, categories, and types. Accepts schema_id or queue_id (resolves to schema automatically)."
    )
    async def get_schema_tree_structure(
        schema_id: int | None = None, queue_id: int | None = None
    ) -> list[dict] | dict:
        return await ops.get_schema_tree_structure(client, schema_id=schema_id, queue_id=queue_id)

    @mcp.tool(
        description="""Remove multiple fields from schema at once. Efficient for pruning unwanted fields during setup.

Use fields_to_keep OR fields_to_remove (not both):
- fields_to_keep: Keep only these field IDs (plus sections). All others removed.
- fields_to_remove: Remove these specific field IDs.

Returns dict with removed_fields and remaining_fields lists. Sections cannot be removed."""
    )
    async def prune_schema_fields(
        schema_id: int,
        fields_to_keep: list[str] | None = None,
        fields_to_remove: list[str] | None = None,
    ) -> dict:
        return await ops.prune_schema_fields(client, schema_id, fields_to_keep, fields_to_remove)

    @mcp.tool(description="Delete a schema. Fails if schema is linked to a queue or annotation (HTTP 409).")
    async def delete_schema(schema_id: int) -> dict:
        return await ops.delete_schema(client, schema_id)
