# ⚡ Distributed Notification Platform

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Celery](https://img.shields.io/badge/Celery-5.4+-37814A.svg?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Redis](https://img.shields.io/badge/Redis-7.0+-DC382D.svg?logo=redis&logoColor=white)](https://redis.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-4169E1.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com)
[![AWS](https://img.shields.io/badge/AWS-SES%20%7C%20SNS%20%7C%20ECS-232F3E.svg?logo=amazon-aws&logoColor=white)](https://aws.amazon.com)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Repository-181717.svg?logo=github&logoColor=white)](https://github.com/Abhixort/Distributed-Notification-Platform)

An enterprise-grade, high-throughput asynchronous distributed notification engine built with **Python, FastAPI, Celery, Redis, PostgreSQL, and Docker**. Designed to reliably dispatch **10,000+ notifications/minute** across multiple communication channels with strict idempotency, token-bucket rate limiting, exponential backoff retries, and dead-letter queue (DLQ) redrive capabilities.

---

## 🌟 Key Architectural Highlights

* **Multi-Channel Notification Architecture**: Engineered an asynchronous notification engine supporting multi-channel delivery (**Email**, **SMS**, **Webhooks**) using FastAPI, Celery, and Redis message brokers.
* **Fault Tolerance & Idempotency**: Implemented exponential backoff retries with random jitter, dead-letter queues (DLQ), and idempotent task execution (Redis distributed locks + PostgreSQL constraints) to eliminate duplicate deliveries during upstream gateway outages.
* **High-Throughput Rate Limiting**: Configured token-bucket rate limiting (atomic Redis Lua scripts) and priority queues (`high`, `medium`, `low`), scaling system capacity to process **10,000+ notifications/min** with full OpenAPI documentation and real-time dashboard analytics.

---

## 🏗️ System Architecture

```mermaid
graph TD
    Client["Client / Microservices / Dashboard"] -->|REST API / Async Ingest| API["FastAPI Application (ASGI)"]
    API -->|1. Token-Bucket Rate Limit Check| RedisLimiter[("Redis (Atomic Lua Token Bucket)")]
    API -->|2. Idempotency Lock & Lookup| RedisIdem[("Redis Idempotency Cache")]
    API -->|3. Record Ingestion (PENDING/QUEUED)| DB[("PostgreSQL 16")]
    API -->|4. Push Task to Priority Queues| Broker[("Redis Message Broker")]
    
    subgraph Celery Queue Architecture
        Broker --> QHigh["high_priority queue (Expedited)"]
        Broker --> QDefault["default_priority queue (Standard)"]
        Broker --> QLow["low_priority queue (Bulk)"]
        Broker --> QDLQ["dead_letter_queue (DLQ)"]
    end

    QHigh --> WHigh["Worker Fleet (High Priority)"]
    QDefault --> WDefault["Worker Fleet (Default / Batch)"]
    QLow --> WLow["Worker Fleet (Low Priority)"]
    QDLQ --> WDLQ["DLQ Inspector / Redrive Worker"]

    WHigh & WDefault & WLow --> ProviderFactory["Provider Adapter Layer"]
    ProviderFactory -->|Email| SES["AWS SES / SMTP Gateway"]
    ProviderFactory -->|SMS| SNS["AWS SNS / Twilio Gateway"]
    ProviderFactory -->|Webhook| WebhookTarget["Target Webhook (HMAC-SHA256 Signed)"]

    ProviderFactory -->|Failures Exceeding Max Retries| QDLQ
    ProviderFactory -->|Audit Logs & Status Updates| DB
    
    Scheduler["Celery Beat"] -->|Scheduled Notifications & Cron| Broker
    Flower["Flower Dashboard (Port 5555)"] -->|Queue Monitoring| Broker
```

---

## 📊 Interactive Management Dashboard

The platform includes a built-in control plane accessible at `http://localhost:8000/dashboard`:
* **Real-Time Analytics**: Live throughput gauges, success/failure ratios, and channel metrics.
* **Interactive Dispatcher**: Test console to trigger multi-channel alerts with custom priorities, template placeholders, and idempotency keys.
* **Token-Bucket Meter**: Live visual gauge demonstrating token drain and automatic refill rate (166.67 tokens/sec).
* **DLQ Management**: Dead-letter queue inspector with single and bulk **1-Click Redrive** or permanent purge.
* **Live Audit Stream**: Real-time event feed capturing delivery attempts, provider responses, and latencies.

---

## 🚀 Quickstart Guide (Local & Docker)

### Option 1: Running with Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/Abhixort/Distributed-Notification-Platform.git
cd Distributed-Notification-Platform

# 2. Start all services (Postgres, Redis, API, Celery Workers, Beat, Flower, Prometheus)
docker-compose up -d --build

# 3. Access Services
# Dashboard:       http://localhost:8000/dashboard
# OpenAPI Docs:    http://localhost:8000/docs
# Flower (Queues): http://localhost:5555
# Prometheus:      http://localhost:9090
```

### Option 2: Running Locally for Development

```bash
# 1. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate   # On Windows
# source venv/bin/activate # On Linux/macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Seed template data
python scripts/seed_data.py

# 4. Start FastAPI server
uvicorn app.main:app --reload --port 8000

# 5. In separate terminal windows, start Celery workers and scheduler
celery -A app.core.celery_app.celery_app worker -Q high_priority,default_priority,low_priority -l INFO
celery -A app.core.celery_app.celery_app beat -l INFO
```

---

## 📡 API Reference & Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/notifications` | Dispatch single notification (Email, SMS, Webhook) with priority & idempotency. |
| `POST` | `/api/v1/notifications/batch` | High-throughput batch dispatch (up to 1,000 notifications in one request). |
| `GET` | `/api/v1/notifications/{id}` | Query notification status, retry history, and downstream provider audit logs. |
| `GET` | `/api/v1/notifications` | Filter and paginate notifications by channel, status, priority, or recipient. |
| `POST` | `/api/v1/templates` | Create dynamic Jinja2 message template with variable schema. |
| `POST` | `/api/v1/templates/render` | Preview rendered subject and body with variable context. |
| `GET` | `/api/v1/dlq` | List notifications stranded in Dead-Letter Queue. |
| `POST` | `/api/v1/dlq/redrive` | Re-enqueue dead-lettered messages back to Celery workers with reset retry budgets. |
| `DELETE`| `/api/v1/dlq/purge` | Permanently purge dead messages. |
| `GET` | `/api/v1/analytics/realtime` | Aggregate platform metrics, throughput, channel breakdown, and queue depths. |
| `GET` | `/api/v1/analytics/health` | Comprehensive health check across Database, Redis, and Broker. |
| `POST` | `/api/v1/mock-webhook/receive` | Test receiver verifying HMAC-SHA256 signature headers. |
| `GET` | `/metrics` | Prometheus metrics scrape endpoint. |

---

## ⚡ High-Throughput & Load Testing (10,000+ req/min)

The platform is benchmarked using **Locust** and **Redis atomic Lua scripts** to guarantee linear scalability without concurrency bottlenecks:

```bash
# Launch Locust Load Generator
locust -f tests/load_testing/locustfile.py --host http://localhost:8000
```
Open `http://localhost:8089` to configure user spawn rates (e.g., 200 concurrent users at 50 users/sec) and verify 10,000+ req/min throughput.

---

## 🧪 Automated Testing

Run the comprehensive unit and integration test suite:

```bash
pytest -v
```

Test coverage includes:
* Token-Bucket rate limiting, token depletion, and burst controls.
* Idempotency distributed locking and deduplication.
* Dynamic Jinja2 template interpolation.
* Multi-channel provider dispatch and mock error handling.
* Dead-Letter Queue (DLQ) state transitions and redrive flows.
* HMAC-SHA256 webhook signature generation and verification.

---

## ☁️ AWS Cloud Architecture

For production cloud deployment on Amazon Web Services (AWS), the platform utilizes:
* **AWS ECS Fargate**: Auto-scaling containers for API and Celery worker fleets.
* **Amazon ElastiCache Redis**: Multi-AZ distributed broker and token-bucket cache.
* **Amazon Aurora / RDS PostgreSQL**: Highly-available relational storage.
* **Amazon SES & SNS**: Native cloud email and SMS delivery gateways.
* Detailed CloudFormation templates and ECS task definitions are located in the [`aws/`](./aws/) directory.

---

## 📄 License
MIT License. Created by [Abhishek](https://github.com/Abhixort).
