"""Tests for rossum_agent.db module."""

from __future__ import annotations

from unittest.mock import MagicMock

import sqlalchemy as sa
from rossum_agent.db import ChatHistoryDAO, chat_files_table, chats_table, metadata
from sqlalchemy.dialects.postgresql import BYTEA, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class TestChatsTable:
    def test_table_name(self):
        assert chats_table.name == "agent_chats"

    def test_table_registered_in_metadata(self):
        assert "agent_chats" in metadata.tables

    def test_chat_id_column(self):
        col = chats_table.c["chat_id"]
        assert isinstance(col.type, sa.Text)
        assert col.primary_key

    def test_user_id_column(self):
        col = chats_table.c["user_id"]
        assert isinstance(col.type, sa.Text)
        assert col.nullable

    def test_messages_column(self):
        col = chats_table.c["messages"]
        assert isinstance(col.type, JSONB)
        assert not col.nullable

    def test_metadata_column(self):
        col = chats_table.c["metadata"]
        assert isinstance(col.type, JSONB)
        assert not col.nullable

    def test_created_at_column(self):
        col = chats_table.c["created_at"]
        assert isinstance(col.type, sa.TIMESTAMP)
        assert col.type.timezone

    def test_updated_at_column(self):
        col = chats_table.c["updated_at"]
        assert isinstance(col.type, sa.TIMESTAMP)
        assert col.type.timezone

    def test_expires_at_column(self):
        col = chats_table.c["expires_at"]
        assert isinstance(col.type, sa.TIMESTAMP)
        assert col.nullable


class TestChatFilesTable:
    def test_table_name(self):
        assert chat_files_table.name == "agent_chat_files"

    def test_table_registered_in_metadata(self):
        assert "agent_chat_files" in metadata.tables

    def test_id_column(self):
        col = chat_files_table.c["id"]
        assert isinstance(col.type, PG_UUID)
        assert col.primary_key

    def test_chat_id_column_fk(self):
        col = chat_files_table.c["chat_id"]
        assert isinstance(col.type, sa.Text)
        assert not col.nullable
        fk_targets = {fk.target_fullname for fk in col.foreign_keys}
        assert "agent_chats.chat_id" in fk_targets

    def test_content_column(self):
        col = chat_files_table.c["content"]
        assert isinstance(col.type, BYTEA)
        assert not col.nullable

    def test_size_column(self):
        col = chat_files_table.c["size"]
        assert isinstance(col.type, sa.Integer)
        assert not col.nullable

    def test_created_at_column(self):
        col = chat_files_table.c["created_at"]
        assert isinstance(col.type, sa.TIMESTAMP)
        assert col.type.timezone


class TestChatHistoryDAO:
    def test_init_stores_engine(self):
        engine = MagicMock()
        dao = ChatHistoryDAO(engine)
        assert dao.engine is engine

    def test_init_exposes_chats_table(self):
        dao = ChatHistoryDAO(MagicMock())
        assert dao.chats is chats_table

    def test_init_exposes_chat_files_table(self):
        dao = ChatHistoryDAO(MagicMock())
        assert dao.chat_files is chat_files_table
