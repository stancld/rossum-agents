"""Tests for rossum_mcp.db module."""

from __future__ import annotations

from unittest.mock import MagicMock

import sqlalchemy as sa
from rossum_mcp.db import SearchPagesDAO, metadata, search_pages_table
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class TestSearchPagesTable:
    def test_table_name(self):
        assert search_pages_table.name == "mcp_search_pages"

    def test_table_registered_in_metadata(self):
        assert "mcp_search_pages" in metadata.tables

    def test_id_column(self):
        col = search_pages_table.c["id"]
        assert isinstance(col.type, PG_UUID)
        assert col.primary_key

    def test_items_column(self):
        col = search_pages_table.c["items"]
        assert isinstance(col.type, JSONB)
        assert not col.nullable

    def test_created_at_column(self):
        col = search_pages_table.c["created_at"]
        assert isinstance(col.type, sa.TIMESTAMP)
        assert col.type.timezone


class TestSearchPagesDAO:
    def test_init_stores_engine(self):
        engine = MagicMock()
        dao = SearchPagesDAO(engine)
        assert dao.engine is engine

    def test_init_exposes_search_pages_table(self):
        dao = SearchPagesDAO(MagicMock())
        assert dao.search_pages is search_pages_table
