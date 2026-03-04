from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastmcp.exceptions import ToolError
from rossum_api.models.schema import Schema

from rossum_mcp.tools.validation import sanitize_schema_content

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _create_schema(client: AsyncRossumAPIClient, name: str, content: list[dict]) -> Schema:
    if not content:
        raise ToolError("Cannot create schema with empty content")

    logger.debug(f"Creating schema: name={name}")
    sanitized_content = sanitize_schema_content(content)
    schema_data = {"name": name, "content": sanitized_content}
    schema: Schema = await client.create_new_schema(schema_data)
    return schema
