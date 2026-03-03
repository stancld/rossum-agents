from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.organization_group import OrganizationGroup

from rossum_mcp.tools.base import build_filters, filter_by_name_regex, graceful_list

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _get_organization_group(client: AsyncRossumAPIClient, organization_group_id: int) -> OrganizationGroup:
    logger.debug(f"Retrieving organization group: organization_group_id={organization_group_id}")
    return await client.retrieve_organization_group(organization_group_id)


async def _list_organization_groups(
    client: AsyncRossumAPIClient, name: str | None = None, use_regex: bool = False
) -> list[OrganizationGroup]:
    logger.debug(f"Listing organization groups: name={name}")
    filters = build_filters(name=None if use_regex else name)
    items = (await graceful_list(client, Resource.OrganizationGroup, "organization_group", **filters)).items
    return filter_by_name_regex(items, name, use_regex)
