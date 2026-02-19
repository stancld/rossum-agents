from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.group import Group
from rossum_api.models.user import User

from rossum_mcp.tools.base import build_filters, graceful_list, is_read_write_mode

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _get_user(client: AsyncRossumAPIClient, user_id: int) -> User:
    return await client.retrieve_user(user_id)


async def _list_users(
    client: AsyncRossumAPIClient,
    username: str | None = None,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    is_active: bool | None = None,
    is_organization_group_admin: bool | None = None,
) -> list[User]:
    filters = build_filters(
        username=username, email=email, first_name=first_name, last_name=last_name, is_active=is_active
    )
    result = await graceful_list(client, Resource.User, "user", **filters)
    users_list = result.items

    if is_organization_group_admin is not None:
        roles_result = await graceful_list(client, Resource.Group, "user_role")
        org_admin_role_urls: set[str] = {
            group.url for group in roles_result.items if group.name == "organization_group_admin"
        }
        if is_organization_group_admin:
            users_list = [user for user in users_list if set(user.groups) & org_admin_role_urls]
        else:
            users_list = [user for user in users_list if not (set(user.groups) & org_admin_role_urls)]

    return users_list


async def _create_user(
    client: AsyncRossumAPIClient,
    username: str,
    email: str,
    queues: list[str] | None = None,
    groups: list[str] | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    is_active: bool = True,
    metadata: dict | None = None,
    oidc_id: str | None = None,
    auth_type: str = "password",
) -> User | dict:
    if not is_read_write_mode():
        return {"error": "create_user is not available in read-only mode"}

    user_data: dict[str, Any] = {
        "username": username,
        "email": email,
        "is_active": is_active,
        "auth_type": auth_type,
    }
    if queues is not None:
        user_data["queues"] = queues
    if groups is not None:
        user_data["groups"] = groups
    if first_name is not None:
        user_data["first_name"] = first_name
    if last_name is not None:
        user_data["last_name"] = last_name
    if metadata is not None:
        user_data["metadata"] = metadata
    if oidc_id is not None:
        user_data["oidc_id"] = oidc_id

    user: User = await client.create_new_user(user_data)
    return user


async def _update_user(
    client: AsyncRossumAPIClient,
    user_id: int,
    username: str | None = None,
    email: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    queues: list[str] | None = None,
    groups: list[str] | None = None,
    is_active: bool | None = None,
    metadata: dict | None = None,
    oidc_id: str | None = None,
    auth_type: str | None = None,
    ui_settings: dict | None = None,
) -> User | dict:
    if not is_read_write_mode():
        return {"error": "update_user is not available in read-only mode"}

    logger.debug(f"Updating user: user_id={user_id}")

    patch_data = build_filters(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name,
        queues=queues,
        groups=groups,
        is_active=is_active,
        metadata=metadata,
        oidc_id=oidc_id,
        auth_type=auth_type,
        ui_settings=ui_settings,
    )

    updated_user_data = await client._http_client.update(Resource.User, user_id, patch_data)
    return cast("User", client._deserializer(Resource.User, updated_user_data))


async def _list_user_roles(client: AsyncRossumAPIClient) -> list[Group]:
    result = await graceful_list(client, Resource.Group, "user_role")
    return result.items


def register_user_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(description="Retrieve one user by ID.")
    async def get_user(user_id: int) -> User:
        return await _get_user(client, user_id)

    @mcp.tool(
        description="List users (filterable by username/email). organization_group_admin users cannot be used as token owners; filter with is_organization_group_admin=false."
    )
    async def list_users(
        username: str | None = None,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        is_active: bool | None = None,
        is_organization_group_admin: bool | None = None,
    ) -> list[User]:
        return await _list_users(
            client, username, email, first_name, last_name, is_active, is_organization_group_admin
        )

    @mcp.tool(
        description="Create a user (requires username + email). Use list_user_roles for role/group URLs; queue/group fields take full API URLs."
    )
    async def create_user(
        username: str,
        email: str,
        queues: list[str] | None = None,
        groups: list[str] | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        is_active: bool = True,
        metadata: dict | None = None,
        oidc_id: str | None = None,
        auth_type: str = "password",
    ) -> User | dict:
        return await _create_user(
            client, username, email, queues, groups, first_name, last_name, is_active, metadata, oidc_id, auth_type
        )

    @mcp.tool(description="Patch a user; only provided fields change. Use list_user_roles for role/group URLs.")
    async def update_user(
        user_id: int,
        username: str | None = None,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        queues: list[str] | None = None,
        groups: list[str] | None = None,
        is_active: bool | None = None,
        metadata: dict | None = None,
        oidc_id: str | None = None,
        auth_type: str | None = None,
        ui_settings: dict | None = None,
    ) -> User | dict:
        return await _update_user(
            client,
            user_id,
            username,
            email,
            first_name,
            last_name,
            queues,
            groups,
            is_active,
            metadata,
            oidc_id,
            auth_type,
            ui_settings,
        )

    @mcp.tool(description="List all user roles (groups of permissions) in the organization.")
    async def list_user_roles() -> list[Group]:
        return await _list_user_roles(client)
