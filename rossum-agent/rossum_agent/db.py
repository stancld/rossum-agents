"""PostgreSQL data access objects for rossum-agent chat history."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path  # noqa: TC003 - used at runtime in save_all_files
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.dialects.postgresql import insert as pg_insert

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)

metadata = sa.MetaData()

chats_table = sa.Table(
    "agent_chats",
    metadata,
    sa.Column("chat_id", sa.Text, primary_key=True),
    sa.Column("user_id", sa.Text, nullable=True, index=True),
    sa.Column("messages", JSONB, nullable=False),
    sa.Column("output_dir", sa.Text, nullable=True),
    sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'")),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
    sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
)

chat_files_table = sa.Table(
    "agent_chat_files",
    metadata,
    sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
    sa.Column(
        "chat_id",
        sa.Text,
        sa.ForeignKey("agent_chats.chat_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    sa.Column("filename", sa.Text, nullable=False),
    sa.Column("content", BYTEA, nullable=False),
    sa.Column("size", sa.Integer, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
)


class ChatHistoryDAO:
    """DAO for agent chat history tables — durable audit store for chat sessions and files."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.chats = chats_table
        self.chat_files = chat_files_table

    async def save_chat(
        self,
        chat_id: str,
        user_id: str | None,
        messages: list[dict[str, Any]],
        output_dir: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Upsert a chat record."""
        stmt = pg_insert(self.chats).values(
            chat_id=chat_id,
            user_id=user_id,
            messages=messages,
            output_dir=output_dir,
            metadata=metadata or {},
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["chat_id"],
            set_={
                "messages": stmt.excluded.messages,
                "output_dir": stmt.excluded.output_dir,
                "metadata": stmt.excluded.metadata,
                "updated_at": sa.func.now(),
            },
        )
        async with self.engine.begin() as conn:
            await conn.execute(stmt)

    async def save_file(self, chat_id: str, filename: str, content: bytes) -> None:
        """Insert or replace a file for a chat."""
        # Delete existing file with same name, then insert
        async with self.engine.begin() as conn:
            await conn.execute(
                self.chat_files.delete().where(
                    (self.chat_files.c.chat_id == chat_id) & (self.chat_files.c.filename == filename)
                )
            )
            await conn.execute(
                self.chat_files.insert().values(
                    id=uuid.uuid4(),
                    chat_id=chat_id,
                    filename=filename,
                    content=content,
                    size=len(content),
                )
            )

    async def save_feedback(self, chat_id: str, turn_index: int, is_positive: bool) -> bool:
        """Set feedback on a specific message turn in the JSONB messages array."""
        # Use jsonb_set to update the feedback key on the specific message
        stmt = (
            self.chats.update()
            .where(self.chats.c.chat_id == chat_id)
            .where(sa.func.jsonb_array_length(self.chats.c.messages) > turn_index)
            .values(
                messages=sa.func.jsonb_set(
                    self.chats.c.messages,
                    sa.text("'{%d,feedback}'" % turn_index),
                    sa.text(f"'{str(is_positive).lower()}'::jsonb"),
                ),
                updated_at=sa.func.now(),
            )
        )
        async with self.engine.begin() as conn:
            result = await conn.execute(stmt)
            return result.rowcount > 0

    async def delete_feedback(self, chat_id: str, turn_index: int) -> bool:
        """Remove feedback from a specific message turn."""
        stmt = (
            self.chats.update()
            .where(self.chats.c.chat_id == chat_id)
            .where(sa.func.jsonb_array_length(self.chats.c.messages) > turn_index)
            .values(
                messages=sa.text("messages #- '{%d,feedback}'" % turn_index),
                updated_at=sa.func.now(),
            )
        )
        async with self.engine.begin() as conn:
            result = await conn.execute(stmt)
            return result.rowcount > 0

    async def save_all_files(self, chat_id: str, output_dir: Path) -> int:
        """Save all files from a directory to the database."""
        if not output_dir.exists() or not output_dir.is_dir():  # noqa: ASYNC240
            return 0
        saved = 0
        for file_path in output_dir.iterdir():  # noqa: ASYNC240
            if file_path.is_file():
                try:
                    await self.save_file(chat_id, file_path.name, file_path.read_bytes())
                    saved += 1
                except Exception as e:
                    logger.error(f"Failed to save file {file_path.name} to PostgreSQL: {e}")
        return saved

    async def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat and its files (cascade)."""
        async with self.engine.begin() as conn:
            result = await conn.execute(self.chats.delete().where(self.chats.c.chat_id == chat_id))
            return result.rowcount > 0
