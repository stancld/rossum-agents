"""Chat service for managing chat sessions."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import secrets
from collections.abc import Coroutine
from typing import TYPE_CHECKING

from rossum_agent.api.models.schemas import (
    ChatDetail,
    ChatListResponse,
    ChatResponse,
    ChatSummary,
    FileInfo,
    Message,
)
from rossum_agent.redis_storage import ChatData, ChatMetadata, RedisStorage

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any, Literal

    from rossum_agent.db import ChatHistoryDAO

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing chat sessions.

    Wraps RedisStorage to provide chat CRUD operations with proper
    data transformation to/from API schemas. Optionally writes to
    PostgreSQL (via ChatHistoryDAO) as a durable audit store.
    """

    def __init__(
        self,
        redis_storage: RedisStorage | None = None,
        pg_dao: ChatHistoryDAO | None = None,
    ) -> None:
        self._storage = redis_storage or RedisStorage()
        self._pg_dao = pg_dao
        self._pg_tasks: set[asyncio.Task] = set()

    @property
    def storage(self) -> RedisStorage:
        """Get the underlying RedisStorage instance."""
        return self._storage

    def _schedule_pg(self, coro: Coroutine[None, None, None]) -> None:
        """Fire-and-forget an async PG write. Errors are logged, never raised."""
        if self._pg_dao is None:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        async def _safe():
            try:
                await coro
            except Exception as e:
                logger.error(f"PostgreSQL write failed: {e}", exc_info=True)

        task = loop.create_task(_safe())
        self._pg_tasks.add(task)
        task.add_done_callback(self._pg_tasks.discard)

    async def drain_pg_tasks(self) -> None:
        """Await all pending PostgreSQL background tasks. Call during shutdown."""
        if self._pg_tasks:
            await asyncio.gather(*self._pg_tasks, return_exceptions=True)

    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._storage.is_connected()

    def create_chat(
        self,
        user_id: str | None,
        mcp_mode: Literal["read-only", "read-write"] = "read-only",
        persona: Literal["default", "cautious"] = "default",
    ) -> ChatResponse:
        timestamp = dt.datetime.now(dt.UTC)
        timestamp_str = timestamp.strftime("%Y%m%d%H%M%S")
        unique_suffix = secrets.token_hex(4)
        chat_id = f"chat_{timestamp_str}_{unique_suffix}"

        initial_messages: list[dict[str, Any]] = []
        metadata = ChatMetadata(mcp_mode=mcp_mode, persona=persona)
        self._storage.save_chat(user_id, chat_id, initial_messages, metadata=metadata)
        if self._pg_dao:
            self._schedule_pg(self._pg_dao.save_chat(chat_id, user_id, initial_messages, metadata=metadata.to_dict()))

        logger.info(
            f"Created chat {chat_id} for user {user_id or 'shared'} with mcp_mode={mcp_mode}, persona={persona}"
        )
        return ChatResponse(chat_id=chat_id, created_at=timestamp)

    def list_chats(self, user_id: str | None, limit: int = 50, offset: int = 0) -> ChatListResponse:
        all_chats = self._storage.list_all_chats(user_id)

        paginated = all_chats[offset : offset + limit]
        chats = [
            ChatSummary(
                chat_id=chat["chat_id"],
                timestamp=chat["timestamp"],
                message_count=chat["message_count"],
                first_message=chat["first_message"],
                preview=chat.get("preview"),
                summary=chat.get("summary"),
            )
            for chat in paginated
        ]

        return ChatListResponse(chats=chats, total=len(all_chats), limit=limit, offset=offset)

    def get_chat(self, user_id: str | None, chat_id: str) -> ChatDetail | None:
        if (chat_data := self._storage.load_chat(user_id, chat_id)) is None:
            return None

        messages = []
        for msg in chat_data.messages:
            msg_type = msg.get("type")
            role = msg.get("role")

            if msg_type == "task_step":
                task_content = msg.get("task", "")
                messages.append(Message(role="user", content=task_content, feedback=msg.get("feedback")))
            elif msg_type == "memory_step":
                text = msg.get("text")
                if text:
                    messages.append(Message(role="assistant", content=text, feedback=msg.get("feedback")))
            elif role in ("user", "assistant"):
                messages.append(Message(role=role, content=msg.get("content", ""), feedback=msg.get("feedback")))

        files_data = self._storage.list_files(chat_id)
        files = [FileInfo(filename=f["filename"], size=f["size"], timestamp=f["timestamp"]) for f in files_data]

        timestamp_str = chat_id.split("_")[1]
        created_at = dt.datetime.strptime(timestamp_str, "%Y%m%d%H%M%S").replace(tzinfo=dt.UTC)

        return ChatDetail(chat_id=chat_id, messages=messages, created_at=created_at, files=files)

    def delete_chat(self, user_id: str | None, chat_id: str) -> bool:
        self._storage.delete_all_files(chat_id)
        deleted = self._storage.delete_chat(user_id, chat_id)
        if self._pg_dao:
            self._schedule_pg(self._pg_dao.delete_chat(chat_id))
        logger.info(f"Deleted chat {chat_id} for user {user_id or 'shared'}: {deleted}")
        return deleted

    def chat_exists(self, user_id: str | None, chat_id: str) -> bool:
        return self._storage.chat_exists(user_id, chat_id)

    def get_messages(self, user_id: str | None, chat_id: str) -> list[dict[str, Any]] | None:
        if (chat_data := self._storage.load_chat(user_id, chat_id)) is None:
            return None
        return chat_data.messages

    def get_chat_data(self, user_id: str | None, chat_id: str) -> ChatData | None:
        return self._storage.load_chat(user_id, chat_id)

    def save_messages(
        self,
        user_id: str | None,
        chat_id: str,
        messages: list[dict[str, Any]],
        output_dir: Path | None = None,
        metadata: ChatMetadata | None = None,
    ) -> bool:
        result = self._storage.save_chat(user_id, chat_id, messages, output_dir, metadata)
        if self._pg_dao:
            self._schedule_pg(self._pg_save_messages(chat_id, user_id, messages, output_dir, metadata))
        return result

    async def _pg_save_messages(
        self,
        chat_id: str,
        user_id: str | None,
        messages: list[dict[str, Any]],
        output_dir: Path | None,
        metadata: ChatMetadata | None,
    ) -> None:
        assert self._pg_dao is not None
        await self._pg_dao.save_chat(
            chat_id,
            user_id,
            messages,
            output_dir=str(output_dir) if output_dir else None,
            metadata=metadata.to_dict() if metadata else {},
        )
        if output_dir:
            await self._pg_dao.save_all_files(chat_id, output_dir)

    def save_feedback(self, user_id: str | None, chat_id: str, turn_index: int, is_positive: bool) -> bool:
        result = self._storage.save_feedback(user_id, chat_id, turn_index, is_positive)
        if self._pg_dao:
            self._schedule_pg(self._pg_dao.save_feedback(chat_id, turn_index, is_positive))
        return result

    def get_feedback(self, user_id: str | None, chat_id: str) -> dict[int, bool]:
        return self._storage.get_feedback(user_id, chat_id)

    def delete_feedback(self, user_id: str | None, chat_id: str, turn_index: int) -> bool:
        result = self._storage.delete_feedback(user_id, chat_id, turn_index)
        if self._pg_dao:
            self._schedule_pg(self._pg_dao.delete_feedback(chat_id, turn_index))
        return result
