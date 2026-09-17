from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.enums import ChannelType, NotificationStatus, PriorityLevel


class NotificationBase(BaseModel):
    channel: ChannelType
    recipient: str = Field(..., description="Recipient email address, phone number (E.164), or Webhook URL")
    priority: PriorityLevel = Field(default=PriorityLevel.MEDIUM)
    subject: Optional[str] = Field(default=None, max_length=255)
    content: Optional[str] = Field(default=None, description="Raw content or rendered body")
    template_id: Optional[str] = Field(default=None, description="UUID or unique code of template")
    template_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Variables to substitute in template")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom tracking metadata or webhook headers")
    scheduled_at: Optional[datetime] = Field(default=None, description="ISO timestamp for scheduled future delivery")
    idempotency_key: Optional[str] = Field(default=None, max_length=128, description="Client-provided idempotency key")

    @field_validator("recipient")
    @classmethod
    def validate_recipient_format(cls, v: str, values) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Recipient cannot be empty.")
        return v


class NotificationCreate(NotificationBase):
    pass


class NotificationBatchCreate(BaseModel):
    notifications: List[NotificationCreate] = Field(..., min_length=1, max_length=1000)


class DeliveryLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    attempt_number: int
    status: NotificationStatus
    provider: str
    provider_message_id: Optional[str] = None
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    latency_ms: Optional[float] = None
    created_at: datetime


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    channel: ChannelType
    recipient: str
    priority: PriorityLevel
    status: NotificationStatus
    subject: Optional[str] = None
    content: Optional[str] = None
    template_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    retry_count: int
    max_retries: int
    scheduled_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_details: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, validation_alias="notification_metadata")
    created_at: datetime
    updated_at: datetime
    logs: Optional[List[DeliveryLogResponse]] = Field(default_factory=list)


class NotificationBatchResponse(BaseModel):
    total_requested: int
    queued_count: int
    duplicate_count: int
    failed_count: int
    notifications: List[NotificationResponse]


class NotificationFilter(BaseModel):
    channel: Optional[ChannelType] = None
    status: Optional[NotificationStatus] = None
    priority: Optional[PriorityLevel] = None
    recipient: Optional[str] = None
    idempotency_key: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
