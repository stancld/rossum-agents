from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.workspace import Workspace

from rossum_mcp.tools.base import build_filters, build_resource_url, delete_resource, graceful_list

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _get_workspace(client: AsyncRossumAPIClient, workspace_id: int) -> Workspace:
    logger.debug(f"Retrieving workspace: workspace_id={workspace_id}")
    return await client.retrieve_workspace(workspace_id)


async def _list_workspaces(
    client: AsyncRossumAPIClient,
    organization_id: int | None = None,
    name: str | None = None,
    use_regex: bool = False,
) -> list[Workspace]:
    logger.debug(f"Listing workspaces: organization_id={organization_id}, name={name}")
    filters = build_filters(organization=organization_id, name=None if use_regex else name)
    items = (await graceful_list(client, Resource.Workspace, "workspace", **filters)).items
    if use_regex and name is not None:
        items = [w for w in items if re.search(name, w.name, re.IGNORECASE)]
    return items


async def _create_workspace(
    client: AsyncRossumAPIClient, name: str, organization_id: int, metadata: dict | None = None
) -> Workspace | dict:
    organization_url = build_resource_url("organizations", organization_id)
    logger.debug(f"Creating workspace: name={name}, organization_id={organization_id}, metadata={metadata}")
    workspace_data: dict = {"name": name, "organization": organization_url}
    if metadata is not None:
        workspace_data["metadata"] = metadata

    workspace: Workspace = await client.create_new_workspace(workspace_data)
    logger.info(f"Successfully created workspace: id={workspace.id}, name={workspace.name}")
    return workspace


async def _delete_workspace(client: AsyncRossumAPIClient, workspace_id: int) -> dict:
    return await delete_resource("workspace", workspace_id, client.delete_workspace)


def register_workspace_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(
        description="Retrieve workspace details.",
        tags={"workspaces"},
        annotations={"readOnlyHint": True},
    )
    async def get_workspace(workspace_id: int) -> Workspace:
        return await _get_workspace(client, workspace_id)

    @mcp.tool(
        description="List all workspaces with optional filters. Set use_regex=True to filter name as a regex pattern (client-side); otherwise name is an exact API-side match.",
        tags={"workspaces"},
        annotations={"readOnlyHint": True},
    )
    async def list_workspaces(
        organization_id: int | None = None,
        name: str | None = None,
        use_regex: bool = False,
    ) -> list[Workspace]:
        return await _list_workspaces(client, organization_id, name, use_regex)

    @mcp.tool(
        description="Create a new workspace.",
        tags={"workspaces", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_workspace(name: str, organization_id: int, metadata: dict | None = None) -> Workspace | dict:
        return await _create_workspace(client, name, organization_id, metadata)

    @mcp.tool(
        description="Delete a workspace; fails if it still contains queues.",
        tags={"workspaces", "write"},
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def delete_workspace(workspace_id: int) -> dict:
        return await _delete_workspace(client, workspace_id)
