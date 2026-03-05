"""PostgreSQL data access objects for rossum-mcp."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

metadata = sa.MetaData()

search_pages_table = sa.Table(
    "mcp_search_pages",
    metadata,
    sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
    sa.Column("items", JSONB, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
)


class SearchPagesDAO:
    """DAO for mcp_search_pages table — stores paginated search result pages."""

    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine
        self.search_pages = search_pages_table
