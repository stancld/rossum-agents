"""PostgreSQL data access objects for rossum-agent chat history."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

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
