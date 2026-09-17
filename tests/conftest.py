import os
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TEST_DB_FILE = "test_notifications.db"
TEST_DB_ASYNC = f"sqlite+aiosqlite:///./{TEST_DB_FILE}"
TEST_DB_SYNC = f"sqlite:///./{TEST_DB_FILE}"

# Set testing environment variables before importing app modules
os.environ["ENVIRONMENT"] = "testing"
os.environ["DATABASE_URL"] = TEST_DB_ASYNC
os.environ["DATABASE_SYNC_URL"] = TEST_DB_SYNC
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["USE_MOCK_PROVIDERS"] = "true"

from app.core.database import Base, sync_engine
from app.api.deps import get_db
from app.main import app


@pytest_asyncio.fixture(scope="session", autouse=True)
def init_test_db():
    # Create sync tables on test DB file
    Base.metadata.create_all(bind=sync_engine)
    yield
    Base.metadata.drop_all(bind=sync_engine)
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass


@pytest_asyncio.fixture(scope="function")
async def db_session():
    async_engine = create_async_engine(TEST_DB_ASYNC, echo=False)
    session_factory = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await async_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
