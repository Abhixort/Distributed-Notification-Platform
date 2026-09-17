import enum


class ChannelType(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"


class PriorityLevel(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    DELIVERED = "delivered"
    FAILED = "failed"
    DLQ = "dlq"


class ProviderType(str, enum.Enum):
    AWS_SES = "aws_ses"
    AWS_SNS = "aws_sns"
    TWILIO = "twilio"
    SMTP = "smtp"
    WEBHOOK = "webhook"
    MOCK = "mock"
