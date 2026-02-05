"""Health check endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from rossum_agent.api.dependencies import get_chat_service
from rossum_agent.api.models.schemas import HealthResponse
from rossum_agent.api.services.chat_service import ChatService

router = APIRouter(tags=["health"])

VERSION = "0.2.0"


@router.get("/health", response_model=HealthResponse)
async def health_check(
    chat_service: Annotated[ChatService, Depends(get_chat_service)],
) -> HealthResponse:
    """Check API health and dependencies."""
    redis_connected = chat_service.is_connected()

    return HealthResponse(
        status="healthy" if redis_connected else "unhealthy", redis_connected=redis_connected, version=VERSION
    )
