from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.relation import Relation, RelationType

from rossum_mcp.tools.base import build_filters, graceful_list

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


def register_relation_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(
        description="Retrieve relation details.",
        tags={"relations"},
        annotations={"readOnlyHint": True},
    )
    async def get_relation(relation_id: int) -> Relation:
        logger.debug(f"Retrieving relation: relation_id={relation_id}")
        relation_data = await client._http_client.fetch_one(Resource.Relation, relation_id)
        return cast("Relation", client._deserializer(Resource.Relation, relation_data))

    @mcp.tool(
        description="List annotation relations with optional filters; e.g. edit/attachment/duplicate.",
        tags={"relations"},
        annotations={"readOnlyHint": True},
    )
    async def list_relations(
        id: int | None = None,
        type: RelationType | None = None,
        parent: int | None = None,
        key: str | None = None,
        annotation: int | None = None,
    ) -> list[Relation]:
        logger.debug(f"Listing relations: id={id}, type={type}, parent={parent}, key={key}, annotation={annotation}")
        filters = build_filters(id=id, type=type, parent=parent, key=key, annotation=annotation)
        result = await graceful_list(client, Resource.Relation, "relation", **filters)
        return result.items
