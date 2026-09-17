from typing import AsyncGenerator
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings
from app.core.logging import logger

# Base Model for all database entities
Base = declarative_base()

# ---------------------------------------------------------------------------
# Async Database Engine (for FastAPI Async API Endpoints)
# ---------------------------------------------------------------------------
async_engine_kwargs = {"echo": settings.DB_ECHO}
if "sqlite" in settings.DATABASE_URL:
    async_engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    async_engine_kwargs.update({
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_pre_ping": True,
    })

async_engine = create_async_engine(settings.DATABASE_URL, **async_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session for request scope."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Synchronous Database Engine (for Celery Background Workers)
# ---------------------------------------------------------------------------
sync_engine_kwargs = {"echo": settings.DB_ECHO}
if "sqlite" in settings.DATABASE_SYNC_URL:
    sync_engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    sync_engine_kwargs.update({
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_pre_ping": True,
    })

sync_engine = create_engine(settings.DATABASE_SYNC_URL, **sync_engine_kwargs)

SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
)


def get_sync_db():
    """Context manager / helper yielding a synchronous database session for Celery workers."""
    session = SyncSessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def init_db():
    """Create tables on startup if they do not exist."""
    try:
        async with async_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.warning(f"Database initialization warning (will retry on connection): {e}")
