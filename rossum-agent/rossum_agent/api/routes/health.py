"""Health check endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from rossum_agent.api.dependencies import get_chat_service
from rossum_agent.api.models.schemas import HealthResponse
from rossum_agent.api.services.chat_service import ChatService
from rossum_agent.storage import get_storage_backend

router = APIRouter(tags=["health"])

VERSION = "0.2.0"


@router.get("/health", response_model=HealthResponse)
async def health_check(
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> HealthResponse:
    """Check API health and dependencies."""
    storage_connected = chat_service.is_connected()

    return HealthResponse(
        status="healthy" if storage_connected else "unhealthy",
        storage_connected=storage_connected,
        storage_backend=get_storage_backend(),
        version=VERSION,
    )
