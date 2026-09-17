from sqlalchemy import Boolean, Column, JSON, String, Text
from app.core.database import Base
from app.models.base import BaseModelMixin


class Template(Base, BaseModelMixin):
    __tablename__ = "templates"

    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)
    channel = Column(String(20), nullable=False, index=True)  # email, sms, webhook
    subject_template = Column(String(255), nullable=True)
    body_template = Column(Text, nullable=False)
    variables = Column(JSON, default=list, nullable=False)  # List of expected variable names
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<Template(name='{self.name}', channel='{self.channel}')>"
