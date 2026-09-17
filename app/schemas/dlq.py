from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.enums import ChannelType, PriorityLevel
from app.schemas.notification import NotificationResponse


class DLQItemResponse(NotificationResponse):
    pass


class DLQRedriveRequest(BaseModel):
    notification_ids: Optional[List[str]] = Field(default=None, description="Specific IDs to redrive. If omitted, redrives all eligible DLQ items.")
    channel: Optional[ChannelType] = Field(default=None, description="Filter DLQ redrives by channel")
    limit: int = Field(default=100, ge=1, le=1000)


class DLQRedriveResponse(BaseModel):
    redriven_count: int
    message: str
    notification_ids: List[str]


class DLQStatsResponse(BaseModel):
    total_dlq_count: int
    by_channel: dict
    by_priority: dict
    oldest_item_timestamp: Optional[datetime] = None
