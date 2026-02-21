"""Chat session CRUD endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from rossum_agent.api.dependencies import RossumCredentials, get_chat_service, get_validated_credentials
from rossum_agent.api.models.schemas import (
    ChatDetail,
    ChatListResponse,
    ChatResponse,
    CreateChatRequest,
    DeleteResponse,
)
from rossum_agent.api.services.chat_service import ChatService

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_chat(
    request: Request,
    body: CreateChatRequest | None = None,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)] = None,  # type: ignore[assignment]
    chat_service: Annotated[ChatService, Depends(get_chat_service)] = None,  # type: ignore[assignment]
) -> ChatResponse:
    """Create a new chat session."""
    mcp_mode = body.mcp_mode if body else "read-only"
    persona = body.persona if body else "default"
    return chat_service.create_chat(user_id=credentials.user_id, mcp_mode=mcp_mode, persona=persona)


@router.get("", response_model=ChatListResponse)
async def list_chats(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)] = None,  # type: ignore[assignment]
    chat_service: Annotated[ChatService, Depends(get_chat_service)] = None,  # type: ignore[assignment]
) -> ChatListResponse:
    """List chat sessions for the authenticated user."""
    return chat_service.list_chats(user_id=credentials.user_id, limit=limit, offset=offset)


@router.get("/{chat_id}", response_model=ChatDetail)
async def get_chat(
    request: Request,
    chat_id: str,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)] = None,  # type: ignore[assignment]
    chat_service: Annotated[ChatService, Depends(get_chat_service)] = None,  # type: ignore[assignment]
) -> ChatDetail:
    """Get detailed information about a chat session."""
    chat = chat_service.get_chat(user_id=credentials.user_id, chat_id=chat_id)

    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    return chat


@router.delete("/{chat_id}", response_model=DeleteResponse)
async def delete_chat(
    request: Request,
    chat_id: str,
    credentials: Annotated[RossumCredentials, Depends(get_validated_credentials)] = None,  # type: ignore[assignment]
    chat_service: Annotated[ChatService, Depends(get_chat_service)] = None,  # type: ignore[assignment]
) -> DeleteResponse:
    """Delete a chat session."""
    if not chat_service.chat_exists(credentials.user_id, chat_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Chat {chat_id} not found")

    deleted = chat_service.delete_chat(user_id=credentials.user_id, chat_id=chat_id)

    return DeleteResponse(deleted=deleted)
