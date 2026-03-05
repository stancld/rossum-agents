from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

from alembic import context
from rossum_mcp.db import metadata
from sqlalchemy.ext.asyncio import create_async_engine

if TYPE_CHECKING:
    import sqlalchemy as sa

target_metadata = metadata
VERSION_TABLE = "alembic_version_mcp"


def run_migrations_offline() -> None:
    url = os.environ["POSTGRES_DSN"]
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=VERSION_TABLE,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    url = os.environ["POSTGRES_DSN"]
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        await conn.run_sync(_run_migrations_sync)
    await engine.dispose()


def _run_migrations_sync(conn: sa.Connection) -> None:
    context.configure(connection=conn, target_metadata=target_metadata, version_table=VERSION_TABLE)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
