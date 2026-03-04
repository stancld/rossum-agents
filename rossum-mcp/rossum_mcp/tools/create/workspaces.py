from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.models.workspace import Workspace

from rossum_mcp.tools.base import build_resource_url

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


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
