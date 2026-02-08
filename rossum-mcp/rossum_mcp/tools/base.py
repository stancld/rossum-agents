from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rossum_api.domain_logic.resources import Resource

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import Any

    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


@dataclass
class GracefulListResult[T]:
    items: list[T]
    skipped_ids: list[int | str] = field(default_factory=list)


BASE_URL = os.environ.get("ROSSUM_API_BASE_URL", "").rstrip("/")

# Marker used to indicate omitted fields in list responses
TRUNCATED_MARKER = "<omitted>"

VALID_MODES = ("read-only", "read-write")

_mcp_mode = os.environ.get("ROSSUM_MCP_MODE", "read-write").lower()
if _mcp_mode not in VALID_MODES:
    raise ValueError(f"Invalid ROSSUM_MCP_MODE: {_mcp_mode}. Must be one of: {VALID_MODES}")


def get_mcp_mode() -> str:
    """Return the current MCP mode."""
    return _mcp_mode


def set_mcp_mode(mode: str) -> None:
    """Set the MCP mode (case-insensitive)."""
    global _mcp_mode
    normalized = mode.lower()
    if normalized not in VALID_MODES:
        raise ValueError(f"Invalid mode '{mode}'. Must be one of: {VALID_MODES}")
    _mcp_mode = normalized


def build_resource_url(resource_type: str, resource_id: int) -> str:
    """Build a full URL for a Rossum API resource."""
    return f"{BASE_URL}/{resource_type}/{resource_id}"


def is_read_write_mode() -> bool:
    """Check if server is in read-write mode."""
    return _mcp_mode == "read-write"


def truncate_dict_fields(data: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    """Truncate specified fields in a dictionary to save context.

    Returns a new dictionary with specified fields replaced by TRUNCATED_MARKER.
    """
    if not data:
        return data

    result = dict(data)
    for field_name in fields:
        if field_name in result:
            result[field_name] = TRUNCATED_MARKER
    return result


async def graceful_list(
    client: AsyncRossumAPIClient,
    resource: Resource,
    resource_label: str,
    max_items: int | None = None,
    **filters: Any,
) -> GracefulListResult:
    """List resources gracefully, skipping items that fail deserialization.

    Uses _http_client.fetch_all directly so that a single broken item
    does not terminate the entire iteration (the high-level client generators
    die on the first deserialization error).
    """
    items: list[Any] = []
    skipped_ids: list[int | str] = []
    async for raw in client._http_client.fetch_all(resource, **filters):
        try:
            item = client._deserializer(resource, raw)
            items.append(item)
        except asyncio.CancelledError:
            raise
        except Exception:
            item_id = raw.get("id", "unknown")
            skipped_ids.append(item_id)
            logger.warning("Failed to deserialize %s (id=%s), skipping", resource_label, item_id)
        if max_items is not None and len(items) >= max_items:
            break
    if skipped_ids:
        logger.warning("Skipped %d %s item(s) that failed to deserialize", len(skipped_ids), resource_label)
    return GracefulListResult(items=items, skipped_ids=skipped_ids)


async def delete_resource(
    resource_type: str,
    resource_id: int,
    delete_fn: Callable[[int], Awaitable[None]],
    success_message: str | None = None,
) -> dict:
    """Generic delete operation with read-only mode check.

    Args:
        resource_type: Name of the resource (e.g., "queue", "workspace")
        resource_id: ID of the resource to delete
        delete_fn: Async function that performs the deletion
        success_message: Custom success message. If None, uses default format.

    Returns:
        Dict with "message" on success or "error" in read-only mode.
    """
    tool_name = f"delete_{resource_type}"
    if not is_read_write_mode():
        return {"error": f"{tool_name} is not available in read-only mode"}

    logger.debug(f"Deleting {resource_type}: {resource_type}_id={resource_id}")
    await delete_fn(resource_id)

    if success_message is None:
        success_message = f"{resource_type.title()} {resource_id} deleted successfully"
    return {"message": success_message}
