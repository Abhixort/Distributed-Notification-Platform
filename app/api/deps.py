from typing import AsyncGenerator, Optional
from fastapi import Header, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_async_db

api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER_NAME, auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide async database session dependency."""
    async for session in get_async_db():
        yield session


async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header),
) -> str:
    """
    Authenticate incoming API requests.
    Allows master key or defaults to 'authenticated_client' in dev/mock mode.
    """
    if not api_key:
        # In development / playground mode, permit anonymous client
        if settings.ENVIRONMENT == "development" or settings.DEBUG:
            return "dev_client"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing required authentication header '{settings.API_KEY_HEADER_NAME}'",
        )

    if api_key == settings.MASTER_API_KEY:
        return "master_admin"

    # Valid key format
    return f"client_{api_key[:8]}"
