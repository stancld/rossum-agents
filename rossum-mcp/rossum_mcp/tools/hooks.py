from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any, Literal

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.hook import Hook, HookRunData, HookType

from rossum_mcp.tools.base import (
    TRUNCATED_MARKER,
    delete_resource,
    extract_id_from_url,
    graceful_list,
    is_read_write_mode,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

type Timestamp = Annotated[str, "ISO 8601 timestamp (e.g., '2024-01-15T10:30:00Z')"]

logger = logging.getLogger(__name__)


@dataclass
class HookTemplate:
    """Represents a hook template from Rossum Store.

    Hook templates provide pre-built extension configurations that can be
    used to quickly create hooks with standard functionality.
    """

    id: int
    url: str
    name: str
    description: str
    type: str
    events: list[str]
    config: dict[str, Any]
    settings_schema: dict[str, Any] | None
    guide: str | None
    use_token_owner: bool


async def _get_hook(client: AsyncRossumAPIClient, hook_id: int) -> Hook:
    hook: Hook = await client.retrieve_hook(hook_id)
    return hook


async def _list_hooks(
    client: AsyncRossumAPIClient,
    queue_id: int | None = None,
    active: bool | None = None,
    first_n: int | None = None,
) -> list[Hook]:
    filters: dict = {}
    if queue_id is not None:
        filters["queue"] = queue_id
    if active is not None:
        filters["active"] = active

    result = await graceful_list(client, Resource.Hook, "hook", max_items=first_n, **filters)
    return result.items


async def _create_hook(
    client: AsyncRossumAPIClient,
    name: str,
    type: HookType,
    queues: list[str] | None = None,
    events: list[str] | None = None,
    config: dict | None = None,
    settings: dict | None = None,
    secret: str | None = None,
) -> Hook | dict:
    if not is_read_write_mode():
        return {"error": "create_hook is not available in read-only mode"}

    hook_data: dict[str, Any] = {"name": name, "type": type, "sideload": ["schemas"]}

    if queues is not None:
        hook_data["queues"] = queues
    if events is not None:
        hook_data["events"] = events
    if config is None:
        config = {}
    if type == "function" and "source" in config:
        config["function"] = config.pop("source")
    if type == "function" and "runtime" not in config:
        config["runtime"] = "python3.12"
    if "timeout_s" in config and config["timeout_s"] > 60:
        config["timeout_s"] = 60
    hook_data["config"] = config
    if settings is not None:
        hook_data["settings"] = settings
    if secret is not None:
        hook_data["secret"] = secret

    hook: Hook = await client.create_new_hook(hook_data)
    return hook


async def _update_hook(
    client: AsyncRossumAPIClient,
    hook_id: int,
    name: str | None = None,
    queues: list[str] | None = None,
    events: list[str] | None = None,
    config: dict | None = None,
    settings: dict | None = None,
    active: bool | None = None,
) -> Hook | dict:
    if not is_read_write_mode():
        return {"error": "update_hook is not available in read-only mode"}

    logger.debug(f"Updating hook: hook_id={hook_id}")

    existing_hook: Hook = await client.retrieve_hook(hook_id)
    hook_data: dict[str, Any] = {
        "name": existing_hook.name,
        "queues": existing_hook.queues,
        "events": list(existing_hook.events),
        "config": dict(existing_hook.config) if existing_hook.config else {},
    }

    if name is not None:
        hook_data["name"] = name
    if queues is not None:
        hook_data["queues"] = queues
    if events is not None:
        hook_data["events"] = events
    if config is not None:
        hook_data["config"] = config
    if settings is not None:
        hook_data["settings"] = settings
    if active is not None:
        hook_data["active"] = active

    updated_hook: Hook = await client.update_part_hook(hook_id, hook_data)
    return updated_hook


async def _list_hook_logs(
    client: AsyncRossumAPIClient,
    hook_id: int | None = None,
    queue_id: int | None = None,
    annotation_id: int | None = None,
    email_id: int | None = None,
    log_level: Literal["INFO", "ERROR", "WARNING"] | None = None,
    status: str | None = None,
    status_code: int | None = None,
    request_id: str | None = None,
    timestamp_before: Timestamp | None = None,
    timestamp_after: Timestamp | None = None,
    start_before: Timestamp | None = None,
    start_after: Timestamp | None = None,
    end_before: Timestamp | None = None,
    end_after: Timestamp | None = None,
    search: str | None = None,
    page_size: int | None = None,
) -> list[HookRunData]:
    filter_mapping: dict[str, Any] = {
        "hook": hook_id,
        "queue": queue_id,
        "annotation": annotation_id,
        "email": email_id,
        "log_level": log_level,
        "status": status,
        "status_code": status_code,
        "request_id": request_id,
        "timestamp_before": timestamp_before,
        "timestamp_after": timestamp_after,
        "start_before": start_before,
        "start_after": start_after,
        "end_before": end_before,
        "end_after": end_after,
        "search": search,
        "page_size": page_size,
    }
    filters = {k: v for k, v in filter_mapping.items() if v is not None}

    result = await graceful_list(client, Resource.HookRunData, "hook_log", **filters)
    return result.items


async def _list_hook_templates(client: AsyncRossumAPIClient) -> list[HookTemplate]:
    templates: list[HookTemplate] = []
    async for item in client.request_paginated("hook_templates"):
        url = item["url"]
        templates.append(
            HookTemplate(
                id=extract_id_from_url(url),
                url=url,
                name=item["name"],
                description=item.get("description", ""),
                type=item["type"],
                events=[],
                config={},
                settings_schema=item.get("settings_schema"),
                guide=TRUNCATED_MARKER,
                use_token_owner=item.get("use_token_owner", False),
            )
        )
    return templates


async def _create_hook_from_template(
    client: AsyncRossumAPIClient,
    name: str,
    hook_template_id: int,
    queues: list[str],
    events: list[str] | None = None,
    token_owner: str | None = None,
) -> Hook | dict:
    if not is_read_write_mode():
        return {"error": "create_hook_from_template is not available in read-only mode"}

    logger.debug(f"Creating hook from template: name={name}, template_id={hook_template_id}")

    hook_template_url = f"{client._http_client.base_url.rstrip('/')}/hook_templates/{hook_template_id}"

    hook_data: dict[str, Any] = {"name": name, "hook_template": hook_template_url, "queues": queues}
    if events is not None:
        hook_data["events"] = events
    if token_owner is not None:
        hook_data["token_owner"] = token_owner

    result = await client._http_client.request_json("POST", "hooks/create", json=hook_data)

    if hook_id := result.get("id"):
        hook: Hook = await client.retrieve_hook(hook_id)
        return hook
    return {"error": "Hook wasn't likely created. Hook ID not available."}


async def _delete_hook(client: AsyncRossumAPIClient, hook_id: int) -> dict:
    return await delete_resource("hook", hook_id, client.delete_hook)


def register_hook_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(description="Retrieve one hook by ID (function hook code is in hook.config['code']).")
    async def get_hook(hook_id: int) -> Hook:
        return await _get_hook(client, hook_id)

    @mcp.tool(
        description="List hooks for a queue; returns full config/settings (function hook code in config['code'])."
    )
    async def list_hooks(
        queue_id: int | None = None, active: bool | None = None, first_n: int | None = None
    ) -> list[Hook]:
        return await _list_hooks(client, queue_id, active, first_n)

    @mcp.tool(
        description="Create a hook. Function hooks: config.source auto-renamed to config.function, default runtime python3.12, timeout_s capped at 60. token_owner cannot be an organization_group_admin user."
    )
    async def create_hook(
        name: str,
        type: HookType,
        queues: list[str] | None = None,
        events: list[str] | None = None,
        config: dict | None = None,
        settings: dict | None = None,
        secret: str | None = None,
    ) -> Hook | dict:
        return await _create_hook(client, name, type, queues, events, config, settings, secret)

    @mcp.tool(description="Patch a hook; only provided fields change.")
    async def update_hook(
        hook_id: int,
        name: str | None = None,
        queues: list[str] | None = None,
        events: list[str] | None = None,
        config: dict | None = None,
        settings: dict | None = None,
        active: bool | None = None,
    ) -> Hook | dict:
        return await _update_hook(client, hook_id, name, queues, events, config, settings, active)

    @mcp.tool(description="List hook execution logs (7-day retention, max 100 per call).")
    async def list_hook_logs(
        hook_id: int | None = None,
        queue_id: int | None = None,
        annotation_id: int | None = None,
        email_id: int | None = None,
        log_level: Literal["INFO", "ERROR", "WARNING"] | None = None,
        status: str | None = None,
        status_code: int | None = None,
        request_id: str | None = None,
        timestamp_before: Timestamp | None = None,
        timestamp_after: Timestamp | None = None,
        start_before: Timestamp | None = None,
        start_after: Timestamp | None = None,
        end_before: Timestamp | None = None,
        end_after: Timestamp | None = None,
        search: str | None = None,
        page_size: int | None = None,
    ) -> list[HookRunData]:
        return await _list_hook_logs(
            client,
            hook_id,
            queue_id,
            annotation_id,
            email_id,
            log_level,
            status,
            status_code,
            request_id,
            timestamp_before,
            timestamp_after,
            start_before,
            start_after,
            end_before,
            end_after,
            search,
            page_size,
        )

    @mcp.tool(description="List Rossum Store hook templates (use with create_hook_from_template).")
    async def list_hook_templates() -> list[HookTemplate]:
        return await _list_hook_templates(client)

    @mcp.tool(
        description="Create a hook from a template; events may override template defaults. If template requires use_token_owner, provide token_owner (not an organization_group_admin user)."
    )
    async def create_hook_from_template(
        name: str,
        hook_template_id: int,
        queues: list[str],
        events: list[str] | None = None,
        token_owner: str | None = None,
    ) -> Hook | dict:
        return await _create_hook_from_template(client, name, hook_template_id, queues, events, token_owner)

    @mcp.tool(description="Delete a hook.")
    async def delete_hook(hook_id: int) -> dict:
        return await _delete_hook(client, hook_id)
