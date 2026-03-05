"""Initial schema: agent_chats and agent_chat_files

Revision ID: 0001
Revises:
Create Date: 2026-03-05

"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_chats",
        sa.Column("chat_id", sa.Text, primary_key=True),
        sa.Column("user_id", sa.Text, nullable=True),
        sa.Column("messages", JSONB, nullable=False),
        sa.Column("output_dir", sa.Text, nullable=True),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_chats_user_id", "agent_chats", ["user_id"])

    op.create_table(
        "agent_chat_files",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chat_id",
            sa.Text,
            sa.ForeignKey("agent_chats.chat_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("content", BYTEA, nullable=False),
        sa.Column("size", sa.Integer, nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.create_index("ix_agent_chat_files_chat_id", "agent_chat_files", ["chat_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_chat_files_chat_id", table_name="agent_chat_files")
    op.drop_table("agent_chat_files")
    op.drop_index("ix_agent_chats_user_id", table_name="agent_chats")
    op.drop_table("agent_chats")
