import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import config
from fastapi import Request

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


def _build_async_url(url: str) -> str:
    return (
        url.replace("postgresql://", "postgresql+asyncpg://")
           .replace("postgres://", "postgresql+asyncpg://")
    )


engine = create_async_engine(
    _build_async_url(config.DATABASE_URL.get_secret_value()),
    pool_size=config.DATABASE_POOL_SIZE,
    max_overflow=config.DATABASE_MAX_OVERFLOW,
    pool_timeout=config.DATABASE_POOL_TIMEOUT,
    pool_recycle=config.DATABASE_POOL_RECYCLE,
    pool_pre_ping=True,
    echo=config.DEBUG,
    connect_args={
        "server_settings": {
            "statement_timeout": str(config.DATABASE_STATEMENT_TIMEOUT_MS),
        },
        "statement_cache_size": 0,  # Requerido para Supabase/PgBouncer Session Pooler
    },
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Conexión a base de datos establecida")


async def get_session(request: Request):
    async with AsyncSessionFactory() as session:
        org_id = getattr(request.state, "organization_id", None)
        tenant = str(org_id) if (config.MULTITENANCY_ENABLED and org_id) else ""
        await session.execute(
            text(
                "SELECT set_config('app.current_tenant',  :t,   true),"
                "       set_config('app.current_user_id', '',   true)"
            ),
            {"t": tenant},
        )
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
