from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.workspace import Workspace

from rossum_mcp.tools.base import (
    build_filters,
    build_resource_url,
    delete_resource,
    filter_by_name_regex,
    graceful_list,
)

if TYPE_CHECKING:
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
    return filter_by_name_regex(items, name, use_regex)


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
