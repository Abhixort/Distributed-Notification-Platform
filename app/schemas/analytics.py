from typing import Dict, List, Optional
from pydantic import BaseModel


class ChannelMetric(BaseModel):
    total_requested: int
    delivered: int
    failed: int
    dlq: int
    success_rate_percent: float
    avg_latency_ms: float


class RealtimeAnalyticsResponse(BaseModel):
    system_status: str
    total_notifications: int
    total_delivered: int
    total_failed: int
    total_in_dlq: int
    total_in_flight: int
    overall_success_rate_percent: float
    current_throughput_per_sec: float
    channel_breakdown: Dict[str, ChannelMetric]
    queue_depths: Dict[str, int]


class SystemHealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    celery_broker: str
    version: str
    uptime_seconds: float
