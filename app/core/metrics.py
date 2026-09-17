from prometheus_client import Counter, Histogram, Gauge

# Notifications Ingested Counter
NOTIFICATIONS_TOTAL = Counter(
    "notifications_total",
    "Total notification requests received",
    ["channel", "priority", "status"],
)

# Notifications Processed / Delivered Counter
NOTIFICATIONS_DELIVERED = Counter(
    "notifications_delivered_total",
    "Total notification deliveries executed by workers",
    ["channel", "provider", "status"],
)

# Notification Delivery Latency Histogram
DELIVERY_LATENCY_SECONDS = Histogram(
    "notification_delivery_latency_seconds",
    "Latency of downstream notification delivery in seconds",
    ["channel", "provider"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Idempotency Cache Hits
IDEMPOTENCY_HITS = Counter(
    "idempotency_hits_total",
    "Total requests resolved via idempotency cache deduplication",
    ["channel"],
)

# Rate Limited Requests
RATE_LIMIT_DROPPED = Counter(
    "rate_limit_dropped_total",
    "Total requests rejected by token bucket rate limiter",
    ["channel", "client_id"],
)

# Dead Letter Queue Metrics
DLQ_PUSHES_TOTAL = Counter(
    "dlq_pushes_total",
    "Total notifications transferred to Dead Letter Queue after max retries",
    ["channel", "reason"],
)

DLQ_REDRIVES_TOTAL = Counter(
    "dlq_redrives_total",
    "Total notifications redriven from DLQ back to active queues",
    ["channel"],
)

# Active Queue Gauge
QUEUE_DEPTH = Gauge(
    "notification_queue_depth",
    "Current depth of message queues",
    ["queue_name"],
)
