from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.document_relation import DocumentRelation

from rossum_mcp.tools.base import build_filters, graceful_list

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _get_document_relation(client: AsyncRossumAPIClient, document_relation_id: int) -> DocumentRelation:
    logger.debug(f"Retrieving document relation: document_relation_id={document_relation_id}")
    return await client.retrieve_document_relation(document_relation_id)


async def _list_document_relations(client: AsyncRossumAPIClient, **kwargs: object) -> list[object]:
    filters = build_filters(**kwargs)
    result = await graceful_list(client, Resource.DocumentRelation, "document_relation", **filters)
    return result.items
