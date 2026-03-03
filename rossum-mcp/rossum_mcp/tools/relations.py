from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.relation import Relation

from rossum_mcp.tools.base import build_filters, graceful_list

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _get_relation(client: AsyncRossumAPIClient, relation_id: int) -> Relation:
    logger.debug(f"Retrieving relation: relation_id={relation_id}")
    relation_data = await client._http_client.fetch_one(Resource.Relation, relation_id)
    return cast("Relation", client._deserializer(Resource.Relation, relation_data))


async def _list_relations(client: AsyncRossumAPIClient, **kwargs: object) -> list[object]:
    filters = build_filters(**kwargs)
    result = await graceful_list(client, Resource.Relation, "relation", **filters)
    return result.items
