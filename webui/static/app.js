/* Trading Control Center — frontend logic (no framework, no build step) */

"use strict";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const state = {
  status: null,        // /api/status
  catalog: null,       // /api/catalog
  jobs: [],            // /api/jobs
  runs: [],            // /api/runs
  view: "overview",
  actionsRendered: false,
  settingsRendered: false,
  strategiesRendered: false,
  logPoll: null,       // {jobId, offset, timer}
  livePoll: null,
};

const PERIOD_COLORS = ["#58a6ff", "#bc8cff", "#3fb950", "#d29922", "#f85149", "#39c5cf"];

// ---------------------------------------------------------------------------
// Helper functions
// ---------------------------------------------------------------------------

function $(id) { return document.getElementById(id); }

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

async function api(path, opts) {
  const res = await fetch(path, opts);
  let data = null;
  try { data = await res.json(); } catch (e) { /* empty */ }
  if (!res.ok) {
    throw new Error((data && data.error) || `HTTP ${res.status}`);
  }
  return data;
}

function fmtMoney(v, cur) {
  if (v === null || v === undefined || isNaN(v)) return "–";
  return Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 }) + (cur ? " " + cur : "");
}

function fmtPct(v, digits = 1) {
  if (v === null || v === undefined || isNaN(v)) return "–";
  const n = Number(v);
  return (n >= 0 ? "+" : "") + n.toFixed(digits) + "%";
}

function fmtDateTime(iso) {
  if (!iso) return "–";
  return String(iso).replace("T", " ").slice(0, 16);
}

function duration(startIso, endIso) {
  if (!startIso) return "";
  const start = new Date(startIso);
  const end = endIso ? new Date(endIso) : new Date();
  let sec = Math.max(0, Math.round((end - start) / 1000));
  const h = Math.floor(sec / 3600); sec -= h * 3600;
  const m = Math.floor(sec / 60); sec -= m * 60;
  if (h > 0) return `${h}h ${m}min`;
  if (m > 0) return `${m}min ${sec}s`;
  return `${sec}s`;
}

function toast(msg, type = "info", ms = 5000) {
  const el = $("toast");
  el.textContent = msg;
  el.className = `toast ${type}`;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add("hidden"), ms);
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

const VIEWS = ["overview", "actions", "runs", "strategies", "live", "problems", "settings"];

function setView(view) {
  if (!VIEWS.includes(view)) view = "overview";
  state.view = view;
  for (const v of VIEWS) {
    $(`view-${v}`).classList.toggle("hidden", v !== view);
  }
  document.querySelectorAll(".nav-item").forEach(a => {
    a.classList.toggle("active", a.dataset.view === view);
  });
  if (view === "actions") renderActions();
  if (view === "strategies") renderStrategies();
  if (view === "settings") renderSettings();
  if (view === "runs") { renderJobs(); renderRuns(); }
  if (view === "live") { renderLiveControls(); refreshLive(); }
  if (view === "problems") renderProblems();
  if (view === "overview") renderDashboard();
}

window.addEventListener("hashchange", () => setView(location.hash.slice(1)));

// ---------------------------------------------------------------------------
// Load data
// ---------------------------------------------------------------------------

async function loadStatus(force = false) {
  try {
    state.status = await api(`/api/status${force ? "?force=1" : ""}`);
  } catch (e) {
    state.status = { mt5: { connected: false, error: String(e) }, config: {}, problems: [] };
  }
  updateGlobalIndicators();
  if (state.view === "overview") renderDashboard();
  if (state.view === "problems") renderProblems();
}

async function loadCatalog() {
  state.catalog = await api("/api/catalog");
}

async function loadJobs() {
  try {
    const prev = JSON.stringify(state.jobs.map(j => j.status));
    const data = await api("/api/jobs");
    state.jobs = data.jobs || [];
    const now = JSON.stringify(state.jobs.map(j => j.status));
    updateGlobalIndicators();
    if (prev !== now) {
      loadRuns();
      if (state.view === "overview") renderDashboard();
      if (state.view === "live") renderLiveControls();
    }
    if (state.view === "runs") renderJobs();
  } catch (e) { /* server briefly unreachable */ }
}

async function loadRuns() {
  try {
    const data = await api("/api/runs");
    state.runs = data.runs || [];
    if (state.view === "runs") renderRuns();
    if (state.view === "overview") renderDashboard();
  } catch (e) { /* ignore */ }
}

// ---------------------------------------------------------------------------
// Global indicators (sidebar, banner)
// ---------------------------------------------------------------------------

function updateGlobalIndicators() {
  const mt5 = state.status?.mt5 || {};
  const pill = $("mt5Pill");
  if (mt5.connected && mt5.terminal?.market_connected) {
    pill.className = "pill pill-ok";
    pill.textContent = "MT5: connected";
  } else if (mt5.connected) {
    pill.className = "pill pill-bad";
    pill.textContent = "MT5: no broker link";
  } else {
    pill.className = "pill pill-bad";
    pill.textContent = "MT5: disconnected";
  }

  const running = state.jobs.filter(j => j.status === "running");
  const jobPill = $("jobPill");
  if (running.length > 0) {
    jobPill.className = "pill pill-busy";
    jobPill.textContent = `${running.length} run${running.length > 1 ? "s" : ""} active`;
  } else {
    jobPill.className = "pill pill-idle";
    jobPill.textContent = "No active runs";
  }

  const problems = state.status?.problems || [];
  const badge = $("problemBadge");
  badge.classList.toggle("hidden", problems.length === 0);
  badge.textContent = problems.length;

  const critical = problems.filter(p => p.severity === "critical");
  const banner = $("problemBanner");
  if (critical.length > 0 && state.view !== "problems") {
    banner.classList.remove("hidden");
    banner.innerHTML = `🚨 <strong>${critical.length} critical issue${critical.length > 1 ? "s" : ""}:</strong> ` +
      esc(critical[0].title) + ` — <a href="#problems">View details &amp; fix</a>`;
  } else {
    banner.classList.add("hidden");
  }
}

// ---------------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------------

function renderDashboard() {
  const s = state.status;
  if (!s) return;
  const mt5 = s.mt5 || {};
  const cfg = s.config || {};
  const acc = mt5.account;

  const cards = [];

  cards.push(card("MT5 Terminal",
    mt5.connected ? "Connected" : "Disconnected",
    mt5.connected
      ? `${esc(mt5.terminal?.name || "")} Build ${esc(mt5.terminal?.build || "")} · Broker: ${mt5.terminal?.market_connected ? "online" : "<span class='neg'>offline</span>"} · Algo Trading: ${mt5.terminal?.trade_allowed ? "<span class='pos'>on</span>" : "<span class='neg'>off</span>"}`
      : esc(mt5.error || "Start terminal and log in."),
    mt5.connected ? "pos" : "neg"));

  if (acc) {
    const mode = acc.trade_mode === 0 ? "Demo account" : (acc.trade_mode === 2 ? "Live account" : "Account");
    cards.push(card(mode,
      fmtMoney(acc.equity, acc.currency),
      `Login ${esc(acc.login)} · ${esc(acc.server)} · Balance ${fmtMoney(acc.balance, acc.currency)}`));
  }

  cards.push(card(`Symbol: ${esc(cfg.symbol || "?")}`,
    mt5.last_price ? Number(mt5.last_price).toLocaleString("en-US") : "–",
    mt5.symbol_ok === false
      ? "<span class='neg'>Symbol not available in terminal!</span>"
      : `M5 data from ${esc(mt5.m5_history_start || "?")} · last bar ${fmtDateTime(mt5.m5_last_candle)}`));

  cards.push(card("Simulation settings",
    `${esc(cfg.simulation_start_date)} → ${esc(cfg.simulation_end_date)}`,
    `Starting capital ${fmtMoney(cfg.simEQ, cfg.simAccCurency)} · Timeframe ${esc(cfg.timeframe)} · `
    + `Rollover/Swap ${cfg.simSwapEnabled === false ? "<span class='neg'>off</span>" : "<span class='pos'>on</span>"} · `
    + `Trade export ${cfg.simExportTradeHistory ? "<span class='pos'>on</span>" : "<span class='dim'>off</span>"} · <a href="#settings">edit</a>`));

  const problems = s.problems || [];
  cards.push(card("Issues",
    problems.length === 0 ? "None" : String(problems.length),
    problems.length === 0
      ? "All clear."
      : `${problems.filter(p => p.severity === "critical").length} critical · <a href="#problems">view</a>`,
    problems.length === 0 ? "pos" : (problems.some(p => p.severity === "critical") ? "neg" : "")));

  const liveJob = state.jobs.find(j => j.status === "running" && j.dangerous);
  cards.push(card("Live Trading",
    liveJob ? "ACTIVE" : "Stopped",
    liveJob
      ? `running since ${fmtDateTime(liveJob.started_at)} · <a href="#live">monitor</a>`
      : `<a href="#live">go to live section</a>`,
    liveJob ? "pos" : ""));

  $("dashCards").innerHTML = cards.join("");

  // Recent jobs
  const recent = state.jobs.slice(0, 5);
  $("dashJobs").innerHTML = recent.length === 0
    ? `<div class="card dim">No runs started from this UI yet. Start one under <a href="#actions">Actions</a>.</div>`
    : recent.map(jobCard).join("");

  // Latest reports
  const runs = state.runs.slice(0, 5);
  $("dashRuns").innerHTML = runs.length === 0
    ? `<div class="card dim">No reports yet.</div>`
    : `<div class="card"><table class="data"><thead><tr><th>Created</th><th>Report</th><th></th></tr></thead><tbody>` +
      runs.map(r => `<tr>
        <td class="dim">${fmtDateTime(r.created)}</td>
        <td>${esc(r.label)}</td>
        <td>
          ${r.main_html ? `<button class="btn btn-small" onclick="openReport('${esc(r.name)}','${esc(r.main_html)}')">Open report</button>` : ""}
          <button class="btn btn-small btn-ghost" onclick="openRunDetail('${esc(r.name)}')">Details &amp; history</button>
        </td></tr>`).join("") +
      `</tbody></table></div>`;
}

function card(label, value, sub, valueClass = "") {
  return `<div class="card stat-card">
    <div class="stat-label">${label}</div>
    <div class="stat-value ${valueClass}">${value}</div>
    <div class="stat-sub">${sub || ""}</div>
  </div>`;
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

function renderActions() {
  if (!state.catalog || state.actionsRendered) return;
  state.actionsRendered = true;

  const byCategory = {};
  for (const a of state.catalog.actions) {
    (byCategory[a.category] = byCategory[a.category] || []).push(a);
  }
  const order = ["Backtest", "Analysis", "Live"];
  let html = "";
  for (const cat of order) {
    if (!byCategory[cat]) continue;
    html += `<div class="action-category">${esc(cat)}</div>`;
    for (const a of byCategory[cat]) html += actionCard(a);
  }
  $("actionList").innerHTML = html;
}

function actionCard(a) {
  const tags = [];
  if (a.recommended) tags.push(`<span class="tag tag-recommended">Recommended to start</span>`);
  if (a.dangerous) tags.push(`<span class="tag tag-danger">⚠ Real orders!</span>`);

  let params = "";
  for (const p of a.params || []) {
    params += paramField(a.id, p);
  }

  const startBtn = a.dangerous
    ? `<button class="btn btn-danger" onclick="startAction('${a.id}')">🔴 Start live trading…</button>`
    : `<button class="btn btn-primary" onclick="startAction('${a.id}')">▶ Start</button>`;

  return `<div class="card action-card" id="action_${a.id}">
    <div class="action-head">
      <span class="action-title">${esc(a.title)}</span>
      ${tags.join(" ")}
    </div>
    <div class="action-desc">${esc(a.description)}</div>
    <div class="action-meta">Duration: ${esc(a.duration_hint || "unknown")} · Script: <code>${esc(a.script)}</code></div>
    ${params ? `<div class="param-grid">${params}</div>` : ""}
    ${startBtn}
  </div>`;
}

function paramField(actionId, p) {
  const id = `p_${actionId}_${p.name}`;
  const label = esc(p.label) + (p.required ? " *" : "");
  switch (p.type) {
    case "date":
      return `<div class="param-field"><label for="${id}">${label}</label>
        <input type="date" id="${id}" value="${esc(p.default || "")}"/></div>`;
    case "text":
      return `<div class="param-field"><label for="${id}">${label}</label>
        <input type="text" id="${id}" value="${esc(p.default || "")}"/></div>`;
    case "bool":
      return `<div class="param-check"><input type="checkbox" id="${id}" ${p.default ? "checked" : ""}/>
        <label for="${id}">${label}</label></div>`;
    case "variants":
      return `<div class="param-field" style="flex:1 1 100%"><label>${label}</label>${variantPicker(id)}</div>`;
    case "variant_single":
      return `<div class="param-field"><label for="${id}">${label}</label>${variantSelect(id)}</div>`;
    default:
      return "";
  }
}

function variantsByGroup() {
  const groups = {};
  for (const v of state.catalog.variants) {
    (groups[v.group] = groups[v.group] || []).push(v);
  }
  return groups;
}

function groupTitle(g) {
  return state.catalog.groups[g]?.title || g;
}

function variantPicker(id) {
  const groups = variantsByGroup();
  let html = `<div class="variant-picker" id="${id}">
    <input class="vp-search" type="text" placeholder="Search…" oninput="vpFilter('${id}', this.value)"/>`;
  for (const [g, vars] of Object.entries(groups)) {
    html += `<div class="vp-group">${esc(groupTitle(g))}</div>`;
    for (const v of vars) {
      html += `<label data-search="${esc((v.name + " " + v.variant_id).toLowerCase())}">
        <input type="checkbox" value="${esc(v.variant_id)}" onchange="vpCount('${id}')"/>
        <span>${esc(v.name)} <span class="vp-id">[${esc(v.variant_id)}]</span></span>
      </label>`;
    }
  }
  html += `</div><div class="vp-count" id="${id}_count">0 selected</div>`;
  return html;
}

function vpFilter(id, term) {
  term = term.toLowerCase().trim();
  document.querySelectorAll(`#${id} label`).forEach(l => {
    l.style.display = !term || (l.dataset.search || "").includes(term) ? "" : "none";
  });
}

function vpCount(id) {
  const n = document.querySelectorAll(`#${id} input[type=checkbox]:checked`).length;
  const el = $(`${id}_count`);
  if (el) el.textContent = `${n} selected`;
}

function variantSelect(id) {
  const groups = variantsByGroup();
  let html = `<select id="${id}"><option value="">— select —</option>`;
  for (const [g, vars] of Object.entries(groups)) {
    html += `<optgroup label="${esc(groupTitle(g))}">`;
    for (const v of vars) {
      html += `<option value="${esc(v.variant_id)}">${esc(v.name)}</option>`;
    }
    html += `</optgroup>`;
  }
  return html + `</select>`;
}

function collectParams(action) {
  const params = {};
  for (const p of action.params || []) {
    const id = `p_${action.id}_${p.name}`;
    if (p.type === "bool") {
      params[p.name] = $(id)?.checked || false;
    } else if (p.type === "variants") {
      params[p.name] = Array.from(
        document.querySelectorAll(`#${id} input[type=checkbox]:checked`)
      ).map(cb => cb.value);
    } else {
      params[p.name] = $(id)?.value || "";
    }
  }
  return params;
}

async function startAction(actionId, extraConfirmed = false) {
  const action = state.catalog.actions.find(a => a.id === actionId);
  if (!action) return;
  if (action.dangerous && !extraConfirmed) { confirmLiveStart(); return; }

  const params = collectParams(action);
  try {
    const res = await api("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionId, params }),
    });
    toast(`Started: ${action.title}`, "success");
    await loadJobs();
    openJobLog(res.job.job_id, res.job.title);
  } catch (e) {
    toast(`Start failed: ${e.message}`, "error", 8000);
  }
}

// ---------------------------------------------------------------------------
// Jobs
// ---------------------------------------------------------------------------

function jobCard(j) {
  const stText = { running: "running", finished: "finished", failed: "failed", stopped: "stopped" }[j.status] || j.status;
  const runLinks = (j.run_dirs || []).map(d =>
    `<button class="btn btn-small btn-ghost" onclick="openRunDetail('${esc(d)}')">${esc(d.slice(16) || d)} — history</button>`).join(" ");
  return `<div class="card status-${j.status}">
    <div class="job-row">
      <span><span class="status-dot"></span><span class="status-text-${j.status}">${stText}</span></span>
      <span class="job-title">${esc(j.title)}</span>
      <span class="job-meta">${fmtDateTime(j.started_at)} · Duration ${duration(j.started_at, j.ended_at)}${j.args?.length ? " · " + esc(j.args.join(" ")) : ""}</span>
      <span style="margin-left:auto">
        <button class="btn btn-small" onclick="openJobLog('${esc(j.job_id)}','${esc(j.title)}')">📜 Log</button>
        ${j.status === "running" ? `<button class="btn btn-small btn-danger" onclick="stopJob('${esc(j.job_id)}')">⏹ Stop</button>` : ""}
        ${runLinks}
      </span>
    </div>
  </div>`;
}

function renderJobs() {
  const jobs = state.jobs;
  $("jobList").innerHTML = jobs.length === 0
    ? `<div class="card dim">No runs yet. Start one under <a href="#actions">Actions</a>.</div>`
    : jobs.map(jobCard).join("");
}

async function stopJob(jobId) {
  const job = state.jobs.find(j => j.job_id === jobId);
  if (job?.dangerous) {
    if (!confirm("Stop live trading?\n\nOpen positions and pending orders will remain in MT5 and will no longer be managed by the strategy.")) return;
  }
  try {
    await api(`/api/jobs/${jobId}/stop`, { method: "POST" });
    toast("Stopping job…", "info");
    loadJobs();
  } catch (e) {
    toast(`Stop failed: ${e.message}`, "error");
  }
}

// ---- Log modal ----

function openJobLog(jobId, title) {
  stopLogPoll();
  openModal(`Log: ${esc(title || jobId)}`,
    `<pre class="log" id="logBox">Loading…</pre>
     <div class="job-meta" id="logStatus"></div>`);
  state.logPoll = { jobId, offset: 0 };
  pollLog();
}

async function pollLog() {
  if (!state.logPoll) return;
  try {
    const data = await api(`/api/jobs/${state.logPoll.jobId}/log?offset=${state.logPoll.offset}`);
    const box = $("logBox");
    if (!box) { stopLogPoll(); return; }
    if (state.logPoll.offset === 0) box.textContent = "";
    if (data.content) {
      box.textContent += data.content;
      box.scrollTop = box.scrollHeight;
    }
    state.logPoll.offset = data.offset;
    const stText = { running: "⏳ running…", finished: "✅ finished", failed: "❌ failed", stopped: "⏹ stopped" }[data.status] || data.status;
    const st = $("logStatus");
    if (st) st.textContent = `Status: ${stText}`;
    if (data.status === "running") {
      state.logPoll.timer = setTimeout(pollLog, 1500);
    } else {
      loadJobs(); loadRuns();
    }
  } catch (e) {
    stopLogPoll();
  }
}

function stopLogPoll() {
  if (state.logPoll?.timer) clearTimeout(state.logPoll.timer);
  state.logPoll = null;
}

// ---------------------------------------------------------------------------
// Reports (runs)
// ---------------------------------------------------------------------------

function renderRuns() {
  const runs = state.runs;
  $("runList").innerHTML = runs.length === 0
    ? `<div class="card dim">No reports found.</div>`
    : `<div class="card"><table class="data">
        <thead><tr><th>Created</th><th>Name</th><th>Files</th><th></th></tr></thead><tbody>` +
      runs.map(r => `<tr>
        <td class="dim">${fmtDateTime(r.created)}</td>
        <td>${esc(r.label)}</td>
        <td class="dim">${r.files.length}</td>
        <td>
          ${r.main_html ? `<button class="btn btn-small" onclick="openReport('${esc(r.name)}','${esc(r.main_html)}')">Open report</button>` : ""}
          <button class="btn btn-small btn-ghost" onclick="openRunDetail('${esc(r.name)}')">Details &amp; history</button>
        </td></tr>`).join("") +
      `</tbody></table></div>`;
}

function openReport(runName, file) {
  openModal(`Report: ${esc(runName)} / ${esc(file)}`,
    `<iframe class="report" src="/reports/runs/${encodeURIComponent(runName)}/${encodeURIComponent(file)}"></iframe>
     <p class="dim" style="margin-top:8px">Summary table only. For the full trade list and period metrics,
     use <strong>Details &amp; history</strong>. Per-window HTML reports: <code>period_*.html</code>.</p>
     <p class="dim">Open in new tab:
     <a href="/reports/runs/${encodeURIComponent(runName)}/${encodeURIComponent(file)}" target="_blank">${esc(file)}</a></p>`);
}

async function openRunDetail(runName) {
  openModal(`Report: ${esc(runName)}`, `<div class="dim">Loading…</div>`);
  let d;
  try {
    d = await api(`/api/runs/${encodeURIComponent(runName)}`);
  } catch (e) {
    $("modalBody").innerHTML = `<div class="neg">Error: ${esc(e.message)}</div>`;
    return;
  }

  try {
    let html = "";

    html += `<h3>Files</h3><p>` + d.files.map(f =>
      `<a href="/reports/runs/${encodeURIComponent(runName)}/${encodeURIComponent(f.name)}" target="_blank">${esc(f.name)}</a>`
    ).join(" · ") + `</p>`;

    const periodHtml = (d.files || []).filter(f => /^period_.*\.html$/i.test(f.name));
    if (periodHtml.length) {
      html += `<p class="dim">Period reports:
        ${periodHtml.map(f =>
          `<a href="/reports/runs/${encodeURIComponent(runName)}/${encodeURIComponent(f.name)}" target="_blank">${esc(f.name)}</a>`
        ).join(" · ")}</p>`;
    }

    for (const ds of d.datasets || []) {
      if (ds.kind === "multi_period") {
        html += `<h3>Returns by period (from ${esc(ds.file)})</h3>`;
        html += multiPeriodChart(ds.data);
        html += multiPeriodTable(ds.data);
      } else if (ds.kind === "single_window") {
        html += `<h3>Result comparison (from ${esc(ds.file)})</h3>`;
        html += singleWindowChart(ds.data);
        html += singleWindowTable(ds.data);
      }
    }

    for (const [name, text] of Object.entries(d.texts || {})) {
      html += `<details class="collapse"><summary>${esc(name)}</summary><pre class="log">${esc(text)}</pre></details>`;
    }

    if (d.trades) {
      html += renderTradeHistory(d.trades);
    }

    $("modalBody").innerHTML = html;
  } catch (e) {
    $("modalBody").innerHTML = `<div class="neg">Could not render report: ${esc(e.message)}</div>`;
  }
}

function flattenTrades(tradesData) {
  const rows = [];
  for (const [vid, val] of Object.entries(tradesData || {})) {
    if (Array.isArray(val)) {
      for (const t of val) rows.push({ ...t, variant_id: vid });
    } else if (val && typeof val === "object") {
      for (const [period, list] of Object.entries(val)) {
        for (const t of list) rows.push({ ...t, variant_id: vid, period });
      }
    }
  }
  return rows.sort((a, b) => String(a.close_time || "").localeCompare(String(b.close_time || "")));
}

function renderTradeHistory(tradesData) {
  const rows = flattenTrades(tradesData);
  if (!rows.length) return "";
  const variants = [...new Set(rows.map(r => r.variant_id))];
  let html = `<h3>Trade history <span class="dim">(${rows.length} closed)</span></h3>`;
  if (variants.length > 1) {
    html += `<p><label class="dim">Filter strategy </label>
      <select id="tradeHistFilter" onchange="filterTradeTable()">
        <option value="">All</option>
        ${variants.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join("")}
      </select></p>`;
  }
  html += `<div class="card table-wrap"><table class="data" id="tradeHistTable">
    <thead><tr>
      <th>Close</th><th>Strategy</th><th>Dir</th><th class="num">Entry</th><th class="num">Exit</th>
      <th class="num">SL</th><th class="num">TP</th><th class="num">R</th><th class="num">PnL</th><th>Outcome</th>
    </tr></thead><tbody>`;
  for (const t of rows) {
    const pnlCls = (t.pnl || 0) >= 0 ? "pos" : "neg";
    html += `<tr data-variant="${esc(t.variant_id)}">
      <td class="dim">${esc(fmtDateTime(t.close_time))}</td>
      <td>${esc(t.variant_id)}${t.period ? `<br/><span class="dim">${esc(t.period)}</span>` : ""}</td>
      <td>${esc(t.direction || "")}</td>
      <td class="num">${t.entry != null ? Number(t.entry).toFixed(2) : "–"}</td>
      <td class="num">${t.exit != null ? Number(t.exit).toFixed(2) : "–"}</td>
      <td class="num">${t.initial_stop_loss != null ? Number(t.initial_stop_loss).toFixed(2) : "–"}</td>
      <td class="num">${t.take_profit != null ? Number(t.take_profit).toFixed(2) : "–"}</td>
      <td class="num ${pnlCls}">${t.r != null ? (t.r >= 0 ? "+" : "") + Number(t.r).toFixed(2) : "–"}</td>
      <td class="num ${pnlCls}">${t.pnl != null ? Number(t.pnl).toLocaleString(undefined, {maximumFractionDigits: 0}) : "–"}</td>
      <td class="dim">${esc(t.outcome || "")}</td>
    </tr>`;
  }
  return html + `</tbody></table></div>`;
}

function filterTradeTable() {
  const sel = $("tradeHistFilter")?.value || "";
  document.querySelectorAll("#tradeHistTable tbody tr").forEach(tr => {
    tr.style.display = !sel || tr.dataset.variant === sel ? "" : "none";
  });
}

// ---------------------------------------------------------------------------
// Charts (plain SVG, no library)
// ---------------------------------------------------------------------------

function svgBarChart(items, seriesNames) {
  // items: [{label, values:[..]}]; seriesNames: series names (colors)
  const barW = 16, gapInGroup = 3, gapBetween = 26;
  const groupW = seriesNames.length * (barW + gapInGroup) + gapBetween;
  const w = Math.max(640, items.length * groupW + 90);
  const h = 280, padL = 56, padB = 70, padT = 14;
  const plotH = h - padB - padT;

  let min = 0, max = 0;
  for (const it of items) for (const v of it.values) {
    if (v === null || isNaN(v)) continue;
    min = Math.min(min, v); max = Math.max(max, v);
  }
  if (max === min) max = min + 1;
  const range = max - min;
  const y = v => padT + plotH - ((v - min) / range) * plotH;

  let svg = `<svg width="${w}" height="${h}" xmlns="http://www.w3.org/2000/svg" style="font-family:'Segoe UI',sans-serif">`;

  // Y axis + grid
  const ticks = 5;
  for (let i = 0; i <= ticks; i++) {
    const val = min + (range * i) / ticks;
    const yy = y(val);
    svg += `<line x1="${padL}" y1="${yy}" x2="${w - 10}" y2="${yy}" stroke="#30363d" stroke-width="1"/>`;
    svg += `<text x="${padL - 6}" y="${yy + 4}" text-anchor="end" font-size="11" fill="#8b949e">${val.toFixed(0)}%</text>`;
  }
  // Zero line
  if (min < 0 && max > 0) {
    svg += `<line x1="${padL}" y1="${y(0)}" x2="${w - 10}" y2="${y(0)}" stroke="#8b949e" stroke-width="1.4"/>`;
  }

  items.forEach((it, gi) => {
    const gx = padL + 10 + gi * groupW;
    it.values.forEach((v, si) => {
      if (v === null || isNaN(v)) return;
      const x = gx + si * (barW + gapInGroup);
      const y0 = y(Math.max(0, Math.min(v, max)));
      const y1 = y(Math.max(min, Math.min(0, v)));
      const barH = Math.max(1, Math.abs(y(v) - y(0)));
      const top = v >= 0 ? y(v) : y(0);
      svg += `<rect x="${x}" y="${top}" width="${barW}" height="${barH}" rx="2"
        fill="${PERIOD_COLORS[si % PERIOD_COLORS.length]}" opacity="0.9">
        <title>${esc(it.label)} – ${esc(seriesNames[si])}: ${v >= 0 ? "+" : ""}${v.toFixed(1)}%</title></rect>`;
    });
    // Group label
    const cx = gx + (seriesNames.length * (barW + gapInGroup)) / 2;
    const label = it.label.length > 22 ? it.label.slice(0, 21) + "…" : it.label;
    svg += `<text x="${cx}" y="${h - padB + 14}" font-size="10" fill="#c9d1d9"
      transform="rotate(-28 ${cx} ${h - padB + 14})" text-anchor="end">${esc(label)}</text>`;
  });

  svg += `</svg>`;

  const legend = seriesNames.map((n, i) =>
    `<span><span class="swatch" style="background:${PERIOD_COLORS[i % PERIOD_COLORS.length]}"></span>${esc(n)}</span>`).join("");

  return `<div class="chart-legend">${legend}</div><div class="chart-box card">${svg}</div>`;
}

function multiPeriodChart(raw) {
  const periodLabels = [];
  for (const v of Object.values(raw)) {
    for (const p of Object.keys(v.periods || {})) {
      if (!periodLabels.includes(p)) periodLabels.push(p);
    }
  }
  const items = Object.entries(raw).map(([vid, v]) => ({
    label: v.name || vid,
    values: periodLabels.map(p => {
      const s = (v.periods || {})[p];
      return s && !s.error ? (s.return_pct ?? null) : null;
    }),
  }));
  return svgBarChart(items, periodLabels);
}

function multiPeriodTable(raw) {
  const rows = Object.entries(raw)
    .map(([vid, v]) => ({ vid, v, agg: v.aggregate || {} }))
    .sort((a, b) => (b.agg.consistency ?? -1e9) - (a.agg.consistency ?? -1e9));
  let html = `<div class="card"><table class="data"><thead><tr>
    <th>Strategy</th><th class="num">Mean Ret.</th><th class="num">Worst</th>
    <th class="num">Consistency</th><th class="num">Max DD</th><th class="num">Capture</th>
    <th class="num">Loss Streak</th><th>All profitable</th><th>Prop OK</th>
  </tr></thead><tbody>`;
  for (const { vid, v, agg } of rows) {
    if (agg.error) {
      html += `<tr><td>${esc(v.name || vid)}</td><td colspan="8" class="neg">${esc(agg.error)}</td></tr>`;
      continue;
    }
    html += `<tr>
      <td><strong>${esc(v.name || vid)}</strong><br/><span class="dim">${esc(vid)}</span></td>
      <td class="num ${agg.mean_return_pct >= 0 ? "pos" : "neg"}">${fmtPct(agg.mean_return_pct)}</td>
      <td class="num ${agg.min_return_pct >= 0 ? "pos" : "neg"}">${fmtPct(agg.min_return_pct)}</td>
      <td class="num">${(agg.consistency ?? 0).toFixed(1)}</td>
      <td class="num ${agg.worst_dd_pct >= 10 ? "neg" : ""}">${(agg.worst_dd_pct ?? 0).toFixed(1)}%</td>
      <td class="num">${(agg.mean_capture ?? 0).toFixed(2)}</td>
      <td class="num">${agg.worst_consec_losses ?? "–"}</td>
      <td>${agg.all_profitable ? "<span class='pos'>YES</span>" : "<span class='neg'>NO</span>"}</td>
      <td>${agg.all_prop_ok ? "<span class='pos'>YES</span>" : "<span class='neg'>NO</span>"}</td>
    </tr>`;
  }
  html += `</tbody></table>
    <p class="dim" style="font-size:12px;margin-bottom:0">Consistency = mean return minus standard deviation across periods (penalises single-window luck).
    Capture = share of maximum favourable excursion collected at exit.
    Prop OK = under 5% daily loss and never below 90% of starting capital in every period.</p></div>`;
  return html;
}

function flatSummary(v) { return v.summary || v; }

function singleWindowChart(raw) {
  const items = Object.entries(raw).map(([vid, v]) => {
    const s = flatSummary(v);
    return { label: v.name || vid, values: [s.error ? null : (s.return_pct ?? null)] };
  });
  return svgBarChart(items, ["Window return"]);
}

function singleWindowTable(raw) {
  const rows = Object.entries(raw)
    .map(([vid, v]) => ({ vid, v, s: flatSummary(v) }))
    .sort((a, b) => (b.s.return_pct ?? -1e9) - (a.s.return_pct ?? -1e9));
  let html = `<div class="card"><table class="data"><thead><tr>
    <th>Strategy</th><th class="num">Return</th><th class="num">Win rate</th>
    <th class="num">Profit factor</th><th class="num">Trades</th><th class="num">Max DD</th>
    <th class="num">Max daily loss</th><th>Prop OK</th>
  </tr></thead><tbody>`;
  for (const { vid, v, s } of rows) {
    if (s.error) {
      html += `<tr><td>${esc(v.name || vid)}</td><td colspan="7" class="neg">${esc(s.error)}</td></tr>`;
      continue;
    }
    html += `<tr>
      <td><strong>${esc(v.name || vid)}</strong><br/><span class="dim">${esc(vid)}</span></td>
      <td class="num ${s.return_pct >= 0 ? "pos" : "neg"}">${fmtPct(s.return_pct)}</td>
      <td class="num">${(s.win_rate ?? 0).toFixed(1)}%</td>
      <td class="num">${Math.min(s.profit_factor ?? 0, 99).toFixed(2)}</td>
      <td class="num">${s.trades ?? "–"}</td>
      <td class="num ${(s.max_dd_pct ?? 0) >= 10 ? "neg" : ""}">${(s.max_dd_pct ?? 0).toFixed(1)}%</td>
      <td class="num ${(s.max_daily_loss_pct ?? 0) >= 5 ? "neg" : ""}">${(s.max_daily_loss_pct ?? 0).toFixed(1)}%</td>
      <td>${s.prop_ftmo_ok ? "<span class='pos'>YES</span>" : "<span class='neg'>NO</span>"}</td>
    </tr>`;
  }
  return html + `</tbody></table></div>`;
}

// ---------------------------------------------------------------------------
// Strategy catalog
// ---------------------------------------------------------------------------

function renderStrategies() {
  if (!state.catalog || state.strategiesRendered) return;
  state.strategiesRendered = true;

  const groups = variantsByGroup();
  let html = "";
  for (const [g, vars] of Object.entries(groups)) {
    const info = state.catalog.groups[g] || { title: g, text: "" };
    html += `<div class="card">
      <h3 style="margin-top:0">${esc(info.title)}</h3>
      <p class="dim" style="line-height:1.5">${esc(info.text)}</p>
      <table class="data"><thead><tr><th>Strategy</th><th>ID</th></tr></thead><tbody>` +
      vars.map(v => `<tr><td>${esc(v.name)}</td><td><code>${esc(v.variant_id)}</code></td></tr>`).join("") +
      `</tbody></table></div>`;
  }
  $("strategyCatalog").innerHTML = html;
}

// ---------------------------------------------------------------------------
// Live trading
// ---------------------------------------------------------------------------

function renderLiveControls() {
  const liveJob = state.jobs.find(j => j.status === "running" && j.dangerous);
  const tradeAllowed = state.status?.mt5?.terminal?.trade_allowed;

  let html = `<div class="live-warning">⚠️ <strong>This section controls real trading.</strong>
    Example strategies are for demonstration only — not intended for live use.
    The selected strategy trades the configured symbol on M5 bars via the MT5 account
    logged into the terminal. The loop checks for a new bar every 5 minutes.
    ${tradeAllowed === false ? "<br/><span class='neg'><strong>Warning: Algo Trading is disabled in MT5 — orders will be rejected.</strong></span>" : ""}
  </div>`;

  if (liveJob) {
    html += `<div class="card status-running"><div class="job-row">
      <span><span class="status-dot"></span><span class="status-text-running">Live trading ACTIVE</span></span>
      <span class="job-meta">since ${fmtDateTime(liveJob.started_at)} (${duration(liveJob.started_at, null)})</span>
      <span style="margin-left:auto">
        <button class="btn btn-small" onclick="openJobLog('${esc(liveJob.job_id)}','Live trading')">📜 Log</button>
        <button class="btn btn-danger btn-small" onclick="stopJob('${esc(liveJob.job_id)}')">⏹ Stop live trading</button>
      </span>
    </div></div>`;
  } else {
    html += `<div class="card"><div class="job-row">
      <span class="dim">Live trading is currently stopped.</span>
      <span style="margin-left:auto">
        <button class="btn btn-danger" onclick="confirmLiveStart()">🔴 Start live trading…</button>
      </span>
    </div></div>`;
  }
  html += `<h2>Account &amp; open positions <button class="btn btn-small btn-ghost" onclick="refreshLive()">⟳ Refresh</button></h2>
    <div id="liveData" class="dim">Loading…</div>`;
  $("liveControls").innerHTML = html;
}

function confirmLiveStart() {
  const action = state.catalog?.actions?.find(a => a.id === "live_trading");
  const params = action ? collectParams(action) : {};
  const vid = params.variant;
  if (!vid) {
    toast("Select a strategy in the Live action form first.", "error", 6000);
    return;
  }
  const v = (state.catalog?.variants || []).find(x => x.variant_id === vid);
  const cfg = state.status?.config || {};
  const exampleWarn = v?.group === "Examples"
    ? `<p class="neg"><strong>Example strategy — demonstration only, NOT for production live use.</strong></p>`
    : "";
  openModal("Start live trading — confirmation", `
    <p><strong>You are about to start automated live trading.</strong></p>
    <ul style="line-height:1.7">
      <li>Strategy: <strong>${esc(v?.name || vid)}</strong> <code>${esc(vid)}</code>${v?.group ? ` (${esc(v.group)})` : ""}</li>
      <li>Symbol: <strong>${esc(cfg.symbol || "?")}</strong></li>
      <li>Account: the one currently logged into MT5</li>
      <li>The strategy places orders, adjusts stops, and manages pending orders autonomously.</li>
      <li>When stopped, open positions remain in MT5!</li>
    </ul>
    ${exampleWarn}
    <p>Type <code>LIVE</code> to confirm:</p>
    <p><input class="confirm-input" id="liveConfirmInput" placeholder="LIVE" autocomplete="off"/></p>
    <button class="btn btn-danger" onclick="doLiveStart()">Start live trading</button>
  `);
  setTimeout(() => $("liveConfirmInput")?.focus(), 100);
}

async function doLiveStart() {
  const val = ($("liveConfirmInput")?.value || "").trim();
  if (val !== "LIVE") {
    toast("Confirmation failed — type LIVE exactly.", "error");
    return;
  }
  closeModal();
  await startAction("live_trading", true);
  location.hash = "#live";
}

async function refreshLive() {
  const box = $("liveData");
  if (!box) return;
  try {
    const d = await api("/api/live");
    if (d.error) {
      box.innerHTML = `<div class="card neg">${esc(d.error)}</div>`;
      return;
    }
    let html = "";
    if (d.account) {
      const a = d.account;
      const mode = a.trade_mode === 0 ? "Demo" : (a.trade_mode === 2 ? "Live" : "?");
      html += `<div class="card-grid">` +
        card("Account", `${esc(a.login)} (${mode})`, esc(a.server)) +
        card("Equity", fmtMoney(a.equity, a.currency), `Balance ${fmtMoney(a.balance, a.currency)}`) +
        card("Floating P/L", fmtMoney(a.profit, a.currency), "", (a.profit ?? 0) >= 0 ? "pos" : "neg") +
        card("Free margin", fmtMoney(a.margin_free, a.currency), "") +
        `</div>`;
    }
    html += `<h3>Open positions (${d.positions.length})</h3>`;
    html += d.positions.length === 0
      ? `<div class="card dim">No open positions.</div>`
      : `<div class="card"><table class="data"><thead><tr>
          <th>Ticket</th><th>Symbol</th><th>Type</th><th class="num">Volume</th>
          <th class="num">Entry</th><th class="num">Current</th><th class="num">SL</th><th class="num">TP</th>
          <th class="num">PnL</th><th>Opened</th></tr></thead><tbody>` +
        d.positions.map(p => `<tr>
          <td class="dim">${p.ticket}</td><td>${esc(p.symbol)}</td><td>${esc(p.type)}</td>
          <td class="num">${p.volume}</td><td class="num">${p.price_open}</td><td class="num">${p.price_current}</td>
          <td class="num">${p.sl || "–"}</td><td class="num">${p.tp || "–"}</td>
          <td class="num ${p.profit >= 0 ? "pos" : "neg"}">${fmtMoney(p.profit)}</td>
          <td class="dim">${fmtDateTime(p.time)}</td></tr>`).join("") +
        `</tbody></table></div>`;

    html += `<h3>Pending orders (${d.pending_orders.length})</h3>`;
    html += d.pending_orders.length === 0
      ? `<div class="card dim">No pending orders.</div>`
      : `<div class="card"><table class="data"><thead><tr>
          <th>Ticket</th><th>Symbol</th><th>Type</th><th class="num">Volume</th>
          <th class="num">Price</th><th class="num">SL</th><th class="num">TP</th><th>Placed</th></tr></thead><tbody>` +
        d.pending_orders.map(o => `<tr>
          <td class="dim">${o.ticket}</td><td>${esc(o.symbol)}</td><td>${esc(o.type)}</td>
          <td class="num">${o.volume}</td><td class="num">${o.price_open}</td>
          <td class="num">${o.sl || "–"}</td><td class="num">${o.tp || "–"}</td>
          <td class="dim">${fmtDateTime(o.time_setup)}</td></tr>`).join("") +
        `</tbody></table></div>`;
    html += `<p class="dim" style="font-size:12px">As of ${fmtDateTime(d.checked_at)}</p>`;
    box.innerHTML = html;
  } catch (e) {
    box.innerHTML = `<div class="card neg">Request failed: ${esc(e.message)}</div>`;
  }
}

// ---------------------------------------------------------------------------
// Problems
// ---------------------------------------------------------------------------

function renderProblems() {
  const problems = state.status?.problems || [];
  const sevText = { critical: "CRITICAL", error: "ERROR", warning: "WARNING", info: "INFO" };
  $("problemList").innerHTML = problems.length === 0
    ? `<div class="card"><span class="pos">✅ No issues detected.</span>
       <span class="dim"> MT5 connected, configuration valid, no failed runs.</span></div>`
    : problems.map(p => `<div class="card problem-item sev-${p.severity}">
        <div class="problem-title"><span class="sev-label ${p.severity}">${sevText[p.severity] || p.severity}</span>${esc(p.title)}</div>
        <div class="problem-detail">${esc(p.detail)}</div>
        <div class="problem-hint"><strong>→ Fix:</strong> ${esc(p.hint)}</div>
      </div>`).join("");
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

function renderSettings() {
  if (!state.status) return;
  const cfg = state.status.config || {};
  const timeframes = ["M1", "M5", "M15", "H1", "H4", "D1"];
  $("settingsForm").innerHTML = `
    <div class="settings-grid">
      <div class="param-field">
        <label>Trading symbol</label>
        <input type="text" id="cfg_symbol" value="${esc(cfg.symbol)}"/>
      </div>
      <div class="param-field">
        <label>Timeframe (base configuration)</label>
        <select id="cfg_timeframe">${timeframes.map(t =>
          `<option ${t === cfg.timeframe ? "selected" : ""}>${t}</option>`).join("")}</select>
      </div>
      <div class="param-field">
        <label>Simulation window: start</label>
        <input type="date" id="cfg_start" value="${esc(cfg.simulation_start_date)}"/>
      </div>
      <div class="param-field">
        <label>Simulation window: end</label>
        <input type="date" id="cfg_end" value="${esc(cfg.simulation_end_date)}"/>
      </div>
      <div class="param-field">
        <label>Simulation starting capital</label>
        <input type="text" id="cfg_eq" value="${esc(cfg.simEQ)}"/>
      </div>
      <div class="param-field">
        <label>Account currency (simulation)</label>
        <input type="text" id="cfg_cur" value="${esc(cfg.simAccCurency)}"/>
      </div>
      <div class="param-field">
        <label>Magic number (MT5 order identifier)</label>
        <input type="text" id="cfg_magic" value="${esc(cfg.magic_number)}"/>
      </div>
      <div class="param-field">
        <label>Rollover / swap in simulation</label>
        <select id="cfg_swap">
          <option value="true" ${cfg.simSwapEnabled !== false ? "selected" : ""}>On — model overnight swap (realistic, default)</option>
          <option value="false" ${cfg.simSwapEnabled === false ? "selected" : ""}>Off — ignore holding costs</option>
        </select>
      </div>
      <div class="param-field">
        <label>Export trade history (trades.json on benchmark runs)</label>
        <select id="cfg_export_trades">
          <option value="false" ${!cfg.simExportTradeHistory ? "selected" : ""}>Off — aggregate reports only (default)</option>
          <option value="true" ${cfg.simExportTradeHistory ? "selected" : ""}>On — per-trade list in run folder + Web UI</option>
        </select>
      </div>
    </div>
    <div class="settings-actions">
      <button class="btn btn-primary" onclick="saveSettings()">💾 Save</button>
      <span class="save-msg" id="saveMsg"></span>
    </div>`;
  state.settingsRendered = true;
}

async function saveSettings() {
  const body = {
    symbol: $("cfg_symbol").value,
    timeframe: $("cfg_timeframe").value,
    simulation_start_date: $("cfg_start").value,
    simulation_end_date: $("cfg_end").value,
    simEQ: parseFloat(String($("cfg_eq").value).replace(",", ".")),
    simAccCurency: $("cfg_cur").value,
    magic_number: parseInt($("cfg_magic").value, 10),
    simSwapEnabled: $("cfg_swap").value === "true",
    simExportTradeHistory: $("cfg_export_trades").value === "true",
  };
  try {
    await api("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    $("saveMsg").innerHTML = `<span class="pos">Saved ✓ — applies from the next run.</span>`;
    toast("Settings saved.", "success");
    loadStatus(true);
  } catch (e) {
    $("saveMsg").innerHTML = `<span class="neg">${esc(e.message)}</span>`;
    toast(`Save failed: ${e.message}`, "error", 8000);
  }
}

// ---------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------

function openModal(title, bodyHtml) {
  $("modalTitle").innerHTML = title;
  $("modalBody").innerHTML = bodyHtml;
  $("modalBackdrop").classList.remove("hidden");
}

function closeModal() {
  $("modalBackdrop").classList.add("hidden");
  stopLogPoll();
}

$("modalClose").addEventListener("click", closeModal);
$("modalBackdrop").addEventListener("click", e => {
  if (e.target === $("modalBackdrop")) closeModal();
});
document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

// ---------------------------------------------------------------------------
// Start & Polling
// ---------------------------------------------------------------------------

$("refreshBtn").addEventListener("click", () => {
  toast("Checking MT5 status…", "info", 2500);
  loadStatus(true);
});

async function init() {
  setView(location.hash.slice(1) || "overview");
  try {
    await loadCatalog();
  } catch (e) {
    toast(`Could not load catalog: ${e.message}`, "error", 10000);
  }
  await Promise.all([loadStatus(), loadJobs(), loadRuns()]);
  setView(state.view); // re-render now with data loaded

  setInterval(loadJobs, 4000);
  setInterval(() => loadStatus(false), 30000);
  setInterval(() => { if (state.view === "live") refreshLive(); }, 15000);
}

init();
