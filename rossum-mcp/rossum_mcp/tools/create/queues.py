from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, cast

from fastmcp.exceptions import ToolError
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.queue import Queue

from rossum_mcp.tools.base import build_resource_url, extract_id_from_url
from rossum_mcp.tools.models import QUEUE_TEMPLATE_NAMES, QueueTemplateName
from rossum_mcp.tools.resource_tracking import embed_tracked_resources, track_resource

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

    from rossum_mcp.tools.models import AutomationLevel, QueueLocale

logger = logging.getLogger(__name__)


async def _create_queue(
    client: AsyncRossumAPIClient,
    base_url: str,
    name: str,
    workspace_id: int,
    schema_id: int,
    engine_id: int | None = None,
    inbox_id: int | None = None,
    connector_id: int | None = None,
    locale: QueueLocale = "en_GB",
    automation_enabled: bool = False,
    automation_level: AutomationLevel = "never",
    training_enabled: bool = True,
    splitting_screen_feature_flag: bool = False,
) -> Queue:
    logger.debug(
        f"Creating queue: name={name}, workspace_id={workspace_id}, schema_id={schema_id}, engine_id={engine_id}"
    )

    queue_data: dict = {
        "name": name,
        "workspace": build_resource_url(base_url, "workspaces", workspace_id),
        "schema": build_resource_url(base_url, "schemas", schema_id),
        "locale": locale,
        "automation_enabled": automation_enabled,
        "automation_level": automation_level,
        "training_enabled": training_enabled,
    }

    if engine_id is not None:
        queue_data["engine"] = build_resource_url(base_url, "engines", engine_id)
    if inbox_id is not None:
        queue_data["inbox"] = build_resource_url(base_url, "inboxes", inbox_id)
    if connector_id is not None:
        queue_data["connector"] = build_resource_url(base_url, "connectors", connector_id)
    if splitting_screen_feature_flag:
        if os.environ.get("SPLITTING_SCREEN_FLAG_NAME") and os.environ.get("SPLITTING_SCREEN_FLAG_VALUE"):
            queue_data["settings"] = {
                os.environ["SPLITTING_SCREEN_FLAG_NAME"]: os.environ["SPLITTING_SCREEN_FLAG_VALUE"]
            }
        else:
            raise ToolError(
                "splitting_screen_feature_flag requested but SPLITTING_SCREEN_FLAG_NAME "
                "and/or SPLITTING_SCREEN_FLAG_VALUE environment variables are not set"
            )

    queue: Queue = await client.create_new_queue(queue_data)
    return queue


def _get_engine_url(queue: Queue) -> str | None:
    for attr in ("dedicated_engine", "generic_engine", "engine"):
        value = getattr(queue, attr, None)
        if value and isinstance(value, str):
            return value
    return None


async def _create_queue_from_template(
    client: AsyncRossumAPIClient,
    base_url: str,
    name: str,
    template_name: QueueTemplateName,
    workspace_id: int,
    include_documents: bool = False,
    engine_id: int | None = None,
) -> Queue:
    if template_name not in QUEUE_TEMPLATE_NAMES:
        raise ToolError(f"Invalid template_name: '{template_name}'. Available templates: {QUEUE_TEMPLATE_NAMES}")

    logger.debug(
        f"Creating queue from template: name={name}, template_name={template_name}, workspace_id={workspace_id}"
    )

    payload: dict = {
        "name": name,
        "template_name": template_name,
        "workspace": build_resource_url(base_url, "workspaces", workspace_id),
        "include_documents": include_documents,
    }

    if engine_id is not None:
        payload["engine"] = build_resource_url(base_url, "engines", engine_id)

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
