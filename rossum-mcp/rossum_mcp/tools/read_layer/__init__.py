"""Unified read layer: `get` and `search` tools replacing ~30 individual get_X/list_X tools."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from typing import TYPE_CHECKING, Literal, get_args

from rossum_mcp.tools.read_layer.models import (
    SearchQuery,  # noqa: TC001 - needed at runtime for FastMCP parameter serialization
)
from rossum_mcp.tools.read_layer.registry import EntityConfig, build_registry, extract_search_kwargs
from rossum_mcp.tools.read_layer.related import fetch_related

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)

EntityType = Literal[
    "queue",
    "schema",
    "hook",
    "engine",
    "rule",
    "user",
    "workspace",
    "email_template",
    "organization_group",
    "annotation",
    "relation",
    "document_relation",
    "organization_limit",
]


def _serialize(obj: object) -> object:
    """Convert dataclass instances to dicts for JSON serialization."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    return obj


async def _get_one(
    client: AsyncRossumAPIClient,
    config: EntityConfig,
    entity: str,
    entity_id: int,
    include_related: bool,
) -> dict[str, object]:
    if config.retrieve_fn is None:
        raise RuntimeError(f"Entity '{entity}' has no retrieve_fn — use search instead")
    result = await config.retrieve_fn(entity_id)
    data = _serialize(result)

    response: dict[str, object] = {"entity": entity, "id": entity_id, "data": data}

    if include_related:
        related = await fetch_related(client, entity, entity_id, result)
        if related:
            response["_related"] = related

    return response


async def _get_many(
    client: AsyncRossumAPIClient,
    config: EntityConfig,
    entity: str,
    entity_ids: list[int],
    include_related: bool,
) -> list[dict[str, object]]:
    tasks = [_get_one(client, config, entity, eid, include_related) for eid in entity_ids]
    return list(await asyncio.gather(*tasks))


def register_read_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    registry = build_registry(client)

    # Fail fast at startup if EntityType drifts from the registry
    for _entity in get_args(EntityType):
        if _entity not in registry or registry[_entity].retrieve_fn is None:
            raise RuntimeError(
                f"EntityType member '{_entity}' is missing from registry or has no retrieve_fn — "
                "update EntityType or build_registry to keep them in sync"
            )

    @mcp.tool(
        description=(
            "Get entities by ID. Accepts a single ID or a list of IDs for batch retrieval. "
            "include_related=True enriches with related data (queue→schema_tree+engine+hooks, schema→queues+rules, hook→queues+events)."
        ),
        tags={"read"},
        annotations={"readOnlyHint": True},
    )
    async def get(
        entity: EntityType, entity_id: int | list[int], include_related: bool = False
    ) -> dict[str, object] | list[dict[str, object]]:
        config = registry.get(entity)
        if config is None:
            return {"error": f"Unknown entity type: {entity}"}
        if config.retrieve_fn is None:
            return {"error": f"Entity '{entity}' does not support get by ID. Use search instead."}

        if isinstance(entity_id, list):
            return await _get_many(client, config, entity, entity_id, include_related)

        return await _get_one(client, config, entity, entity_id, include_related)

    @mcp.tool(
        description="Search/list entities with typed, entity-specific filters. Pass a query object with `entity` discriminator.",
        tags={"read"},
        annotations={"readOnlyHint": True},
    )
    async def search(query: SearchQuery) -> list[object]:
        entity = query.entity
        config = registry.get(entity)
        if config is None:
            return [{"error": f"Unknown entity type: {entity}"}]
        if config.search_fn is None:
            return [{"error": f"Entity '{entity}' does not support search/list."}]

        kwargs = extract_search_kwargs(query)
        result = await config.search_fn(**kwargs)
        return [_serialize(item) for item in result]
