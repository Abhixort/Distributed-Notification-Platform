import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, String
from app.core.database import Base


def get_utc_now():
    return datetime.now(timezone.utc)


class BaseModelMixin:
    """Base mixin providing UUID primary keys and standard UTC timestamps."""
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)
