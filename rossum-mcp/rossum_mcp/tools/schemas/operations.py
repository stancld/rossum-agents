"""Schema CRUD operations for Rossum MCP Server."""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import asdict, is_dataclass
from typing import TYPE_CHECKING, Any

from rossum_api import APIClientError
from rossum_api.domain_logic.resources import Resource
from rossum_api.models.schema import Schema

from rossum_mcp.tools.base import (
    TRUNCATED_MARKER,
    delete_resource,
    extract_id_from_url,
    graceful_list,
    is_read_write_mode,
)
from rossum_mcp.tools.schemas.models import SchemaNode, SchemaNodeUpdate  # noqa: TC001 - needed at runtime for FastMCP
from rossum_mcp.tools.schemas.patching import PatchOperation, apply_schema_patch
from rossum_mcp.tools.schemas.pruning import (
    _collect_all_field_ids,
    _collect_ancestor_ids,
    _extract_schema_tree,
    _remove_fields_from_content,
)
from rossum_mcp.tools.schemas.validation import sanitize_schema_content

if TYPE_CHECKING:
    from collections.abc import Callable

    from rossum_api import AsyncRossumAPIClient

MAX_RETRIES_ON_PRECONDITION_FAILED = 5

logger = logging.getLogger(__name__)


async def _update_schema_with_retry(
    client: AsyncRossumAPIClient,
    schema_id: int,
    prepare_content: Callable[[list], list | None],
) -> tuple[list, list | None]:
    """Fetch schema, transform content, update with retry on 412 Precondition Failed.

    prepare_content receives the current content list and returns the transformed content,
    or None to indicate no changes are needed.

    Returns (original_content, transformed_content). transformed_content is None
    when prepare_content returned None.
    """
    for attempt in range(MAX_RETRIES_ON_PRECONDITION_FAILED):
        current_schema: dict = await client._http_client.request_json("GET", f"schemas/{schema_id}")
        content = current_schema.get("content", [])
        if not isinstance(content, list):
            raise ValueError("Unexpected schema content format")

        new_content = prepare_content(content)
        if new_content is None:
            return content, None

        if not new_content:
            raise ValueError("Cannot update schema with empty content — this would remove all fields")

        sanitized = sanitize_schema_content(new_content)
        try:
            await client._http_client.update(Resource.Schema, schema_id, {"content": sanitized})
            return content, new_content
        except APIClientError as e:
            if e.status_code == 412 and attempt < MAX_RETRIES_ON_PRECONDITION_FAILED - 1:
                logger.warning(
                    f"Schema {schema_id} was modified concurrently (412 Precondition Failed), "
                    f"retrying ({attempt + 1}/{MAX_RETRIES_ON_PRECONDITION_FAILED})..."
                )
                await asyncio.sleep(0.5 * (attempt + 1) + random.uniform(0, 0.5))
                continue
            raise
    raise RuntimeError("Unreachable")


def _truncate_schema_for_list(schema: Schema) -> Schema:
    """Truncate content field in schema to save context in list responses."""
    from dataclasses import replace  # noqa: PLC0415 - avoid circular import with models

    return replace(schema, content=TRUNCATED_MARKER)


async def get_schema(client: AsyncRossumAPIClient, schema_id: int) -> Schema | dict:
    try:
        schema: Schema = await client.retrieve_schema(schema_id)
        return schema
    except APIClientError as e:
        if e.status_code == 404:
            return {"error": f"Schema {schema_id} not found"}
        raise


async def list_schemas(
    client: AsyncRossumAPIClient, name: str | None = None, queue_id: int | None = None
) -> list[Schema]:
    logger.debug(f"Listing schemas: name={name}, queue_id={queue_id}")
    filters: dict = {}
    if name is not None:
        filters["name"] = name
    if queue_id is not None:
        filters["queue"] = queue_id

    result = await graceful_list(client, Resource.Schema, "schema", **filters)
    return [_truncate_schema_for_list(schema) for schema in result.items]


async def update_schema(client: AsyncRossumAPIClient, schema_id: int, schema_data: dict) -> Schema | dict:
    if not is_read_write_mode():
        return {"error": "update_schema is not available in read-only mode"}

    logger.debug(f"Updating schema: schema_id={schema_id}")
    if "content" in schema_data and isinstance(schema_data["content"], list):
        if not schema_data["content"]:
            return {"error": "Cannot update schema with empty content — this would remove all fields"}
        schema_data = {**schema_data, "content": sanitize_schema_content(schema_data["content"])}
    await client._http_client.update(Resource.Schema, schema_id, schema_data)
    updated_schema: Schema = await client.retrieve_schema(schema_id)
    return updated_schema


async def create_schema(client: AsyncRossumAPIClient, name: str, content: list[dict]) -> Schema | dict:
    if not is_read_write_mode():
        return {"error": "create_schema is not available in read-only mode"}

    if not content:
        return {"error": "Cannot create schema with empty content"}

    logger.debug(f"Creating schema: name={name}")
    sanitized_content = sanitize_schema_content(content)
    schema_data = {"name": name, "content": sanitized_content}
    schema: Schema = await client.create_new_schema(schema_data)
    return schema


async def patch_schema(
    client: AsyncRossumAPIClient,
    schema_id: int,
    operation: PatchOperation,
    node_id: str,
    node_data: SchemaNode | SchemaNodeUpdate | None = None,
    parent_id: str | None = None,
    position: int | None = None,
) -> Schema | dict:
    if not is_read_write_mode():
        return {"error": "patch_schema is not available in read-only mode"}

    if operation not in ("add", "update", "remove"):
        return {"error": f"Invalid operation '{operation}'. Must be 'add', 'update', or 'remove'."}

    logger.debug(f"Patching schema: schema_id={schema_id}, operation={operation}, node_id={node_id}")

    node_data_dict: dict | None = None
    if node_data is not None:
        if isinstance(node_data, dict):
            node_data_dict = node_data
        elif hasattr(node_data, "to_dict"):
            node_data_dict = node_data.to_dict()
        else:
            node_data_dict = asdict(node_data)

    def prepare(content: list) -> list:
        return apply_schema_patch(
            content=content,
            operation=operation,
            node_id=node_id,
            node_data=node_data_dict,
            parent_id=parent_id,
            position=position,
        )

    try:
        await _update_schema_with_retry(client, schema_id, prepare)
    except ValueError as e:
        return {"error": str(e)}

    return await client.retrieve_schema(schema_id)


async def get_schema_tree_structure(
    client: AsyncRossumAPIClient, schema_id: int | None = None, queue_id: int | None = None
) -> list[dict] | dict:
    if schema_id is None and queue_id is None:
        return {"error": "Provide schema_id or queue_id"}
    if schema_id is not None and queue_id is not None:
        return {"error": "Provide schema_id or queue_id, not both"}
    if queue_id:
        queue = await client.retrieve_queue(queue_id)
        schema_id = extract_id_from_url(queue.schema)
    schema = await get_schema(client, schema_id)  # type: ignore[arg-type]
    if isinstance(schema, dict):
        return schema
    content_dicts: list[dict[str, Any]] = [
        asdict(section) if is_dataclass(section) else dict(section)  # type: ignore[arg-type]
        for section in schema.content
    ]
    return _extract_schema_tree(content_dicts)


async def prune_schema_fields(
    client: AsyncRossumAPIClient,
    schema_id: int,
    fields_to_keep: list[str] | None = None,
    fields_to_remove: list[str] | None = None,
) -> dict:
    if not is_read_write_mode():
        return {"error": "prune_schema_fields is not available in read-only mode"}

    if fields_to_keep and fields_to_remove:
        return {"error": "Specify fields_to_keep OR fields_to_remove, not both"}
    if not fields_to_keep and not fields_to_remove:
        return {"error": "Must specify fields_to_keep or fields_to_remove"}

    def prepare(content: list) -> list | None:
        all_ids = _collect_all_field_ids(content)
        section_ids = {s.get("id") for s in content if s.get("category") == "section"}

        if fields_to_keep:
            fields_to_keep_set = set(fields_to_keep) | section_ids
            ancestor_ids = _collect_ancestor_ids(content, fields_to_keep_set)
            fields_to_keep_set |= ancestor_ids
            remove_set = all_ids - fields_to_keep_set
        else:
            remove_set = set(fields_to_remove) - section_ids  # type: ignore[arg-type]

        if not remove_set:
            return None

        pruned_content, _ = _remove_fields_from_content(content, remove_set)
        return pruned_content

    try:
        original_content, result_content = await _update_schema_with_retry(client, schema_id, prepare)
    except ValueError as e:
        return {"error": str(e)}

    if result_content is None:
        all_ids = _collect_all_field_ids(original_content)
        return {"removed_fields": [], "remaining_fields": sorted(all_ids)}

    all_ids = _collect_all_field_ids(original_content)
    remaining_ids = _collect_all_field_ids(result_content)
    return {"removed_fields": sorted(all_ids - remaining_ids), "remaining_fields": sorted(remaining_ids)}


async def delete_schema(client: AsyncRossumAPIClient, schema_id: int) -> dict:
    return await delete_resource("schema", schema_id, client.delete_schema)
