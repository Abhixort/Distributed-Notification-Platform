from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import BaseModelMixin


class DeliveryLog(Base, BaseModelMixin):
    __tablename__ = "delivery_logs"

    notification_id = Column(String(36), ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False)  # delivered, failed, dlq
    provider = Column(String(50), nullable=False)  # aws_ses, aws_sns, webhook, etc.
    provider_message_id = Column(String(128), nullable=True)
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    latency_ms = Column(Float, nullable=True)

    # Relationships
    notification = relationship("Notification", back_populates="logs")

    def __repr__(self):
        return f"<DeliveryLog(notif_id='{self.notification_id}', attempt={self.attempt_number}, status='{self.status}')>"
