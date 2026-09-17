from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.enums import ChannelType


class TemplateBase(BaseModel):
    name: str = Field(..., max_length=100, description="Unique human-readable identifier code (e.g., 'welcome_email')")
    description: Optional[str] = Field(default=None, max_length=255)
    channel: ChannelType
    subject_template: Optional[str] = Field(default=None, description="Jinja2 template for email subject")
    body_template: str = Field(..., description="Jinja2 template for message body")
    variables: Optional[List[str]] = Field(default_factory=list, description="List of expected variables in template")


class TemplateCreate(TemplateBase):
    pass


class TemplateUpdate(BaseModel):
    description: Optional[str] = None
    subject_template: Optional[str] = None
    body_template: Optional[str] = None
    variables: Optional[List[str]] = None


class TemplateResponse(TemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TemplateRenderRequest(BaseModel):
    template_id: str
    data: Dict[str, Any]


class TemplateRenderResponse(BaseModel):
    subject: Optional[str] = None
    rendered_body: str
