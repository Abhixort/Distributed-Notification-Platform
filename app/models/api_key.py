from sqlalchemy import Boolean, Column, Float, Integer, String
from app.core.database import Base
from app.models.base import BaseModelMixin


class ApiKey(Base, BaseModelMixin):
    __tablename__ = "api_keys"

    key_hash = Column(String(128), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    client_id = Column(String(50), nullable=False, index=True)
    rate_limit_capacity = Column(Integer, default=200, nullable=False)
    rate_limit_refill_rate = Column(Float, default=166.67, nullable=False)  # Tokens/sec
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<ApiKey(name='{self.name}', client_id='{self.client_id}')>"
