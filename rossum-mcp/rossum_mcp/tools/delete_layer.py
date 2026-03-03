"""Unified delete layer: single `delete` tool replacing individual delete_X tools."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Literal, get_args

from rossum_mcp.tools.annotations import _delete_annotation
from rossum_mcp.tools.hooks import _delete_hook
from rossum_mcp.tools.queues import _delete_queue
from rossum_mcp.tools.rules import _delete_rule
from rossum_mcp.tools.schemas.operations import delete_schema
from rossum_mcp.tools.workspaces import _delete_workspace

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

DeleteEntityType = Literal[
    "queue",
    "schema",
    "hook",
    "rule",
    "workspace",
    "annotation",
]


DeleteRegistry = dict[str, Callable[[int], Awaitable[dict]]]


def _build_delete_registry(client: AsyncRossumAPIClient) -> DeleteRegistry:
    return {
        "queue": lambda eid: _delete_queue(client, eid),
        "schema": lambda eid: delete_schema(client, eid),
        "hook": lambda eid: _delete_hook(client, eid),
        "rule": lambda eid: _delete_rule(client, eid),
        "workspace": lambda eid: _delete_workspace(client, eid),
        "annotation": lambda eid: _delete_annotation(client, eid),
    }


def register_delete_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    registry = _build_delete_registry(client)

    # Fail fast at startup if DeleteEntityType drifts from the registry
    for _entity in get_args(DeleteEntityType):
        if _entity not in registry:
            raise RuntimeError(
                f"DeleteEntityType member '{_entity}' is missing from registry — "
                "update DeleteEntityType or _build_delete_registry to keep them in sync"
            )

    @mcp.tool(
        description=(
            "Delete an entity by ID. "
            "Entity-specific behavior: "
            "queue → deletion begins after ~24h, cascades to annotations/documents; "
            "annotation → soft-delete (status 'deleted'); "
            "workspace → fails if it still contains queues; "
            "schema → fails with 409 if linked to any queue/annotation."
        ),
        tags={"write"},
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def delete(entity: DeleteEntityType, entity_id: int) -> dict:
        delete_fn = registry.get(entity)
        if delete_fn is None:
            return {"error": f"Unknown entity type: {entity}"}

        return await delete_fn(entity_id)
