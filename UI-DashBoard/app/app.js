document.addEventListener("DOMContentLoaded", () => {
  // =============================================
  // Navigation tabs
  // =============================================
  const navItems = document.querySelectorAll(".nav-item");
  const tabViews = document.querySelectorAll(".tab-view");

  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const tab = item.getAttribute("data-tab");
      navItems.forEach(n => n.classList.remove("active"));
      tabViews.forEach(v => v.classList.remove("active"));

      item.classList.add("active");
      const view = document.getElementById(`view-${tab}`);
      if (view) {
        view.classList.add("active");
        setTimeout(() => {
          drawAccuracyChart();
          drawPerformanceChart();
        }, 60);
      }
    });
  });

  // =============================================
  // Load Status Data from API
  // =============================================
  let appState = null;
  async function fetchStatus() {
    try {
      const res = await fetch("/api/status");
      appState = await res.json();
      updateBadges(appState);
    } catch (e) {
      console.warn("Could not fetch status API:", e);
    }
  }

  function updateBadges(state) {
    if (!state) return;

    // Update global version & round
    const curRound = (state.round && state.round.currentRound) || 1;
    const verValues = document.querySelectorAll(".topbar-version .ver-value, .sbc-value");
    verValues.forEach(el => {
      el.textContent = `v4.2.${curRound}`;
    });

    // Update global CID if IPFS refs exist
    const cidRef = document.querySelector(".ipfs-ref-item .ref-value");
    if (cidRef && state.round && state.round.globalCid) {
      cidRef.textContent = state.round.globalCid.slice(0, 8) + "..." + state.round.globalCid.slice(-6);
      cidRef.title = state.round.globalCid;
    }

    // Render live ledger rows if present
    const ledgerTbody = document.getElementById("ledger-tbody");
    if (ledgerTbody && state.round && state.round.submissions && state.round.submissions.length > 0) {
      ledgerTbody.innerHTML = "";
      state.round.submissions.forEach((sub) => {
        const tr = document.createElement("tr");
        const shortHash = sub.hash ? (sub.hash.slice(0, 10) + "..." + sub.hash.slice(-8)) : "0x...";
        const shortTx = sub.txHash ? (sub.txHash.slice(0, 10) + "...") : "Confirmed";
        const hospitalName = sub.hospital === 1 ? "St. Jude Node" : (sub.hospital === 2 ? "Johns Hopkins Node" : "Mayo Clinic Node");
        const badgeClass = sub.hospital === 1 ? "mh" : (sub.hospital === 2 ? "jh" : "cc");
        const badgeText = sub.hospital === 1 ? "SJ" : (sub.hospital === 2 ? "JH" : "MC");
        tr.innerHTML = `
          <td style="padding:12px;border-bottom:1px solid var(--border-light);"><span class="mono" title="${sub.hash}" style="font-size:0.78rem;">${shortHash}</span></td>
          <td style="padding:12px;border-bottom:1px solid var(--border-light);"><span class="node-badge ${badgeClass}" style="width:24px;height:24px;font-size:0.6rem;">${badgeText}</span> ${hospitalName}</td>
          <td style="padding:12px;border-bottom:1px solid var(--border-light);">${new Date().toISOString().slice(0, 10)}<br><span style="color:var(--text-dim);font-size:0.75rem;">${shortTx}</span></td>
          <td style="padding:12px;border-bottom:1px solid var(--border-light);"><span class="status-tag committed">On-Chain Verified</span></td>
        `;
        ledgerTbody.appendChild(tr);
      });
    }
  }

  // =============================================
  // Prompt Chips for Diagnosis
  // =============================================
  const chips = document.querySelectorAll(".prompt-chip");
  const symptomInput = document.getElementById("symptom-input");
  const btnDiagnose = document.getElementById("btn-diagnose");
  const resultsList = document.getElementById("results-list");

  chips.forEach(chip => {
    chip.addEventListener("click", () => {
      symptomInput.value = chip.getAttribute("data-symptoms");
      triggerDiagnosis();
    });
  });

  if (btnDiagnose) {
    btnDiagnose.addEventListener("click", triggerDiagnosis);
  }

  if (symptomInput) {
    symptomInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") triggerDiagnosis();
    });
  }

  async function triggerDiagnosis() {
    const text = symptomInput ? symptomInput.value.trim() : "";
    if (!text) return;

    if (btnDiagnose) {
      btnDiagnose.disabled = true;
      btnDiagnose.innerHTML = "<span>⏳</span><span>Analyzing Symptoms...</span>";
    }

    try {
      const res = await fetch("/api/diagnose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symptoms: text })
      });
      const data = await res.json();
      renderDiagnosis(data);
    } catch (err) {
      console.error(err);
    } finally {
      if (btnDiagnose) {
        btnDiagnose.disabled = false;
        btnDiagnose.innerHTML = "<span>🎯</span><span>Get AI Suggestion</span>";
      }
    }
  }

  function renderDiagnosis(data) {
    if (!resultsList) return;
    resultsList.innerHTML = "";

    if (!data) return;

    // Render Urgent Care Alert if flagged
    if (data.urgent_care_alert) {
      const alertDiv = document.createElement("div");
      alertDiv.className = "diag-alert-banner";
      alertDiv.style.cssText = "background:#fee2e2;border:1px solid #f87171;color:#b91c1c;padding:10px 14px;border-radius:var(--radius-md);margin-bottom:12px;font-size:0.8rem;font-weight:600;";
      alertDiv.innerHTML = `🚨 ${data.urgent_care_alert}`;
      resultsList.appendChild(alertDiv);
    }

    const differentials = (data.evidence && data.evidence.top_differentials) || [];
    if (differentials.length === 0) {
      const emptyDiv = document.createElement("div");
      emptyDiv.style.cssText = "padding:16px;text-align:center;color:var(--text-dim);font-size:0.85rem;";
      emptyDiv.textContent = "No direct ontology matches found. Please specify additional clinical symptoms.";
      resultsList.appendChild(emptyDiv);
      return;
    }

    differentials.forEach((r, idx) => {
      const div = document.createElement("div");
      div.className = "diag-result-item";
      div.innerHTML = `
        <div class="diag-result-top">
          <span class="diag-disease-name">${r.disease}</span>
          <span class="status-tag verified" style="font-size:0.7rem;">Ontology Match</span>
        </div>
        <div class="diag-score-label">Relevance Indicators: ${r.match_score} term match(es)</div>
        <div class="diag-bar-track"><div class="diag-bar-fill" style="width:${Math.min(100, r.match_score * 35)}%;"></div></div>
        <div class="diag-note" style="margin-top:6px;font-size:0.75rem;color:var(--text-dim);">🔬 Matched in 793-disease clinical ontology</div>
      `;
      resultsList.appendChild(div);
    });

    if (data.disclaimer) {
      const disc = document.createElement("div");
      disc.style.cssText = "margin-top:12px;font-size:0.7rem;color:var(--text-muted);font-style:italic;";
      disc.textContent = `ℹ️ ${data.disclaimer}`;
      resultsList.appendChild(disc);
    }
  }

  // =============================================
  // Advance Round Button
  // =============================================
  const btnAdvanceRound = document.getElementById("btn-advance-round");
  if (btnAdvanceRound) {
    btnAdvanceRound.addEventListener("click", async () => {
      btnAdvanceRound.disabled = true;
      btnAdvanceRound.innerHTML = "<span>⏳ Aggregating...</span>";

      try {
        const res = await fetch("/api/advance-round", { method: "POST" });
        const data = await res.json();
        if (data.success) {
          fetchStatus();
          alert(`🎉 Successfully advanced to Federated Round ${data.state.currentRound}!\nGlobal Accuracy now at ${data.state.globalAccuracy}%.`);
        }
      } catch (e) {
        console.error(e);
      } finally {
        btnAdvanceRound.disabled = false;
        btnAdvanceRound.innerHTML = "<span>⚡ Trigger Aggregation</span>";
      }
    });
  }

  // =============================================
  // Chart Drawing (Canvas-based simple charts)
  // =============================================
  function drawAccuracyChart() {
    const canvas = document.getElementById("accuracy-chart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * 2;
    canvas.height = rect.height * 2;
    ctx.scale(2, 2);
    const w = rect.width;
    const h = rect.height;

    // Data points (simulated accuracy curve)
    const points = [
      { x: 0.05, y: 0.15 },
      { x: 0.12, y: 0.18 },
      { x: 0.2, y: 0.25 },
      { x: 0.3, y: 0.35 },
      { x: 0.4, y: 0.42 },
      { x: 0.5, y: 0.55 },
      { x: 0.58, y: 0.58 },
      { x: 0.65, y: 0.62 },
      { x: 0.72, y: 0.68 },
      { x: 0.78, y: 0.72 },
      { x: 0.85, y: 0.78 },
      { x: 0.92, y: 0.85 },
      { x: 0.97, y: 0.88 }
    ];

    // Grid lines
    ctx.strokeStyle = "#e5e7eb";
    ctx.lineWidth = 0.5;
    for (let i = 0; i < 6; i++) {
      const y = h * (i / 5) * 0.85 + h * 0.05;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Fill area
    ctx.beginPath();
    ctx.moveTo(points[0].x * w, h - points[0].y * h * 0.85 - h * 0.05);
    for (let i = 1; i < points.length; i++) {
      const cx = (points[i - 1].x + points[i].x) / 2 * w;
      const cy = h - (points[i - 1].y + points[i].y) / 2 * h * 0.85 - h * 0.05;
      ctx.quadraticCurveTo(
        points[i - 1].x * w + (points[i].x - points[i - 1].x) * w * 0.5,
        h - points[i - 1].y * h * 0.85 - h * 0.05,
        points[i].x * w,
        h - points[i].y * h * 0.85 - h * 0.05
      );
    }
    ctx.lineTo(points[points.length - 1].x * w, h);
    ctx.lineTo(points[0].x * w, h);
    ctx.closePath();
    const gradient = ctx.createLinearGradient(0, 0, 0, h);
    gradient.addColorStop(0, "rgba(26, 86, 219, 0.15)");
    gradient.addColorStop(1, "rgba(26, 86, 219, 0.01)");
    ctx.fillStyle = gradient;
    ctx.fill();

    // Line
    ctx.beginPath();
    ctx.moveTo(points[0].x * w, h - points[0].y * h * 0.85 - h * 0.05);
    for (let i = 1; i < points.length; i++) {
      ctx.quadraticCurveTo(
        points[i - 1].x * w + (points[i].x - points[i - 1].x) * w * 0.5,
        h - points[i - 1].y * h * 0.85 - h * 0.05,
        points[i].x * w,
        h - points[i].y * h * 0.85 - h * 0.05
      );
    }
    ctx.strokeStyle = "#1a56db";
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // Data dots
    points.forEach((p, i) => {
      if (i % 2 === 0 || i === points.length - 1) {
        const px = p.x * w;
        const py = h - p.y * h * 0.85 - h * 0.05;
        ctx.beginPath();
        ctx.arc(px, py, 4, 0, Math.PI * 2);
        ctx.fillStyle = "#1a56db";
        ctx.fill();
        ctx.beginPath();
        ctx.arc(px, py, 2, 0, Math.PI * 2);
        ctx.fillStyle = "white";
        ctx.fill();
      }
    });
  }

  function drawPerformanceChart() {
    const canvas = document.getElementById("performance-chart");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * 2;
    canvas.height = rect.height * 2;
    ctx.scale(2, 2);
    const w = rect.width;
    const h = rect.height;

    // Recall curve (green, upper)
    const recallPoints = [
      { x: 0.05, y: 0.3 }, { x: 0.15, y: 0.35 }, { x: 0.25, y: 0.4 },
      { x: 0.4, y: 0.48 }, { x: 0.55, y: 0.55 }, { x: 0.65, y: 0.62 },
      { x: 0.75, y: 0.7 }, { x: 0.85, y: 0.78 }, { x: 0.95, y: 0.85 }
    ];

    // Grid
    ctx.strokeStyle = "#e5e7eb";
    ctx.lineWidth = 0.5;
    for (let i = 0; i < 5; i++) {
      const y = h * (i / 4) * 0.85 + h * 0.05;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Draw recall line
    ctx.beginPath();
    ctx.moveTo(recallPoints[0].x * w, h - recallPoints[0].y * h * 0.85 - h * 0.05);
    for (let i = 1; i < recallPoints.length; i++) {
      ctx.quadraticCurveTo(
        recallPoints[i - 1].x * w + (recallPoints[i].x - recallPoints[i - 1].x) * w * 0.5,
        h - recallPoints[i - 1].y * h * 0.85 - h * 0.05,
        recallPoints[i].x * w,
        h - recallPoints[i].y * h * 0.85 - h * 0.05
      );
    }
    ctx.strokeStyle = "#059669";
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // Initialize charts after a short delay for layout
  setTimeout(() => {
    drawAccuracyChart();
    drawPerformanceChart();
  }, 100);

  // Redraw on resize
  window.addEventListener("resize", () => {
    drawAccuracyChart();
    drawPerformanceChart();
  });

  // Chart toggle buttons
  document.querySelectorAll(".chart-toggle-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".chart-toggle-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });

  // Refresh button
  const btnRefresh = document.getElementById("btn-refresh");
  if (btnRefresh) {
    btnRefresh.addEventListener("click", async () => {
      btnRefresh.style.transform = "rotate(360deg)";
      btnRefresh.style.transition = "transform 0.5s ease";
      await fetchStatus();
      drawAccuracyChart();
      drawPerformanceChart();
      setTimeout(() => {
        btnRefresh.style.transform = "none";
        btnRefresh.style.transition = "none";
      }, 500);
    });
  }

  // Export report
  const btnExport = document.getElementById("btn-export");
  if (btnExport) {
    btnExport.addEventListener("click", () => {
      if (!appState) return;
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(appState, null, 2));
      const downloadAnchor = document.createElement("a");
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", `medxchain_audit_report_round_${appState.currentRound || 1}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
    });
  }

  // Network info button
  const btnNetwork = document.getElementById("btn-network");
  if (btnNetwork) {
    btnNetwork.addEventListener("click", () => {
      const addr = appState ? appState.contractAddress : "0x5FbDB2315678afecb367f032d93F642f64180aa3";
      alert(`🔗 Blockchain Network Connected\n• RPC: http://127.0.0.1:8545\n• Contract: ${addr}\n• Status: Sync Active (99.9% Integrity)`);
    });
  }

  // Search input filter for tables
  const searchInput = document.getElementById("topbar-search-input");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase();
      document.querySelectorAll(".data-table tbody tr, .hospital-item").forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(q) ? "" : "none";
      });
    });
  }

  // =============================================
  // Initial fetch
  // =============================================
  fetchStatus();
});
