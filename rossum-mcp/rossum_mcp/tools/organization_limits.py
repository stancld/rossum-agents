from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.models.organization_limit import OrganizationLimit

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _get_organization_limit(client: AsyncRossumAPIClient, organization_id: int) -> OrganizationLimit:
    logger.debug(f"Retrieving organization limit: organization_id={organization_id}")
    organization_limit: OrganizationLimit = await client.retrieve_organization_limit(organization_id)
    return organization_limit


def register_organization_limit_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(description="Retrieve email sending limits and usage counters for an organization.")
    async def get_organization_limit(organization_id: int) -> OrganizationLimit:
        return await _get_organization_limit(client, organization_id)
