"""Update operations for engines."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from rossum_api.domain_logic.resources import Resource
from rossum_api.models.engine import Engine

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

    from rossum_mcp.tools.update.models import EngineUpdateData

logger = logging.getLogger(__name__)


async def _update_engine(client: AsyncRossumAPIClient, engine_id: int, engine_data: EngineUpdateData) -> Engine | dict:
    logger.debug(f"Updating engine: engine_id={engine_id}, data={engine_data}")
    updated_engine_data = await client._http_client.update(Resource.Engine, engine_id, dict(engine_data))
    return cast("Engine", client._deserializer(Resource.Engine, updated_engine_data))
