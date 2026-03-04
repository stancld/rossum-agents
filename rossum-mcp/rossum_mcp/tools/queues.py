from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, TypedDict, cast, get_args

from rossum_api import APIClientError
from rossum_api.domain_logic.resources import Resource
from rossum_api.models import deserialize_default
from rossum_api.models.engine import Engine
from rossum_api.models.queue import Queue

from rossum_mcp.tools.base import (
    build_filters,
    build_resource_url,
    delete_resource,
    extract_id_from_url,
    filter_by_name_regex,
    graceful_list,
)
from rossum_mcp.tools.resource_tracking import embed_tracked_resources, track_resource

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


@dataclass
class QueueListItem:
    """Queue summary for list responses (settings omitted to save context)."""

    id: int
    name: str
    url: str
    workspace: str | None = None
    schema: str | None = None
    inbox: str | None = None
    connector: str | None = None
    automation_enabled: bool = False
    automation_level: str = "never"
    status: str | None = None
    counts: dict[str, int] | None = None
    settings: str = "<omitted>"


class QueueUpdateData(TypedDict, total=False):
    name: str
    automation_enabled: bool
    automation_level: str
    locale: str
    metadata: dict[str, Any]
    settings: dict[str, Any]
    engine: str
    dedicated_engine: str
    training_enabled: bool
    webhooks: list[str]
    hooks: list[str]
    default_score_threshold: float
    session_timeout: str
    document_lifetime: str | None
    delete_after: str | None
    schema: str
    workspace: str
    connector: str | None
    inbox: str | None


def _queue_to_list_item(queue: Queue) -> QueueListItem:
    return QueueListItem(
        id=queue.id,
        name=queue.name,
        url=queue.url,
        workspace=queue.workspace,
        schema=queue.schema,
        inbox=queue.inbox,
        connector=queue.connector,
        automation_enabled=queue.automation_enabled,
        automation_level=queue.automation_level,
        status=queue.status,
        counts=queue.counts or None,
    )


async def _get_queue(client: AsyncRossumAPIClient, queue_id: int) -> Queue:
    logger.debug(f"Retrieving queue: queue_id={queue_id}")
    queue: Queue = await client.retrieve_queue(queue_id)
    return queue


async def _list_queues(
    client: AsyncRossumAPIClient,
    id: str | None = None,
    workspace_id: int | None = None,
    name: str | None = None,
    use_regex: bool = False,
) -> list[QueueListItem]:
    logger.debug(f"Listing queues: id={id}, workspace_id={workspace_id}, name={name}")
    filters = build_filters(id=id, workspace=workspace_id, name=None if use_regex else name)
    result = await graceful_list(client, Resource.Queue, "queue", **filters)
    items = [_queue_to_list_item(queue) for queue in result.items]
    return filter_by_name_regex(items, name, use_regex)


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


def _validate_queue_column_settings(queue_data: QueueUpdateData) -> str | None:
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


async def _update_queue(client: AsyncRossumAPIClient, queue_id: int, queue_data: QueueUpdateData) -> Queue | dict:
    validation_error = _validate_queue_column_settings(queue_data)
    if validation_error:
        return {"error": validation_error}

    logger.debug(f"Updating queue: queue_id={queue_id}, data={queue_data}")
    updated_queue_data = await client._http_client.update(Resource.Queue, queue_id, dict(queue_data))
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


async def _list_queue_template_names() -> list[str]:
    return list(QUEUE_TEMPLATE_NAMES)


def _get_engine_url(queue: Queue) -> str | None:
    """Extract the engine URL from a queue, checking all engine fields."""
    for attr in ("dedicated_engine", "generic_engine", "engine"):
        value = getattr(queue, attr, None)
        if value and isinstance(value, str):
            return value
    return None


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
    queue = cast("Queue", client._deserializer(Resource.Queue, response))

    tracked: list[dict] = []

    # Track the schema created as a side effect
    try:
        schema_id = extract_id_from_url(queue.schema)
        schema = await client.retrieve_schema(schema_id)
        track_resource(tracked, "schema", schema_id, schema)
    except Exception:
        logger.warning(f"Failed to fetch schema for tracked resource (queue={queue.id})", exc_info=True)

    # Track the engine created as a side effect
    engine_url = _get_engine_url(queue)
    if engine_url:
        try:
            eid = extract_id_from_url(engine_url)
            engine = await client.retrieve_engine(eid)
            track_resource(tracked, "engine", eid, engine)
        except Exception:
            logger.warning(f"Failed to fetch engine for tracked resource (queue={queue.id})", exc_info=True)

    return embed_tracked_resources(queue, tracked)


def register_queue_tools(mcp: FastMCP, client: AsyncRossumAPIClient) -> None:
    @mcp.tool(
        description="Update queue settings.",
        tags={"queues", "write"},
        annotations={"readOnlyHint": False},
    )
    async def update_queue(queue_id: int, queue_data: QueueUpdateData) -> Queue | dict:
        return await _update_queue(client, queue_id, queue_data)
