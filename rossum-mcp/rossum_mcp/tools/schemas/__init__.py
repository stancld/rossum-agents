from __future__ import annotations

from typing import TYPE_CHECKING

from rossum_api.models.schema import Schema

from rossum_mcp.tools.schemas import operations as ops
from rossum_mcp.tools.schemas.models import (
    DatapointType,
    NodeCategory,
    SchemaDatapoint,
    SchemaListItem,
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
    apply_schema_patch,
)
from rossum_mcp.tools.schemas.validation import (
    MAX_ID_LENGTH,
    VALID_DATAPOINT_TYPES,
    VALID_UI_CONFIGURATION_EDIT,
    VALID_UI_CONFIGURATION_TYPES,
    SchemaValidationError,
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
    "SchemaListItem",
    "SchemaMultivalue",
    "SchemaNode",
    "SchemaNodeUpdate",
    "SchemaTreeNode",
    "SchemaTuple",
    "SchemaValidationError",
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
    @mcp.tool(
        description="Retrieve schema details.",
        tags={"schemas"},
        annotations={"readOnlyHint": True},
    )
    async def get_schema(schema_id: int) -> Schema | dict:
        return await ops.get_schema(client, schema_id)

    @mcp.tool(
        description="List all schemas with optional filters. Set use_regex=True to filter name as a regex pattern (client-side); otherwise name is an exact API-side match.",
        tags={"schemas"},
        annotations={"readOnlyHint": True},
    )
    async def list_schemas(
        name: str | None = None, queue_id: int | None = None, use_regex: bool = False
    ) -> list[SchemaListItem]:
        return await ops.list_schemas(client, name, queue_id, use_regex)

    @mcp.tool(
        description="Update schema settings; requires full schema.",
        tags={"schemas", "write"},
        annotations={"readOnlyHint": False},
    )
    async def update_schema(schema_id: int, schema_data: dict) -> Schema | dict:
        return await ops.update_schema(client, schema_id, schema_data)

    @mcp.tool(
        description="Create a schema; requires at least one section containing datapoints.",
        tags={"schemas", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_schema(name: str, content: list[dict]) -> Schema | dict:
        return await ops.create_schema(client, name, content)

    @mcp.tool(
        description="Patch schema nodes (add/update/remove). Prereq: load schema-patching skill. Ops: add (parent_id + node_data), update (node_id + node_data), remove (node_id only). Tuple datapoints require explicit id; section-level datapoints use the passed node_id.",
        tags={"schemas", "write"},
        annotations={"readOnlyHint": False},
    )
    async def patch_schema(
        schema_id: int,
        operation: PatchOperation,
        node_id: str,
        node_data: SchemaNode | SchemaNodeUpdate | None = None,
        parent_id: str | None = None,
        position: int | None = None,
    ) -> dict:
        return await ops.patch_schema(client, schema_id, operation, node_id, node_data, parent_id, position)

    @mcp.tool(
        description="Lightweight schema tree (ids/labels/categories/types); accepts schema_id or queue_id.",
        tags={"schemas"},
        annotations={"readOnlyHint": True},
    )
    async def get_schema_tree_structure(
        schema_id: int | None = None, queue_id: int | None = None
    ) -> list[dict] | dict:
        return await ops.get_schema_tree_structure(client, schema_id=schema_id, queue_id=queue_id)

    @mcp.tool(
        description="Remove many fields at once. Provide fields_to_keep (keep only these leaf IDs; parent containers preserved automatically; list section IDs to preserve them as empty containers) or fields_to_remove (remove these leaf IDs). Returns {removed_fields, remaining_fields}.",
        tags={"schemas", "write"},
        annotations={"readOnlyHint": False},
    )
    async def prune_schema_fields(
        schema_id: int,
        fields_to_keep: list[str] | None = None,
        fields_to_remove: list[str] | None = None,
    ) -> dict:
        return await ops.prune_schema_fields(client, schema_id, fields_to_keep, fields_to_remove)

    @mcp.tool(
        description="Delete a schema; fails with 409 if linked to any queue/annotation.",
        tags={"schemas", "write"},
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def delete_schema(schema_id: int) -> dict:
        return await ops.delete_schema(client, schema_id)
