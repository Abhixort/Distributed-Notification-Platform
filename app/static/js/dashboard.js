document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const statTotal = document.getElementById("stat-total");
  const statDelivered = document.getElementById("stat-delivered");
  const statSuccessRate = document.getElementById("stat-success-rate");
  const statDlq = document.getElementById("stat-dlq");
  const dlqBadge = document.getElementById("dlq-badge");
  const tokenMeterFill = document.getElementById("token-meter-fill");
  const tokenCountDisplay = document.getElementById("token-count-display");
  const dlqTableBody = document.getElementById("dlq-table-body");
  const auditFeedList = document.getElementById("audit-feed-list");
  const dispatchForm = document.getElementById("dispatch-form");
  const dispatchResponse = document.getElementById("dispatch-response");
  const channelSelect = document.getElementById("channel-select");
  const recipientInput = document.getElementById("recipient-input");
  const subjectGroup = document.getElementById("subject-group");
  const subjectInput = document.getElementById("subject-input");
  const contentInput = document.getElementById("content-input");
  const idempotencyInput = document.getElementById("idempotency-input");
  const btnGenIdempotency = document.getElementById("btn-gen-idempotency");
  const btnDispatchBurst = document.getElementById("btn-dispatch-burst");
  const btnRedriveAll = document.getElementById("btn-redrive-all");
  const btnPurgeDlq = document.getElementById("btn-purge-dlq");
  const btnRefresh = document.getElementById("btn-refresh");

  let localTokenBalance = 200;
  const maxCapacity = 200;

  // Handle Channel Switch
  channelSelect.addEventListener("change", (e) => {
    const channel = e.target.value;
    if (channel === "email") {
      subjectGroup.style.display = "block";
      recipientInput.placeholder = "developer@company.com";
      recipientInput.value = "developer@company.com";
    } else if (channel === "sms") {
      subjectGroup.style.display = "none";
      recipientInput.placeholder = "+15551234567";
      recipientInput.value = "+15551234567";
    } else if (channel === "webhook") {
      subjectGroup.style.display = "none";
      recipientInput.placeholder = "http://localhost:8000/api/v1/mock-webhook/receive";
      recipientInput.value = "http://localhost:8000/api/v1/mock-webhook/receive";
    }
  });

  // Generate Idempotency Key
  btnGenIdempotency.addEventListener("click", () => {
    idempotencyInput.value = "idemp-" + Math.random().toString(36).substring(2, 10) + "-" + Date.now();
  });

  // Fetch Dashboard Stats
  async function fetchStats() {
    try {
      const res = await fetch("/api/v1/analytics/realtime");
      if (!res.ok) return;
      const data = await res.json();

      statTotal.textContent = data.total_notifications.toLocaleString();
      statDelivered.textContent = data.total_delivered.toLocaleString();
      statSuccessRate.textContent = `${data.overall_success_rate_percent}% Success Rate`;
      statDlq.textContent = data.total_in_dlq.toLocaleString();
      dlqBadge.textContent = data.total_in_dlq;

      // Update Token Meter Simulation
      localTokenBalance = Math.min(maxCapacity, localTokenBalance + 15);
      const pct = Math.max(5, (localTokenBalance / maxCapacity) * 100);
      tokenMeterFill.style.width = `${pct}%`;
      tokenCountDisplay.textContent = `${Math.floor(localTokenBalance)} / ${maxCapacity}`;

    } catch (err) {
      console.error("Failed to fetch analytics:", err);
    }
  }

  // Fetch DLQ Items
  async function fetchDLQ() {
    try {
      const res = await fetch("/api/v1/dlq?limit=10");
      if (!res.ok) return;
      const items = await res.json();

      if (!items || items.length === 0) {
        dlqTableBody.innerHTML = `
          <tr>
            <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 2rem;">
              No dead-lettered notifications. All queues are running cleanly!
            </td>
          </tr>`;
        return;
      }

      dlqTableBody.innerHTML = items.map(item => `
        <tr>
          <td><span class="badge badge-${item.channel}">${item.channel}</span></td>
          <td style="font-family: monospace; font-size: 0.8rem;">${item.recipient}</td>
          <td>${item.retry_count} / ${item.max_retries}</td>
          <td style="color: var(--accent-rose); font-size: 0.75rem; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${item.error_details || 'Max retries exhausted'}">
            ${item.error_details || 'Max retries exhausted'}
          </td>
          <td>
            <button class="btn btn-secondary" onclick="redriveItem('${item.id}')" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">
              Redrive
            </button>
          </td>
        </tr>
      `).join("");

    } catch (err) {
      console.error("Failed to fetch DLQ:", err);
    }
  }

  // Fetch Recent Notifications Audit Feed
  async function fetchFeed() {
    try {
      const res = await fetch("/api/v1/notifications?limit=8");
      if (!res.ok) return;
      const items = await res.json();

      if (!items || items.length === 0) return;

      auditFeedList.innerHTML = items.map(item => `
        <div class="audit-item">
          <div>
            <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">
              <span class="badge badge-${item.channel}">${item.channel}</span>
              <span class="badge badge-${item.status}">${item.status}</span>
              <span style="font-size: 0.75rem; color: var(--text-muted);">${item.priority} priority</span>
            </div>
            <div style="font-size: 0.8rem; color: var(--text-primary); font-family: monospace;">
              ${item.recipient}
            </div>
          </div>
          <div style="font-size: 0.75rem; color: var(--text-muted); text-align: right;">
            ${new Date(item.created_at).toLocaleTimeString()}
          </div>
        </div>
      `).join("");

    } catch (err) {
      console.error("Failed to fetch feed:", err);
    }
  }

  // Window helper for redriving item
  window.redriveItem = async function(id) {
    try {
      const res = await fetch("/api/v1/dlq/redrive", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notification_ids: [id] })
      });
      if (res.ok) {
        fetchDLQ();
        fetchStats();
      }
    } catch (err) {
      console.error("Redrive error:", err);
    }
  };

  // Redrive All
  btnRedriveAll.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/v1/dlq/redrive", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      if (res.ok) {
        alert("Triggered redrive for all eligible DLQ items!");
        fetchDLQ();
        fetchStats();
      }
    } catch (err) {
      console.error("Redrive all error:", err);
    }
  });

  // Purge DLQ
  btnPurgeDlq.addEventListener("click", async () => {
    if (!confirm("Are you sure you want to permanently purge all DLQ messages?")) return;
    try {
      const res = await fetch("/api/v1/dlq/purge", { method: "DELETE" });
      if (res.ok) {
        fetchDLQ();
        fetchStats();
      }
    } catch (err) {
      console.error("Purge error:", err);
    }
  });

  // Dispatch Single
  dispatchForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      channel: channelSelect.value,
      recipient: recipientInput.value.trim(),
      priority: document.getElementById("priority-select").value,
      subject: channelSelect.value === "email" ? subjectInput.value.trim() : null,
      content: contentInput.value.trim(),
      idempotency_key: idempotencyInput.value.trim() || null,
    };

    localTokenBalance = Math.max(0, localTokenBalance - 1);

    try {
      dispatchResponse.style.display = "block";
      dispatchResponse.textContent = "Dispatching notification to asynchronous queue...";

      const res = await fetch("/api/v1/notifications", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      const data = await res.json();
      dispatchResponse.textContent = JSON.stringify(data, null, 2);

      fetchStats();
      fetchFeed();
    } catch (err) {
      dispatchResponse.textContent = "Error dispatching: " + err.message;
    }
  });

  // Dispatch Burst (10x)
  btnDispatchBurst.addEventListener("click", async () => {
    const channel = channelSelect.value;
    const recipient = recipientInput.value.trim();
    const priority = document.getElementById("priority-select").value;
    const content = contentInput.value.trim();

    dispatchResponse.style.display = "block";
    dispatchResponse.textContent = `Dispatching burst of 10 notifications concurrently...`;

    localTokenBalance = Math.max(0, localTokenBalance - 10);

    const items = Array.from({ length: 10 }, (_, i) => ({
      channel: channel,
      recipient: recipient,
      priority: priority,
      subject: channel === "email" ? `Burst Test Notification #${i + 1}` : null,
      content: `${content} (Burst Item #${i + 1})`,
      idempotency_key: "burst-" + Math.random().toString(36).substring(2, 9),
    }));

    try {
      const res = await fetch("/api/v1/notifications/batch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notifications: items })
      });
      const data = await res.json();
      dispatchResponse.textContent = JSON.stringify(data, null, 2);
      fetchStats();
      fetchFeed();
    } catch (err) {
      dispatchResponse.textContent = "Burst error: " + err.message;
    }
  });

  btnRefresh.addEventListener("click", () => {
    fetchStats();
    fetchDLQ();
    fetchFeed();
  });

  // Initial Load & Recurring Polling Loop
  fetchStats();
  fetchDLQ();
  fetchFeed();
  setInterval(() => {
    fetchStats();
    fetchFeed();
  }, 3000);
});
