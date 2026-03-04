"""Get operations for engines."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from rossum_api.models.engine import EngineField

if TYPE_CHECKING:
    from rossum_api import AsyncRossumAPIClient

logger = logging.getLogger(__name__)


async def _get_engine_fields(client: AsyncRossumAPIClient, engine_id: int | None = None) -> list[EngineField]:
    logger.debug(f"Retrieving engine fields: engine_id={engine_id}")
    return [engine_field async for engine_field in client.retrieve_engine_fields(engine_id=engine_id)]
