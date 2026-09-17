import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.database import init_db
from app.core.exceptions import (
    IdempotencyConflictException,
    NotificationPlatformException,
    RateLimitExceededException,
    ResourceNotFoundException,
    TemplateRenderError,
)
from app.core.logging import logger, setup_logging
from app.core.redis import close_redis, get_async_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown routines."""
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.PROJECT_NAME} in '{settings.ENVIRONMENT}' environment...")
    await init_db()
    
    # Test Redis connectivity
    from app.core.redis import set_redis_availability
    try:
        redis_client = await get_async_redis()
        await redis_client.ping()
        set_redis_availability(True)
        logger.info("Connected to Redis broker & cache successfully.")
    except Exception as e:
        set_redis_availability(False)
        logger.warning(f"Redis is currently not running ({e}). Operating with resilient in-memory fallback.")

    yield

    # Shutdown
    logger.info("Shutting down Distributed Notification Platform...")
    await close_redis()


# FastAPI App Definition
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
# Distributed Notification Platform API
High-Throughput, Resilient, Multi-Channel Notification Engine.

### Core Capabilities:
- **Multi-Channel Delivery Engine**: Asynchronous routing to Email (AWS SES/SMTP), SMS (AWS SNS/Twilio), and Webhooks (HMAC-SHA256).
- **Fault Tolerance & Idempotency**: Dual-tier idempotency locking, exponential backoff retries with jitter, and Dead-Letter Queue (DLQ) redrive mechanics.
- **High-Throughput Rate Limiting**: Redis Token-Bucket algorithm supporting 10,000+ notifications/minute and priority queues.
- **Observability**: Prometheus metrics endpoint (`/metrics`), structured tracing, and live management dashboard.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus Instrumentation
Instrumentator().instrument(app).expose(app, endpoint="/metrics")

# Mount Static Assets and Templates
base_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(base_dir, "static")
templates_dir = os.path.join(base_dir, "templates")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

templates = Jinja2Templates(directory=templates_dir)


# ---------------------------------------------------------------------------
# Global Exception Handlers
# ---------------------------------------------------------------------------
@app.exception_handler(RateLimitExceededException)
async def rate_limit_handler(request: Request, exc: RateLimitExceededException):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"error": "RateLimitExceeded", "message": exc.message, "details": exc.details},
        headers={"Retry-After": str(int(exc.retry_after) + 1)},
    )


@app.exception_handler(IdempotencyConflictException)
async def idempotency_conflict_handler(request: Request, exc: IdempotencyConflictException):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"error": "IdempotencyConflict", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(ResourceNotFoundException)
async def not_found_handler(request: Request, exc: ResourceNotFoundException):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "NotFound", "message": exc.message, "details": exc.details},
    )


@app.exception_handler(TemplateRenderError)
async def template_error_handler(request: Request, exc: TemplateRenderError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "TemplateRenderError", "message": exc.message, "details": exc.details},
    )


# ---------------------------------------------------------------------------
# Mount API Routers
# ---------------------------------------------------------------------------
app.include_router(api_v1_router, prefix=settings.API_V1_STR)


# ---------------------------------------------------------------------------
# Frontend Dashboard Routes
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_view(request: Request):
    """Serve the interactive management dashboard."""
    return templates.TemplateResponse(
        request,
        "index.html",
        {"project_name": settings.PROJECT_NAME},
    )
