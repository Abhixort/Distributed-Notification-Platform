import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    PROJECT_NAME: str = "Distributed Notification Platform"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    CORS_ORIGINS: List[str] = ["*"]

    # Database URLs
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/notification_db"
    DATABASE_SYNC_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/notification_db"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # Redis URLs
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_URL: str = "redis://localhost:6379/1"
    REDIS_MAX_CONNECTIONS: int = 50

    # Celery Broker & Backend
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # Token Bucket Rate Limiting (10,000+ notifications/min)
    RATE_LIMIT_ENABLED: bool = True
    DEFAULT_RATE_LIMIT_CAPACITY: int = 200  # Max burst tokens
    DEFAULT_RATE_LIMIT_REFILL_RATE: float = 166.67  # Tokens added per second (~10,000/min)

    # Idempotency
    IDEMPOTENCY_EXPIRATION_SECONDS: int = 86400  # 24 hours retention
    IDEMPOTENCY_LOCK_TIMEOUT_SECONDS: int = 10  # In-flight concurrency lock

    # Retries & Fault Tolerance
    MAX_NOTIFICATION_RETRIES: int = 5
    RETRY_BASE_DELAY_SECONDS: int = 2
    RETRY_MAX_DELAY_SECONDS: int = 60
    RETRY_EXPONENTIAL_FACTOR: int = 2

    # AWS SES & SNS Integration
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    SES_SENDER_EMAIL: str = "notifications@platform.internal"
    USE_MOCK_PROVIDERS: bool = True  # Mock providers enabled for testing/local

    # Webhook Delivery
    WEBHOOK_DEFAULT_TIMEOUT_SECONDS: int = 10
    WEBHOOK_SECRET_KEY: str = "platform-webhook-hmac-secret-key-32-bytes"

    # Security & API Auth
    SECRET_KEY: str = "super-secret-system-key-change-in-production"
    API_KEY_HEADER_NAME: str = "X-API-Key"
    MASTER_API_KEY: str = "notif_master_key_super_secret_9999"


settings = Settings()
