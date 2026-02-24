from __future__ import annotations

import logging
import re
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
    return await client.retrieve_organization_group(organization_group_id)


async def _list_organization_groups(
    client: AsyncRossumAPIClient, name: str | None = None, use_regex: bool = False
) -> list[OrganizationGroup]:
    logger.debug(f"Listing organization groups: name={name}")
    filters = build_filters(name=None if use_regex else name)
    items = (await graceful_list(client, Resource.OrganizationGroup, "organization_group", **filters)).items
    if use_regex and name is not None:
        items = [g for g in items if re.search(name, g.name, re.IGNORECASE)]
    return items


def _is_feature_enabled(features: dict, key: str) -> bool:
    return bool(features.get(key, {}).get("enabled"))


async def _are_lookup_fields_enabled(client: AsyncRossumAPIClient) -> dict:
    groups = await _list_organization_groups(client)
    for group in groups:
        features = group.features or {}
        if _is_feature_enabled(features, "datasets") and _is_feature_enabled(features, "lookup_fields"):
            return {"enabled": True}
    return {"enabled": False}


async def _are_reasoning_fields_enabled(client: AsyncRossumAPIClient) -> dict:
    groups = await _list_organization_groups(client)
    for group in groups:
        features = group.features or {}
        if _is_feature_enabled(features, "reasoning_fields"):
            return {"enabled": True}
    return {"enabled": False}


def register_organization_group_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(
        description="Retrieve organization group details.",
        tags={"organization_groups"},
        annotations={"readOnlyHint": True},
    )
    async def get_organization_group(organization_group_id: int) -> OrganizationGroup:
        return await _get_organization_group(client, organization_group_id)

    @mcp.tool(
        description="List organization groups with optional name filter. Set use_regex=True to filter name as a regex pattern (client-side); otherwise name is an exact API-side match.",
        tags={"organization_groups"},
        annotations={"readOnlyHint": True},
    )
    async def list_organization_groups(name: str | None = None, use_regex: bool = False) -> list[OrganizationGroup]:
        return await _list_organization_groups(client, name, use_regex)

    @mcp.tool(
        description="Check if lookup fields are enabled. Both 'datasets' and 'lookup_fields' features must be enabled in an organization group.",
        tags={"organization_groups"},
        annotations={"readOnlyHint": True},
    )
    async def are_lookup_fields_enabled() -> dict:
        return await _are_lookup_fields_enabled(client)

    @mcp.tool(
        description="Check if reasoning fields are enabled. The 'reasoning_fields' feature must be enabled in an organization group.",
        tags={"organization_groups"},
        annotations={"readOnlyHint": True},
    )
    async def are_reasoning_fields_enabled() -> dict:
        return await _are_reasoning_fields_enabled(client)
