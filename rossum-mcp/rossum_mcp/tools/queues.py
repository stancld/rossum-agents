from __future__ import annotations

import logging
import os
from dataclasses import replace
from typing import TYPE_CHECKING, Literal, cast, get_args

from rossum_api import APIClientError
from rossum_api.domain_logic.resources import Resource
from rossum_api.models import deserialize_default
from rossum_api.models.engine import Engine
from rossum_api.models.queue import Queue
from rossum_api.models.schema import Schema

from rossum_mcp.tools.base import (
    build_filters,
    build_resource_url,
    delete_resource,
    extract_id_from_url,
    graceful_list,
    truncate_dict_fields,
)

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)

# Fields to truncate in queue.settings for list responses
_QUEUE_SETTINGS_TRUNCATE_FIELDS = (
    "accepted_mime_types",
    "annotation_list_table",
    "users",
    "dashboard_customization",
    "email_notifications",
)


def _truncate_queue_for_list(queue: Queue) -> Queue:
    """Truncate verbose fields in queue settings to save context in list responses."""
    if not queue.settings:
        return queue
    return replace(queue, settings=truncate_dict_fields(queue.settings, _QUEUE_SETTINGS_TRUNCATE_FIELDS))


async def _get_queue(client: AsyncRossumAPIClient, queue_id: int) -> Queue:
    logger.debug(f"Retrieving queue: queue_id={queue_id}")
    queue: Queue = await client.retrieve_queue(queue_id)
    return queue


async def _list_queues(
    client: AsyncRossumAPIClient,
    id: str | None = None,
    workspace_id: int | None = None,
    name: str | None = None,
) -> list[Queue]:
    logger.debug(f"Listing queues: id={id}, workspace_id={workspace_id}, name={name}")
    filters = build_filters(id=id, workspace=workspace_id, name=name)
    result = await graceful_list(client, Resource.Queue, "queue", **filters)
    return [_truncate_queue_for_list(queue) for queue in result.items]


async def _get_queue_schema(client: AsyncRossumAPIClient, queue_id: int) -> Schema:
    logger.debug(f"Retrieving queue schema: queue_id={queue_id}")
    queue: Queue = await client.retrieve_queue(queue_id)
    schema_url = queue.schema
    schema_id = extract_id_from_url(schema_url)
    schema: Schema = await client.retrieve_schema(schema_id)
    return schema


async def _get_queue_engine(client: AsyncRossumAPIClient, queue_id: int) -> Engine | dict:
    logger.debug(f"Retrieving queue engine: queue_id={queue_id}")
    queue: Queue = await client.retrieve_queue(queue_id)

    engine_url = None
    if queue.dedicated_engine:
        engine_url = queue.dedicated_engine
    elif queue.generic_engine:
        engine_url = queue.generic_engine
    elif queue.engine:
        engine_url = queue.engine

    if not engine_url:
        return {"message": "No engine assigned to this queue"}

    try:
        if isinstance(engine_url, str):
            engine_id = extract_id_from_url(engine_url)
            engine: Engine = await client.retrieve_engine(engine_id)
        else:
            engine = deserialize_default(Resource.Engine, engine_url)
    except APIClientError as e:
        if e.status_code == 404:
            return {"message": f"Engine not found (engine URL: {engine_url})"}
        raise

    return engine


async def _create_queue(
    client: AsyncRossumAPIClient,
    name: str,
    workspace_id: int,
    schema_id: int,
    engine_id: int | None = None,
    inbox_id: int | None = None,
    connector_id: int | None = None,
    locale: str = "en_GB",
    automation_enabled: bool = False,
    automation_level: str = "never",
    training_enabled: bool = True,
    splitting_screen_feature_flag: bool = False,
) -> Queue | dict:
    logger.debug(
        f"Creating queue: name={name}, workspace_id={workspace_id}, schema_id={schema_id}, engine_id={engine_id}"
    )

    queue_data: dict = {
        "name": name,
        "workspace": build_resource_url("workspaces", workspace_id),
        "schema": build_resource_url("schemas", schema_id),
        "locale": locale,
        "automation_enabled": automation_enabled,
        "automation_level": automation_level,
        "training_enabled": training_enabled,
    }

    if engine_id is not None:
        queue_data["engine"] = build_resource_url("engines", engine_id)
    if inbox_id is not None:
        queue_data["inbox"] = build_resource_url("inboxes", inbox_id)
    if connector_id is not None:
        queue_data["connector"] = build_resource_url("connectors", connector_id)
    if splitting_screen_feature_flag:
        if os.environ.get("SPLITTING_SCREEN_FLAG_NAME") and os.environ.get("SPLITTING_SCREEN_FLAG_VALUE"):
            queue_data["settings"] = {
                os.environ["SPLITTING_SCREEN_FLAG_NAME"]: os.environ["SPLITTING_SCREEN_FLAG_VALUE"]
            }
        else:
            return {
                "error": "splitting_screen_feature_flag requested but SPLITTING_SCREEN_FLAG_NAME and/or SPLITTING_SCREEN_FLAG_VALUE environment variables are not set"
            }

    queue: Queue = await client.create_new_queue(queue_data)
    return queue


_VALID_META_NAMES = {
    "status",
    "original_file_name",
    "labels",
    "assignees",
    "queue",
    "details",
    "created_at",
    "modified_at",
    "confirmed_at",
    "exported_at",
    "rejected_at",
    "deleted_at",
    "assigned_at",
    "modifier",
    "confirmed_by",
    "exported_by",
    "export_failed_at",
    "rejected_by",
    "deleted_by",
}


def _validate_queue_column_settings(queue_data: dict) -> str | None:
    """Validate meta_name values in annotation_list_table columns. Returns error message or None."""
    columns = queue_data.get("settings", {}).get("annotation_list_table", {}).get("columns", [])
    if not isinstance(columns, list):
        return None

    invalid = []
    for col in columns:
        if isinstance(col, dict) and col.get("column_type") == "meta":
            meta_name = col.get("meta_name")
            if meta_name and meta_name not in _VALID_META_NAMES:
                invalid.append(meta_name)

    if invalid:
        return f"Invalid meta_name value(s): {invalid}. Valid values: {sorted(_VALID_META_NAMES)}"
    return None


async def _update_queue(client: AsyncRossumAPIClient, queue_id: int, queue_data: dict) -> Queue | dict:
    validation_error = _validate_queue_column_settings(queue_data)
    if validation_error:
        return {"error": validation_error}

    logger.debug(f"Updating queue: queue_id={queue_id}, data={queue_data}")
    updated_queue_data = await client._http_client.update(Resource.Queue, queue_id, queue_data)
    return cast("Queue", client._deserializer(Resource.Queue, updated_queue_data))


async def _delete_queue(client: AsyncRossumAPIClient, queue_id: int) -> dict:
    return await delete_resource(
        "queue", queue_id, client.delete_queue, f"Queue {queue_id} scheduled for deletion (starts after 24 hours)"
    )


# Available template names for create_queue_from_template
QueueTemplateName = Literal[
    "EU Demo Template",
    "AP&R EU Demo Template",
    "Tax Invoice EU Demo Template",
    "US Demo Template",
    "AP&R US Demo Template",
    "Tax Invoice US Demo Template",
    "UK Demo Template",
    "AP&R UK Demo Template",
    "Tax Invoice UK Demo Template",
    "CZ Demo Template",
    "Empty Organization Template",
    "Delivery Notes Demo Template",
    "Delivery Note Demo Template",
    "Chinese Invoices (Fapiao) Demo Template",
    "Tax Invoice CN Demo Template",
    "Certificates of Analysis Demo Template",
    "Purchase Order Demo Template",
    "Credit Note Demo Template",
    "Debit Note Demo Template",
    "Proforma Invoice Demo Template",
]
QUEUE_TEMPLATE_NAMES = get_args(QueueTemplateName)


async def _create_queue_from_template(
    client: AsyncRossumAPIClient,
    name: str,
    template_name: QueueTemplateName,
    workspace_id: int,
    include_documents: bool = False,
    engine_id: int | None = None,
) -> Queue | dict:
    if template_name not in QUEUE_TEMPLATE_NAMES:
        return {
            "error": f"Invalid template_name: '{template_name}'",
            "available_templates": QUEUE_TEMPLATE_NAMES,
        }

    logger.debug(
        f"Creating queue from template: name={name}, template_name={template_name}, workspace_id={workspace_id}"
    )

    payload: dict = {
        "name": name,
        "template_name": template_name,
        "workspace": build_resource_url("workspaces", workspace_id),
        "include_documents": include_documents,
    }

    if engine_id is not None:
        payload["engine"] = build_resource_url("engines", engine_id)

    response = await client._http_client.request_json(
        method="POST",
        url="queues/from_template",
        json=payload,
    )
    return cast("Queue", client._deserializer(Resource.Queue, response))


def register_queue_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(
        description="Retrieve queue details.",
        tags={"queues"},
        annotations={"readOnlyHint": True},
    )
    async def get_queue(queue_id: int) -> Queue:
        return await _get_queue(client, queue_id)

    @mcp.tool(
        description="List queues with filters; id supports comma-separated values.",
        tags={"queues"},
        annotations={"readOnlyHint": True},
    )
    async def list_queues(
        id: str | None = None, workspace_id: int | None = None, name: str | None = None
    ) -> list[Queue]:
        return await _list_queues(client, id, workspace_id, name)

    @mcp.tool(
        description="Retrieve queue schema.",
        tags={"queues"},
        annotations={"readOnlyHint": True},
    )
    async def get_queue_schema(queue_id: int) -> Schema:
        return await _get_queue_schema(client, queue_id)

    @mcp.tool(
        description="Retrieve queue engine. Returns None if no engine assigned.",
        tags={"queues"},
        annotations={"readOnlyHint": True},
    )
    async def get_queue_engine(queue_id: int) -> Engine | dict:
        return await _get_queue_engine(client, queue_id)

    @mcp.tool(
        description="Create a queue.",
        tags={"queues", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_queue(
        name: str,
        workspace_id: int,
        schema_id: int,
        engine_id: int | None = None,
        inbox_id: int | None = None,
        connector_id: int | None = None,
        locale: str = "en_GB",
        automation_enabled: bool = False,
        automation_level: str = "never",
        training_enabled: bool = True,
        splitting_screen_feature_flag: bool = False,
    ) -> Queue | dict:
        return await _create_queue(
            client,
            name,
            workspace_id,
            schema_id,
            engine_id,
            inbox_id,
            connector_id,
            locale,
            automation_enabled,
            automation_level,
            training_enabled,
            splitting_screen_feature_flag,
        )

    @mcp.tool(
        description="Update queue settings.",
        tags={"queues", "write"},
        annotations={"readOnlyHint": False},
    )
    async def update_queue(queue_id: int, queue_data: dict) -> Queue | dict:
        return await _update_queue(client, queue_id, queue_data)

    @mcp.tool(
        description="Delete a queue (deletion begins after ~24h); cascades to annotations/documents.",
        tags={"queues", "write"},
        annotations={"readOnlyHint": False, "destructiveHint": True},
    )
    async def delete_queue(queue_id: int) -> dict:
        return await _delete_queue(client, queue_id)

    @mcp.tool(
        description="List template names usable by create_queue_from_template.",
        tags={"queues"},
        annotations={"readOnlyHint": True},
    )
    async def get_queue_template_names() -> list[str]:
        return list(QUEUE_TEMPLATE_NAMES)

    @mcp.tool(
        description="Create a queue from a template (includes schema + engine defaults).",
        tags={"queues", "write"},
        annotations={"readOnlyHint": False},
    )
    async def create_queue_from_template(
        name: str,
        template_name: QueueTemplateName,
        workspace_id: int,
        include_documents: bool = False,
        engine_id: int | None = None,
    ) -> Queue | dict:
        return await _create_queue_from_template(
            client, name, template_name, workspace_id, include_documents, engine_id
        )
