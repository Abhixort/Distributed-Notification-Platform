from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import BaseModelMixin


class Notification(Base, BaseModelMixin):
    __tablename__ = "notifications"

    channel = Column(String(20), nullable=False, index=True)  # email, sms, webhook
    recipient = Column(String(255), nullable=False, index=True)
    priority = Column(String(20), default="medium", nullable=False, index=True)  # high, medium, low
    status = Column(String(20), default="pending", nullable=False, index=True)  # pending, queued, processing, delivered, failed, dlq

    subject = Column(String(255), nullable=True)
    content = Column(Text, nullable=True)

    template_id = Column(String(36), ForeignKey("templates.id", ondelete="SET NULL"), nullable=True)
    template_data = Column(JSON, default=dict, nullable=False)

    idempotency_key = Column(String(128), unique=True, nullable=True, index=True)

    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=5, nullable=False)

    scheduled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    error_details = Column(Text, nullable=True)

    notification_metadata = Column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    logs = relationship(
        "DeliveryLog",
        back_populates="notification",
        cascade="all, delete-orphan",
        order_by="DeliveryLog.attempt_number",
        lazy="selectin",
    )
    template = relationship("Template", lazy="selectin")

    @property
    def metadata_payload(self) -> dict:
        return self.notification_metadata or {}

    __table_args__ = (
        Index("ix_notifications_status_priority", "status", "priority"),
        Index("ix_notifications_scheduled", "status", "scheduled_at"),
    )

    def __repr__(self):
        return f"<Notification(id='{self.id}', channel='{self.channel}', recipient='{self.recipient}', status='{self.status}')>"
