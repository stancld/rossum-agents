from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.organization_group import OrganizationGroup

from rossum_mcp.tools.base import build_filters, graceful_list

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _get_organization_group(client: AsyncRossumAPIClient, organization_group_id: int) -> OrganizationGroup:
    logger.debug(f"Retrieving organization group: organization_group_id={organization_group_id}")
    organization_group: OrganizationGroup = await client.retrieve_organization_group(organization_group_id)
    return organization_group


async def _list_organization_groups(client: AsyncRossumAPIClient, name: str | None = None) -> list[OrganizationGroup]:
    logger.debug(f"Listing organization groups: name={name}")
    filters = build_filters(name=name)
    result = await graceful_list(client, Resource.OrganizationGroup, "organization_group", **filters)
    return result.items


async def _are_lookup_fields_enabled(client: AsyncRossumAPIClient) -> dict:
    groups = await _list_organization_groups(client)
    for group in groups:
        features = group.features or {}
        if features.get("datasets") and features.get("lookup_fields"):
            return {"enabled": True}
    return {"enabled": False}


def register_organization_group_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(description="Retrieve organization group details.")
    async def get_organization_group(organization_group_id: int) -> OrganizationGroup:
        return await _get_organization_group(client, organization_group_id)

    @mcp.tool(description="List organization groups with optional name filter.")
    async def list_organization_groups(name: str | None = None) -> list[OrganizationGroup]:
        return await _list_organization_groups(client, name)

    @mcp.tool(description="Check if lookup fields are enabled in an organization group.")
    async def are_lookup_fields_enabled() -> dict:
        return await _are_lookup_fields_enabled(client)
