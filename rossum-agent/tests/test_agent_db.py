"""Tests for rossum_agent.db module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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

    @staticmethod
    def _make_engine(mock_conn):
        """Create a mock async engine whose .begin() returns mock_conn as async ctx manager."""
        mock_engine = MagicMock()
        ctx = AsyncMock()
        ctx.__aenter__.return_value = mock_conn
        ctx.__aexit__.return_value = False
        mock_engine.begin.return_value = ctx
        return mock_engine

    @pytest.mark.asyncio
    async def test_save_chat_executes_upsert(self):
        mock_conn = AsyncMock()
        engine = self._make_engine(mock_conn)

        dao = ChatHistoryDAO(engine)
        await dao.save_chat(
            "chat_1", "user_1", [{"role": "user", "content": "hi"}], metadata={"mcp_mode": "read-only"}
        )

        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_file_executes_delete_and_insert(self):
        mock_conn = AsyncMock()
        engine = self._make_engine(mock_conn)

        dao = ChatHistoryDAO(engine)
        await dao.save_file("chat_1", "report.pdf", b"pdf-content")

        assert mock_conn.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_save_feedback_executes_update(self):
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = MagicMock(rowcount=1)
        engine = self._make_engine(mock_conn)

        dao = ChatHistoryDAO(engine)
        result = await dao.save_feedback("chat_1", 0, True)

        assert result is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_feedback_executes_update(self):
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = MagicMock(rowcount=1)
        engine = self._make_engine(mock_conn)

        dao = ChatHistoryDAO(engine)
        result = await dao.delete_feedback("chat_1", 0)

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_chat_returns_true_when_deleted(self):
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = MagicMock(rowcount=1)
        engine = self._make_engine(mock_conn)

        dao = ChatHistoryDAO(engine)
        result = await dao.delete_chat("chat_1")

        assert result is True

    @pytest.mark.asyncio
    async def test_delete_chat_returns_false_when_not_found(self):
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = MagicMock(rowcount=0)
        engine = self._make_engine(mock_conn)

        dao = ChatHistoryDAO(engine)
        result = await dao.delete_chat("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_save_all_files_nonexistent_dir(self, tmp_path):
        dao = ChatHistoryDAO(AsyncMock())
        result = await dao.save_all_files("chat_1", tmp_path / "nonexistent")
        assert result == 0

    @pytest.mark.asyncio
    async def test_save_all_files_saves_files(self, tmp_path):
        (tmp_path / "a.txt").write_bytes(b"aaa")
        (tmp_path / "b.txt").write_bytes(b"bbb")

        dao = ChatHistoryDAO(AsyncMock())
        with patch.object(dao, "save_file", new_callable=AsyncMock) as mock_save:
            result = await dao.save_all_files("chat_1", tmp_path)

        assert result == 2
        assert mock_save.call_count == 2
