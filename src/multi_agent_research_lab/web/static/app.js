/**
 * Multi-Agent Research Studio Frontend Logic
 * VinUni AI Lab 20
 */

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const topicSelect = document.getElementById("topic-select");
  const queryInput = document.getElementById("query-input");
  const maxSourcesInput = document.getElementById("max-sources");
  const sourcesVal = document.getElementById("sources-val");
  const audienceSelect = document.getElementById("audience-select");
  const criticToggle = document.getElementById("critic-toggle");

  const btnRunMulti = document.getElementById("btn-run-multi");
  const btnRunBaseline = document.getElementById("btn-run-baseline");
  const btnRunBenchmark = document.getElementById("btn-run-benchmark");
  const btnReBenchmark = document.getElementById("btn-re-benchmark");

  const graphStateBadge = document.getElementById("graph-state-badge");
  const nodeSupervisor = document.getElementById("node-supervisor");
  const nodeResearcher = document.getElementById("node-researcher");
  const nodeAnalyst = document.getElementById("node-analyst");
  const nodeWriter = document.getElementById("node-writer");
  const nodeCritic = document.getElementById("node-critic");
  const nodeDone = document.getElementById("node-done");

  const hudLatency = document.getElementById("hud-latency");
  const hudCost = document.getElementById("hud-cost");
  const hudQuality = document.getElementById("hud-quality");
  const hudCitation = document.getElementById("hud-citation");
  const hudHops = document.getElementById("hud-hops");

  const finalAnswerContent = document.getElementById("final-answer-content");
  const analysisNotesContent = document.getElementById("analysis-notes-content");
  const sourcesListContent = document.getElementById("sources-list-content");
  const traceJsonContent = document.getElementById("trace-json-content");

  // Arena elements
  const abLat = document.getElementById("ab-lat");
  const abCost = document.getElementById("ab-cost");
  const abCite = document.getElementById("ab-cite");
  const arenaBaselineContent = document.getElementById("arena-baseline-content");

  const amLat = document.getElementById("am-lat");
  const amCost = document.getElementById("am-cost");
  const amCite = document.getElementById("am-cite");
  const amQual = document.getElementById("am-qual");
  const arenaMultiContent = document.getElementById("arena-multi-content");

  // Benchmark table
  const benchmarkTbody = document.getElementById("benchmark-tbody");

  // Slider update
  maxSourcesInput.addEventListener("input", (e) => {
    sourcesVal.textContent = e.target.value;
  });

  // Critic toggle display node
  criticToggle.addEventListener("change", (e) => {
    nodeCritic.style.display = e.target.checked ? "flex" : "none";
  });

  // Tab switching
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      const target = document.getElementById(btn.dataset.tab);
      if (target) target.classList.add("active");
    });
  });

  // Subtab switching
  document.querySelectorAll(".subtab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".subtab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".subtab-content").forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      const target = document.getElementById(btn.dataset.subtab);
      if (target) target.classList.add("active");
    });
  });

  // Fetch available topics
  async function loadTopics() {
    try {
      const res = await fetch("/api/topics");
      if (res.ok) {
        const topics = await res.json();
        topicSelect.innerHTML = '<option value="">-- Chọn chủ đề từ Corpus 30 Topics --</option>';
        topics.forEach((t) => {
          const opt = document.createElement("option");
          opt.value = t.question || t.name;
          opt.textContent = `${t.id}: ${t.name}`;
          topicSelect.appendChild(opt);
        });
      }
    } catch (e) {
      console.warn("Could not load topics:", e);
    }
  }
  loadTopics();

  topicSelect.addEventListener("change", (e) => {
    if (e.target.value) {
      queryInput.value = e.target.value;
    }
  });

  // Simple Markdown renderer
  function renderMarkdown(md) {
    if (!md) return "";
    let html = md
      .replace(/^### (.*$)/gim, "<h3>$1</h3>")
      .replace(/^## (.*$)/gim, "<h2>$1</h2>")
      .replace(/^# (.*$)/gim, "<h1>$1</h1>")
      .replace(/\*\*(.*?)\*\*/gim, "<b>$1</b>")
      .replace(/\*(.*?)\*/gim, "<i>$1</i>")
      .replace(/`([^`]+)`/gim, "<code>$1</code>")
      .replace(/^\s*-\s+(.*$)/gim, "<li>$1</li>")
      .replace(/\[(\d+)\]/gim, '<span class="citation-badge">[$1]</span>')
      .replace(/\n\n/gim, "</p><p>")
      .replace(/\n/gim, "<br>");
    return `<p>${html}</p>`;
  }

  // Node highlight animation
  function clearNodeHighlights() {
    document.querySelectorAll(".node-item").forEach((n) => n.classList.remove("active"));
  }

  async function animateRoutes(routeHistory) {
    const nodeMap = {
      supervisor: nodeSupervisor,
      researcher: nodeResearcher,
      analyst: nodeAnalyst,
      writer: nodeWriter,
      critic: nodeCritic,
      done: nodeDone,
    };

    for (const r of routeHistory) {
      clearNodeHighlights();
      const node = nodeMap[r];
      if (node) {
        node.classList.add("active");
      }
      await new Promise((resolve) => setTimeout(resolve, 350));
    }
  }

  // Run Multi-Agent
  btnRunMulti.addEventListener("click", async () => {
    const query = queryInput.value.trim();
    if (!query) return alert("Vui lòng nhập câu hỏi nghiên cứu!");

    btnRunMulti.disabled = true;
    btnRunMulti.innerHTML = '<span>⏳ Đang điều phối...</span>';
    graphStateBadge.textContent = "Running";
    graphStateBadge.className = "state-badge running";
    clearNodeHighlights();

    try {
      const payload = {
        query: query,
        max_sources: parseInt(maxSourcesInput.value, 10),
        audience: audienceSelect.value,
        enable_critic: criticToggle.checked,
      };

      const res = await fetch("/api/run-multi", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();

      // Animate Graph
      await animateRoutes(data.route_history);

      // Update HUD
      hudLatency.textContent = `${data.latency_seconds}s`;
      hudCost.textContent = `$${data.cost_usd.toFixed(6)}`;
      hudQuality.textContent = `${data.quality_score}/10`;
      hudCitation.textContent = `${(data.citation_coverage * 100).toFixed(0)}%`;
      hudHops.textContent = `${data.iteration} hops`;

      // Update Contents
      finalAnswerContent.innerHTML = renderMarkdown(data.final_answer);
      analysisNotesContent.innerHTML = renderMarkdown(data.analysis_notes);
      traceJsonContent.textContent = JSON.stringify(data.trace, null, 2);

      // Render Sources
      sourcesListContent.innerHTML = "";
      if (data.sources && data.sources.length > 0) {
        data.sources.forEach((s, i) => {
          const div = document.createElement("div");
          div.className = "source-item";
          div.innerHTML = `
            <div class="source-title">[${i + 1}] ${s.title}</div>
            <div class="source-url">${s.url || "Offline Corpus"}</div>
            <div class="source-snippet">${s.snippet}</div>
          `;
          sourcesListContent.appendChild(div);
        });
      } else {
        sourcesListContent.innerHTML = '<div class="placeholder-box">Không có tài liệu nào.</div>';
      }

      // Update Arena Multi View
      amLat.textContent = `${data.latency_seconds}s`;
      amCost.textContent = `$${data.cost_usd.toFixed(6)}`;
      amCite.textContent = `${(data.citation_coverage * 100).toFixed(0)}%`;
      amQual.textContent = `${data.quality_score}/10`;
      arenaMultiContent.innerHTML = renderMarkdown(data.final_answer);

      graphStateBadge.textContent = "Completed";
      graphStateBadge.className = "state-badge done";
    } catch (err) {
      alert("Lỗi khi chạy multi-agent: " + err.message);
      graphStateBadge.textContent = "Error";
    } finally {
      btnRunMulti.disabled = false;
      btnRunMulti.innerHTML = '<span>🚀 Chạy Multi-Agent Workflow</span>';
    }
  });

  // Run Baseline
  btnRunBaseline.addEventListener("click", async () => {
    const query = queryInput.value.trim();
    if (!query) return alert("Vui lòng nhập câu hỏi nghiên cứu!");

    btnRunBaseline.disabled = true;
    btnRunBaseline.innerHTML = '<span>⏳ Đang chạy...</span>';

    try {
      const res = await fetch("/api/run-baseline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query }),
      });

      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();

      // Update Arena Baseline View
      abLat.textContent = `${data.latency_seconds}s`;
      abCost.textContent = `$${data.cost_usd.toFixed(6)}`;
      abCite.textContent = `${(data.citation_coverage * 100).toFixed(0)}%`;
      arenaBaselineContent.innerHTML = renderMarkdown(data.final_answer);

      // Switch tab to Arena
      document.querySelector('[data-tab="arena-tab"]').click();
    } catch (err) {
      alert("Lỗi khi chạy baseline: " + err.message);
    } finally {
      btnRunBaseline.disabled = false;
      btnRunBaseline.innerHTML = '<span>⚡ Chạy Single-Agent Baseline</span>';
    }
  });

  // Run Benchmark
  async function triggerBenchmark() {
    btnRunBenchmark.disabled = true;
    btnRunBenchmark.innerHTML = '<span>⏳ Đang đo đạc benchmark...</span>';
    if (btnReBenchmark) btnReBenchmark.disabled = true;

    try {
      const res = await fetch("/api/benchmark", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          queries: [
            queryInput.value.trim() || "Research GraphRAG state-of-the-art and write a 500-word summary",
            "Compare single-agent and multi-agent workflows for customer support",
            "Summarize production guardrails for LLM agents",
          ],
        }),
      });

      if (!res.ok) throw new Error(await res.text());
      const rows = await res.json();

      benchmarkTbody.innerHTML = "";
      rows.forEach((r) => {
        const tr = document.createElement("tr");
        const isMulti = r.run_name.toLowerCase().includes("multi");
        tr.style.background = isMulti ? "rgba(16, 185, 129, 0.05)" : "transparent";
        tr.innerHTML = `
          <td><b>${r.run_name}</b></td>
          <td>${r.latency_seconds.toFixed(3)}s</td>
          <td>$${(r.estimated_cost_usd || 0).toFixed(4)}</td>
          <td><b>${r.quality_score || 0}/10</b></td>
          <td>${((r.citation_coverage || 0) * 100).toFixed(0)}%</td>
          <td>${((r.failure_rate || 0) * 100).toFixed(0)}%</td>
          <td><span style="color:#9ca3af;font-size:0.82rem;">${r.notes}</span></td>
        `;
        benchmarkTbody.appendChild(tr);
      });

      // Switch tab to benchmark
      document.querySelector('[data-tab="benchmark-tab"]').click();
    } catch (err) {
      alert("Lỗi khi chạy benchmark: " + err.message);
    } finally {
      btnRunBenchmark.disabled = false;
      btnRunBenchmark.innerHTML = '<span>📊 Chạy Benchmark So Sánh</span>';
      if (btnReBenchmark) btnReBenchmark.disabled = false;
    }
  }

  btnRunBenchmark.addEventListener("click", triggerBenchmark);
  if (btnReBenchmark) btnReBenchmark.addEventListener("click", triggerBenchmark);
});
