/**
 * AetherSelf Operations Hub Frontend Controller
 * Connects via WebSockets to stream real-time telemetry, model switches,
 * CoT reasoning traces, and manage fault injection.
 */

document.addEventListener("DOMContentLoaded", () => {
  let ws = null;
  let retryTimer = null;

  // DOM Elements
  const pulseEl = document.getElementById("connection-pulse");
  const statePillText = document.getElementById("current-state-text");
  const globalStatePill = document.getElementById("global-state-pill");

  // Metric Ribbon
  const recoveryRateEl = document.getElementById("metric-recovery-rate");
  const mtthEl = document.getElementById("metric-mtth");
  const ramFootprintEl = document.getElementById("metric-ram-footprint");

  // Gauges
  const valCpu = document.getElementById("val-cpu");
  const barCpu = document.getElementById("bar-cpu");
  const valMem = document.getElementById("val-mem");
  const barMem = document.getElementById("bar-mem");
  const valIpc = document.getElementById("val-ipc");
  const barIpc = document.getElementById("bar-ipc");
  const valQueue = document.getElementById("val-queue");
  const barQueue = document.getElementById("bar-queue");
  const valErrors = document.getElementById("val-errors");
  const barErrors = document.getElementById("bar-errors");
  const valHandles = document.getElementById("val-handles");
  const barHandles = document.getElementById("bar-handles");

  // Anomaly Meter
  const anomalyScoreText = document.getElementById("anomaly-score-text");
  const anomalyFill = document.getElementById("anomaly-fill");
  const anomalyVariances = document.getElementById("anomaly-variances");

  // Model Switcher
  const activeModelTag = document.getElementById("active-model-tag");
  const tier1Box = document.getElementById("tier-1-box");
  const tier2Box = document.getElementById("tier-2-box");

  // CoT & Action Plan
  const cotLogs = document.getElementById("cot-logs");
  const planCard = document.getElementById("plan-card");

  // RAG
  const ragResultsList = document.getElementById("rag-results-list");
  const ragItemsTag = document.getElementById("rag-items-tag");
  const ragInput = document.getElementById("rag-query-input");
  const btnRagQuery = document.getElementById("btn-rag-query");

  // Cluster & Ledger
  const clusterGrid = document.getElementById("cluster-grid");
  const ledgerBody = document.getElementById("ledger-body");

  // Connect WebSocket
  function connectWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      pulseEl.className = "pulse-indicator pulse-active";
      console.log("[AetherSelf] WebSocket connected.");
      if (retryTimer) clearInterval(retryTimer);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleServerEvent(msg);
      } catch (e) {
        console.error("WS Parse Error", e);
      }
    };

    ws.onclose = () => {
      pulseEl.className = "pulse-indicator pulse-disconnected";
      console.warn("[AetherSelf] WebSocket disconnected. Retrying in 2s...");
      retryTimer = setTimeout(connectWebSocket, 2000);
    };

    ws.onerror = (err) => {
      ws.close();
    };
  }

  // Handle Event Stream
  function handleServerEvent(payload) {
    const { event, data } = payload;

    if (event === "telemetry_update" || event === "initial_state") {
      updateTelemetryUI(data);
    } else if (event === "state_change") {
      updateStateNodes(data.state);
    } else if (event === "rag_results") {
      renderRagMatches(data.matches);
    } else if (event === "action_plan") {
      renderActionPlan(data);
    }
  }

  // Update UI Elements
  function updateTelemetryUI(data) {
    const snap = data.snapshot || data.telemetry;
    const anomaly = data.anomaly || {};
    const state = data.state || "NORMAL";
    const model = data.model_switcher || {};
    const metrics = data.metrics || {};
    const services = data.services || {};

    if (!snap) return;

    // 1. Ribbon Metrics
    if (metrics.recovery_rate_percent) {
      recoveryRateEl.innerText = `${metrics.recovery_rate_percent.toFixed(1)}%`;
    }
    if (metrics.mtth_seconds) {
      mtthEl.innerText = `${metrics.mtth_seconds.toFixed(2)} s`;
    }
    if (snap.memory_mb) {
      ramFootprintEl.innerText = `${(snap.memory_mb / 1024).toFixed(2)} GB`;
    }
    if (metrics.vector_items_count) {
      ragItemsTag.innerText = `${metrics.vector_items_count} STORED TRACES`;
    }

    // 2. Telemetry Gauges
    valCpu.innerText = `${snap.cpu_percent}%`;
    barCpu.style.width = `${Math.min(100, snap.cpu_percent)}%`;

    valMem.innerText = `${snap.memory_percent}% (${snap.memory_mb.toFixed(0)} MB)`;
    barMem.style.width = `${Math.min(100, snap.memory_percent)}%`;

    valIpc.innerText = `${snap.ipc_latency_ms.toFixed(1)} ms`;
    barIpc.style.width = `${Math.min(100, (snap.ipc_latency_ms / 350) * 100)}%`;

    valQueue.innerText = `${snap.queue_backlog} msgs`;
    barQueue.style.width = `${Math.min(100, (snap.queue_backlog / 80) * 100)}%`;

    valErrors.innerText = `${snap.error_log_rate.toFixed(1)} err/s`;
    barErrors.style.width = `${Math.min(100, (snap.error_log_rate / 20) * 100)}%`;

    valHandles.innerText = `${snap.open_file_handles} handles`;
    barHandles.style.width = `${Math.min(100, (snap.open_file_handles / 200) * 100)}%`;

    // 3. Anomaly Meter
    const aScore = snap.anomaly_score !== undefined ? snap.anomaly_score : (anomaly.anomaly_score || 0.0);
    anomalyScoreText.innerText = `${aScore.toFixed(2)} (${aScore > 0.65 ? "ANOMALOUS" : "Nominal"})`;
    anomalyScoreText.style.color = aScore > 0.65 ? "var(--danger)" : "var(--success)";
    anomalyFill.style.width = `${Math.min(100, aScore * 100)}%`;

    if (anomaly.context_summary) {
      anomalyVariances.innerText = anomaly.context_summary;
    }

    // 4. Model Switcher
    const isEscalated = model.is_escalated;
    if (isEscalated) {
      activeModelTag.innerText = "TIER 2 (3.8B CoT SLM)";
      activeModelTag.className = "tag tag-model";
      tier1Box.classList.remove("active");
      tier2Box.classList.add("active");
    } else {
      activeModelTag.innerText = "TIER 1 (1B ROUTINE)";
      activeModelTag.className = "tag tag-live";
      tier1Box.classList.add("active");
      tier2Box.classList.remove("active");
    }

    // 5. State Machine Update
    updateStateNodes(state);

    // 6. Cluster Status Cards
    renderClusterGrid(services);

    // 7. Ledger update
    if (data.incident_history && data.incident_history.length > 0) {
      renderLedger(data.incident_history);
    }
  }

  // Update State Flow Nodes
  function updateStateNodes(currentState) {
    statePillText.innerText = currentState;
    const nodes = document.querySelectorAll(".state-node");
    nodes.forEach((n) => n.classList.remove("active"));

    const activeNode = document.getElementById(`node-${currentState}`);
    if (activeNode) {
      activeNode.classList.add("active");
    }
  }

  // Render CoT Logs
  function appendCotLog(line, stepClass = "") {
    const div = document.createElement("div");
    div.className = `cot-line ${stepClass}`;
    div.innerText = line;
    cotLogs.appendChild(div);
    cotLogs.scrollTop = cotLogs.scrollHeight;
  }

  // Render Action Plan
  function renderActionPlan(plan) {
    planCard.innerHTML = `
      <div class="plan-row"><span class="plan-label">Plan ID:</span><span class="plan-val">${plan.plan_id}</span></div>
      <div class="plan-row"><span class="plan-label">Target Service:</span><span class="plan-val" style="color:var(--primary);">${plan.target_service}</span></div>
      <div class="plan-row"><span class="plan-label">Safety Primitive:</span><span class="plan-val" style="color:var(--success); font-weight:700;">${plan.action}</span></div>
      <div class="plan-row"><span class="plan-label">Parameters:</span><span class="plan-val">${JSON.stringify(plan.parameters)}</span></div>
      <div class="plan-row"><span class="plan-label">Rollback Plan:</span><span class="plan-val" style="color:var(--warning);">${plan.rollback_action}</span></div>
      <div class="plan-row"><span class="plan-label">Confidence:</span><span class="plan-val">${(plan.confidence * 100).toFixed(1)}%</span></div>
      <div class="plan-row"><span class="plan-label">Diagnosis:</span><span class="plan-val" style="color:#e2e8f0;">${plan.root_cause_diagnosis}</span></div>
    `;

    // Append CoT steps to terminal
    if (plan.chain_of_thought) {
      plan.chain_of_thought.forEach((step, idx) => {
        appendCotLog(step, `step-${idx + 1}`);
      });
    }
  }

  // Render RAG Matches
  function renderRagMatches(matches) {
    if (!matches || matches.length === 0) {
      ragResultsList.innerHTML = `<div class="rag-card placeholder-card">No relevant historical traces found.</div>`;
      return;
    }
    ragResultsList.innerHTML = "";
    matches.forEach((m) => {
      const inc = m.incident;
      const card = document.createElement("div");
      card.className = "rag-card";
      card.innerHTML = `
        <div class="rag-card-header">
          <span>${inc.title}</span>
          <span class="rag-badge">Score: ${m.final_score.toFixed(3)}</span>
        </div>
        <div class="rag-symptom">${inc.symptoms}</div>
        <div class="rag-fix">Target: ${inc.target_service} | Recommended Fix: ${inc.recommended_action}</div>
      `;
      ragResultsList.appendChild(card);
    });
  }

  // Render Cluster Grid
  function renderClusterGrid(services) {
    clusterGrid.innerHTML = "";
    for (const [name, s] of Object.entries(services)) {
      const card = document.createElement("div");
      card.className = "cluster-card";
      const healthClass = `status-${s.health}`;
      card.innerHTML = `
        <div class="cluster-card-title">
          <span>${name}</span>
          <span class="svc-status-pill ${healthClass}">${s.health}</span>
        </div>
        <div style="font-size:0.72rem; color:var(--text-muted);">
          Fault: <span style="color:${s.active_fault ? 'var(--danger)' : 'var(--text-secondary)'}; font-weight:600;">${s.active_fault ? s.fault_name : 'None (Nominal)'}</span>
        </div>
        <div style="font-size:0.68rem; color:var(--text-muted); font-family:var(--font-mono);">
          Uptime: ${s.uptime_s}s
        </div>
      `;
      clusterGrid.appendChild(card);
    }
  }

  // Render Ledger
  function renderLedger(history) {
    if (!history || history.length === 0) return;
    ledgerBody.innerHTML = "";
    history.slice().reverse().forEach((item) => {
      const tr = document.createElement("tr");
      const timeStr = new Date(item.timestamp * 1000).toLocaleTimeString();
      const statusColor = item.status === "RESOLVED" ? "var(--success)" : "var(--danger)";
      tr.innerHTML = `
        <td style="font-family:var(--font-mono);">${timeStr}</td>
        <td style="font-weight:600;">${item.target}</td>
        <td style="color:var(--primary); font-family:var(--font-mono);">${item.action}</td>
        <td style="font-family:var(--font-mono); font-weight:700;">${item.duration_s ? item.duration_s.toFixed(2) + ' s' : '-'}</td>
        <td style="color:var(--text-secondary);">${item.diagnosis || item.error || '-'}</td>
        <td style="color:${statusColor}; font-weight:700;">${item.status}</td>
      `;
      ledgerBody.appendChild(tr);
    });
  }

  // Fault Injection Button Handlers
  document.querySelectorAll(".btn-chaos[data-fault]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const fault = btn.getAttribute("data-fault");
      appendCotLog(`[CHAOS EVENT] Operator injected fault: '${fault}'...`, "step-1");
      try {
        const resp = await fetch("/api/fault/inject", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ fault_type: fault }),
        });
        const res = await resp.json();
        console.log("Fault Injected", res);
      } catch (err) {
        console.error("Fault Injection Error", err);
      }
    });
  });

  // Clear Faults
  document.getElementById("btn-clear-faults").addEventListener("click", async () => {
    appendCotLog(`[OPERATOR] Normalizing cluster and clearing faults...`, "step-4");
    try {
      await fetch("/api/fault/clear", { method: "POST" });
    } catch (e) {
      console.error(e);
    }
  });

  // Manual RAG Query
  btnRagQuery.addEventListener("click", async () => {
    const q = ragInput.value.trim();
    if (!q) return;
    try {
      const resp = await fetch("/api/rag/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: q, top_k: 3 }),
      });
      const data = await resp.json();
      renderRagMatches(data.matches);
    } catch (err) {
      console.error("RAG Query Error", err);
    }
  });

  // Manual Sync Button
  document.getElementById("btn-manual-sync").addEventListener("click", async () => {
    try {
      const resp = await fetch("/api/status");
      const data = await resp.json();
      updateTelemetryUI(data);
    } catch (err) {
      console.error(err);
    }
  });

  // Initial Connect
  connectWebSocket();
});
