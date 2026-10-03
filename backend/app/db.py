import socket
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    get_settings().async_database_url,
    pool_pre_ping=True,
    # supabase pooler doesn't support prepared statements
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from app import models  # noqa: F401  (register tables on Base.metadata)

    try:
        conn_ctx = await engine.connect()
    except socket.gaierror as exc:
        raise RuntimeError(
            f"Cannot resolve database host '{engine.url.host}'. If this is Supabase's "
            "direct connection (db.<ref>.supabase.co), it is IPv6-only: use the "
            "Session pooler connection string from Supabase -> Connect instead."
        ) from exc
    await conn_ctx.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # no policies = not reachable through supabase's public api
        for table in Base.metadata.sorted_tables:
            await conn.execute(text(f"ALTER TABLE {table.name} ENABLE ROW LEVEL SECURITY"))
