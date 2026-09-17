import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_email_notification(client: AsyncClient):
    payload = {
        "channel": "email",
        "recipient": "developer@company.com",
        "priority": "high",
        "subject": "Platform Deployment Successful",
        "content": "All distributed workers are operating within baseline latency.",
    }
    response = await client.post("/api/v1/notifications", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["channel"] == "email"
    assert data["recipient"] == "developer@company.com"
    assert data["priority"] == "high"
    assert "id" in data


@pytest.mark.asyncio
async def test_notification_idempotency_deduplication(client: AsyncClient):
    idemp_key = "idemp-test-order-998877"
    payload = {
        "channel": "sms",
        "recipient": "+15559876543",
        "priority": "medium",
        "content": "Your payment of $49.99 was processed.",
        "idempotency_key": idemp_key,
    }

    # First dispatch
    res1 = await client.post("/api/v1/notifications", json=payload)
    assert res1.status_code == 202
    data1 = res1.json()

    # Second dispatch with identical idempotency key
    res2 = await client.post("/api/v1/notifications", json=payload)
    assert res2.status_code == 202
    data2 = res2.json()

    # Must return the same notification record without creating a duplicate
    assert data1["id"] == data2["id"]
    assert data2["idempotency_key"] == idemp_key


@pytest.mark.asyncio
async def test_batch_notifications_dispatch(client: AsyncClient):
    items = [
        {"channel": "email", "recipient": f"user{i}@example.com", "content": f"Bulk notification #{i}"}
        for i in range(5)
    ]
    response = await client.post("/api/v1/notifications/batch", json={"notifications": items})
    assert response.status_code == 202
    data = response.json()
    assert data["total_requested"] == 5
    assert data["queued_count"] == 5
    assert data["failed_count"] == 0


@pytest.mark.asyncio
async def test_create_and_render_template(client: AsyncClient):
    tmpl_payload = {
        "name": "invoice_receipt",
        "channel": "email",
        "subject_template": "Invoice #{{ invoice_no }} for {{ customer }}",
        "body_template": "<p>Total Amount: ${{ total }}</p>",
        "variables": ["invoice_no", "customer", "total"],
    }
    t_res = await client.post("/api/v1/templates", json=tmpl_payload)
    assert t_res.status_code == 201
    tmpl_data = t_res.json()

    # Render Template
    render_payload = {
        "template_id": tmpl_data["id"],
        "data": {"invoice_no": "INV-1002", "customer": "Acme Corp", "total": "250.00"},
    }
    r_res = await client.post("/api/v1/templates/render", json=render_payload)
    assert r_res.status_code == 200
    render_data = r_res.json()
    assert render_data["subject"] == "Invoice #INV-1002 for Acme Corp"
    assert render_data["rendered_body"] == "<p>Total Amount: $250.00</p>"


@pytest.mark.asyncio
async def test_analytics_and_health_endpoints(client: AsyncClient):
    h_res = await client.get("/api/v1/analytics/health")
    assert h_res.status_code == 200
    h_data = h_res.json()
    assert h_data["database"] == "healthy"

    a_res = await client.get("/api/v1/analytics/realtime")
    assert a_res.status_code == 200
    a_data = a_res.json()
    assert "channel_breakdown" in a_data
    assert "total_notifications" in a_data


@pytest.mark.asyncio
async def test_mock_webhook_receiver_endpoint(client: AsyncClient):
    res = await client.post("/api/v1/mock-webhook/receive", json={"status": "active", "tier": "enterprise"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
