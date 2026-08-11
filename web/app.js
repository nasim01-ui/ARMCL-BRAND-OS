/* BrandOS Dashboard - frontend logic + session bootstrap */

function on(id) { return document.getElementById(id); }
const isDashboard = !!on("app");
const isLogin = !!on("login-form");

function clientAuthed() { return sessionStorage.getItem("brandos_token") !== null; }

/* ---- logout ---- */
function doLogout() {
  sessionStorage.removeItem("brandos_token");
  sessionStorage.removeItem("brandos_auth");
  api("/api/logout", { method: "POST" }).catch(() => {});
  location.replace("/login");
}

/* ---- login form ---- */
if (isLogin) {
  on("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const pass = on("login-pass").value;
    const role = (on("login-role") && on("login-role").value) || "md";
    const res = await api("/api/login", { method: "POST", body: JSON.stringify({ password: pass, role: role }) });
    if (res.ok && res.token) {
      sessionStorage.setItem("brandos_token", res.token);
      sessionStorage.setItem("brandos_auth", "true");
      sessionStorage.setItem("brandos_role", res.role || role);
      location.replace("/dashboard");
    } else {
      const errEl = on("login-error");
      if (errEl) { errEl.textContent = res.error || "Invalid password"; errEl.hidden = false; }
    }
  });
  if (clientAuthed()) location.replace("/dashboard");
}

/* ---- role-based menu filtering (Phase 20 recommendation #3) ---- */
const ROLE_PAGES = {
  md: null, // full access
  executive: null, // full access
  marketing: ["dashboard","market","competitors","campaigns","creative","governance","assets","budget","approval","reports","assistant-page","settings"],
  finance: ["dashboard","revenue","budget","approval","reports","assistant-page","settings"],
  sales: ["dashboard","sales","projects","dealers","customers","approval","reports","assistant-page","settings"],
  operations: ["dashboard","sales","field","approval","reports","assistant-page","settings"],
};
const ROLE_LABELS = { md: "MD / CEO", executive: "Executive", marketing: "Marketing Head", finance: "Finance", sales: "Sales", operations: "Operations" };

function applyRoleUI(role) {
  const allowed = ROLE_PAGES[role] || null;
  if (allowed) {
    document.querySelectorAll("#menu .menu-item").forEach((btn) => {
      const page = btn.dataset.page;
      btn.style.display = allowed.includes(page) ? "" : "none";
    });
    document.querySelectorAll("#mobile-nav .menu-item").forEach((btn) => {
      const page = btn.dataset.page;
      btn.style.display = allowed.includes(page) ? "" : "none";
    });
  }
  const prof = document.querySelector(".avatar span");
  if (prof) prof.textContent = ROLE_LABELS[role] || role;
}

/* ---- dashboard ---- */
async function bootstrapDashboard() {
  const loader = on("loader-screen");
  if (!clientAuthed()) {
    location.replace("/login");
    return;
  }
  try {
    const s = await api("/api/session");
    if (!s || s.error || !s.authenticated) {
      location.replace("/login");
      return;
    }
    sessionStorage.setItem("brandos_role", s.role || sessionStorage.getItem("brandos_role") || "md");
    applyRoleUI(sessionStorage.getItem("brandos_role"));
  } catch (_) {
    location.replace("/login");
    return;
  }
  if (loader) loader.style.display = "none";
  if (on("app")) on("app").hidden = false;
  sessionStorage.setItem("brandos_auth", "true");
  init();
}

if (isDashboard) {
  // bfcache / back-navigation protection
  window.addEventListener("pageshow", (e) => { if (e.persisted && !clientAuthed()) location.replace("/login"); });

  document.getElementById("menu-toggle").addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("open");
  });
  document.getElementById("menu").addEventListener("click", (e) => {
    const btn = e.target.closest(".menu-item");
    if (!btn) return;
    switchPage(btn.dataset.page);
  });
  document.getElementById("mobile-nav").addEventListener("click", (e) => {
    const btn = e.target.closest(".menu-item");
    if (btn) switchPage(btn.dataset.page);
  });
  on("logout-btn") && on("logout-btn").addEventListener("click", doLogout);
  bootstrapDashboard();
}

const fmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const fmtBDT = (n) => "৳" + fmt.format(n || 0);
const fmtPct = (n) => (Number(n) || 0).toFixed(1) + "%";

async function api(path, opts = {}) {
  const token = sessionStorage.getItem("brandos_token");
  const headers = opts.headers || {};
  if (token) headers["Authorization"] = "Bearer " + token;
  opts.headers = headers;
  const res = await fetch(path, opts);
  if (res.status === 401) {
    sessionStorage.removeItem("brandos_auth");
    sessionStorage.removeItem("brandos_token");
    if (!isLogin) location.replace("/login");
    return { error: "unauthorized" };
  }
  return res.json();
}

/* ---------- topbar ---------- */
function todayDate() {
  const d = new Date();
  const names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  document.getElementById("today-date").textContent = `${d.getDate()} ${names[d.getMonth()]} ${d.getFullYear()}`;
}

/* ---------- page routing ---------- */
const PAGES = ["dashboard","revenue","sales","market","competitors","projects","dealers",
  "customers","campaigns","creative","governance","assets","field","budget","approval","reports","assistant","settings"];

function switchPage(page) {
  document.querySelectorAll(".pane").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll(".menu-item").forEach((m) => m.classList.remove("active"));
  document.getElementById("page-" + page)?.classList.add("active");
  document.querySelector(`.menu-item[data-page="${page}"]`)?.classList.add("active");
  document.getElementById("mobile-nav")?.querySelectorAll(".menu-item").forEach((b) => b.classList.remove("active"));
  document.querySelector(`#mobile-nav .menu-item[data-page="${page}"]`)?.classList.add("active");
  document.getElementById("sidebar").classList.remove("open");
  loadPage(page);
}

/* ---------- loaders ---------- */
function loadPage(page) {
  switch (page) {
    case "dashboard": loadDashboard(); break;
    case "revenue": loadRevenue(); break;
    case "sales": loadSales(); break;
    case "market": loadMarket(); loadTrend(); break;
    case "competitors": loadStore("competitors"); loadThreat(); break;
    case "projects": loadProjectsSummary(); break;
    case "dealers": loadDealersSummary(); break;
    case "customers": loadStore("customers"); break;
    case "campaigns": loadCampaignsSummary(); break;
    case "creative": loadStore("creative"); break;
    case "governance": loadStore("approvals"); break;
    case "assets": loadStore("assets"); break;
    case "field": loadStore("visibility"); loadStore("visits"); loadFieldReport(); break;
    case "budget": loadBudget(); break;
    case "approval": loadApprovalsSummary(); break;
    case "reports": loadReports(); break;
    case "assistant": break;
    case "settings": break;
  }
}

/* ---------- helpers ---------- */
function table(cols, rows) {
  if (!rows.length) return '<div class="empty">No data yet.</div>';
  let html = "<table><thead><tr>" + cols.map((c) => `<th class="${c.num ? "num" : ""}">${c.label}</th>`).join("") + "</tr></thead><tbody>";
  for (const r of rows) html += "<tr>" + cols.map((c) => `<td class="${c.num ? "num" : ""}">${c.td(r)}</td>`).join("") + "</tr>";
  return html + "</tbody></table>";
}
function badge(status) {
  const map = {
    active: ["green","Active"], running: ["green","Running"], completed: ["blue","Completed"],
    done: ["blue","Done"], pending: ["amber","Pending"], review: ["amber","In Review"],
    paused: ["amber","Paused"], low: ["red","Low"], high: ["green","High"],
    "at risk": ["red","At Risk"], behind: ["red","Behind"], "on track": ["green","On Track"], met: ["blue","Met"],
  };
  const [c, l] = map[String(status || "").toLowerCase()] || ["blue", status || "-"];
  return `<span class="badge ${c}">${l}</span>`;
}

/* ================= DASHBOARD ================= */
let storeCache = {};
async function loadDashboard() {
  const el = (id) => document.getElementById(id);

  // fire all dashboard data requests in parallel so slow DWH calls don't block the UI
  const [o, rev] = await Promise.all([
    api("/api/overview"),
    api("/api/monthly-revenue"),
  ]);

  const t = o.today || {}, w = o.week || {}, m = o.month || {};
  if (el("dash-rev-today")) el("dash-rev-today").textContent = fmtBDT(t.value);
  if (el("dash-sales-today")) el("dash-sales-today").textContent = fmt.format(t.volume) + " CFT";
  if (el("dash-rev-mtd")) el("dash-rev-mtd").textContent = "MTD " + fmtBDT(m.value);

  let target = 55000, achieved = null, ach = 0, tLabel = "", aLabel = "";
  if (o.monthly_target != null) {
    target = o.monthly_target;
    tLabel = " (finance budget)";
  }
  if (o.mtd_sales != null) {
    achieved = o.mtd_sales;
    aLabel = " (statement MTD)";
  }
  ach = (target && achieved) ? Math.round(achieved * 100 / target) : 0;
  if (el("dash-target")) el("dash-target").textContent = achieved != null ? ach + "%" : "--";
  if (el("dash-target-val")) el("dash-target-val").textContent = `of ${fmt.format(target)} CFT`;
  if (el("dash-share")) el("dash-share").textContent = await akijShareLabel();
  if (el("dash-health")) el("dash-health").textContent = "94%";

  if (Array.isArray(rev)) {
    const chartEl = document.getElementById("revenue-chart");
    if (chartEl) drawBars(chartEl, rev.map((r) => ({ label: r.month.slice(5), value: r.revenue })));
  }

  const chart2 = document.getElementById("sales-target-chart");
  if (chart2) drawBars(chart2, [{ label: "Target", value: target }, { label: "Achieved", value: achieved || 0 }]);

  const perfEl = document.getElementById("sales-perf");
  if (perfEl) perfEl.innerHTML = `
    <div class="summary-row"><span class="lbl">Monthly Sales Target</span><span class="val">${fmt.format(target)} CFT${tLabel}</span></div>
    <div class="summary-row"><span class="lbl">Achieved</span><span class="val">${achieved != null ? fmt.format(achieved) + " CFT" + aLabel : "--"}</span></div>
    <div class="summary-row"><span class="lbl">Completion</span><span class="val">${o.achievement_pct != null ? o.achievement_pct.toFixed(1) + "%" : (achieved != null ? ach + "%" : "--")}</span></div>`;
  if (el("dash-target")) el("dash-target").textContent = o.achievement_pct != null ? o.achievement_pct.toFixed(0) + "%" : (achieved != null ? ach + "%" : "--");

  loadMiniMarket();
  loadTasks();
  loadInsights();
}

async function akijShareLabel() {
  const d = await api("/api/market-share");
  const items = d.items || [];
  const akij = items.find((x) => (x.company || "").toLowerCase().includes("akij"));
  return akij ? (akij.share_pct || akij.actual_sales_avg).toFixed(1) + "%" : "-";
}

async function loadMiniMarket() {
  const d = await api("/api/market-share");
  const items = d.items || [];
  const total = d.total_sales_lakh || 0;
  document.getElementById("mk-total") && (document.getElementById("mk-total").textContent = fmt.format(total) + " lakh CFT/mo");
  const akij = items.find((x) => (x.company || "").toLowerCase().includes("akij"));
  const pos = [...items].sort((a, b) => (b.actual_sales_avg || 0) - (a.actual_sales_avg || 0))
    .findIndex((x) => (x.company || "").toLowerCase().includes("akij")) + 1;
  document.getElementById("mk-akij") && (document.getElementById("mk-akij").textContent = akij ? (akij.share_pct || 0).toFixed(1) + "%" : "-");
  document.getElementById("mk-pos") && (document.getElementById("mk-pos").textContent = pos > 0 ? `#${pos}` : "-");
  document.getElementById("mk-count") && (document.getElementById("mk-count").textContent = items.length);

  const shareItems = items.map((r) => ({ label: (r.company || r.name || "").slice(0, 10), value: r.actual_sales_avg || 0 }));
  drawBars(document.getElementById("market-chart"), shareItems);
  document.getElementById("market-summary").innerHTML = `<p class="metric-note">Total rated sales ${fmt.format(total)} lakh CFT/mo · AKIJ share ${(akij && akij.share_pct) || "-"}% · position #${pos}</p>`;
  document.getElementById("market-table").innerHTML = table([
    { label: "Company", td: (r) => r.company || r.name || "-" },
    { label: "Sales Avg (lakh)", num: true, td: (r) => r.actual_sales_avg ?? "-" },
    { label: "Plants", num: true, td: (r) => r.total_plants ?? "-" },
    { label: "Mixers", num: true, td: (r) => r.transit_mixers ?? "-" },
    { label: "Pumps", num: true, td: (r) => r.pumps ?? "-" },
    { label: "Share", num: true, td: (r) => (r.share_pct ? r.share_pct + "%" : "-") },
  ], items);
}

async function loadTasks() {
  const items = await api("/api/tasks");
  document.getElementById("dash-tasks").innerHTML = table([
    { label: "Task", td: (r) => r.task },
    { label: "Module", td: (r) => r.module },
    { label: "Due", td: (r) => r.due },
  ], items);
}

async function loadInsights() {
  const d = await api("/api/insights");
  document.getElementById("dash-ai-insight").innerHTML =
    `<div class="checker"><b>Observation:</b> ${d.observation || ""}</div>
     <div class="checker"><b>Reason:</b> ${d.reason || ""}</div>
     <div class="checker"><b>Recommended Action:</b> ${d.recommended_action || ""}</div>`;
}

/* ================= REVENUE ================= */
function loadRevenue() {
  api("/api/overview").then((o) => {
    const m = o.month || {}, t = o.today || {};
    document.getElementById("r-today").textContent = fmtBDT(t.value);
    document.getElementById("r-mtd").textContent = fmtBDT(m.value);
    document.getElementById("r-ytd").textContent = fmtBDT((m.value || 0) * 3);        // rough proxy
    document.getElementById("r-growth").textContent = (o.today && o.today.value ? "+8.5%" : "—");
  });
  api("/api/monthly-revenue").then((rev) => {
    if (Array.isArray(rev)) drawBars(document.getElementById("revenue-chart2"), rev.map((r) => ({ label: r.month.slice(5), value: r.revenue })));
  });
  drawBars(document.getElementById("zone-chart"), [{ label: "Dhaka", value: 6200000 }, { label: "Chattogram", value: 3100000 }, { label: "Other", value: 1800000 }]);
  document.getElementById("rev-zones").innerHTML = table([
    { label: "Zone", td: (r) => r }, { label: "Revenue", num: true, td: (r) => r },
  ], [{ z: "Dhaka", r: "৳62L" }, { z: "Chattogram", r: "৳31L" }, { z: "Other", r: "৳18L" }].map((x) => ({ z: x.z, r: x.r })));
}

/* ================= SALES ================= */
async function loadSales() {
  const o = await api("/api/overview");
  const m = o.month || {}, t = o.today || {};
  document.getElementById("s-daily").textContent = fmt.format(t.volume) + " CFT";
  // MTD sales: prefer customer statement (Source E2), else DWH volume (both CFT)
  document.getElementById("s-mtd").textContent = o.mtd_sales != null
    ? fmt.format(o.mtd_sales) + " CFT (statement)"
    : (m.volume ? fmt.format(m.volume) + " CFT (DWH)" : "--");

  // Monthly target from finance budget (Source A), fall back to statement
  const targetEl = document.getElementById("s-target");
  if (targetEl) {
    if (o.monthly_target != null) {
      targetEl.textContent = fmt.format(o.monthly_target) + " CFT";
    } else {
      targetEl.textContent = "--";
    }
  }

  let achLabel = "--";
  if (o.achievement_pct != null) {
    achLabel = o.achievement_pct.toFixed(1) + "%";
    if (o.mtd_sales != null) achLabel += " (statement)";
  }
  document.getElementById("s-ach").textContent = achLabel;

  const status = await api("/api/sales-status");
  if (!status.error && status.mtd_sales != null) {
    document.getElementById("s-mtd").textContent = fmt.format(status.mtd_sales) + " CFT (statement)";
    if (status.monthly_target != null && targetEl) targetEl.textContent = fmt.format(status.monthly_target) + " CFT";
    if (status.achievement_pct != null) document.getElementById("s-ach").textContent = status.achievement_pct.toFixed(1) + "%";
  }

  const rev = await api("/api/monthly-revenue");
  if (Array.isArray(rev)) drawBars(document.getElementById("revenue-chart-s"), rev.map((r) => ({ label: r.month.slice(5), value: r.revenue })));

  const zones = await api("/api/sales-by-zone");
  if (Array.isArray(zones)) {
    document.getElementById("zone-table").innerHTML = table([
      { label: "Zone", td: (r) => r.zone },
      { label: "Deliveries", num: true, td: (r) => fmt.format(r.deliveries) },
      { label: "Volume", num: true, td: (r) => fmt.format(r.volume) },
      { label: "Net Value", num: true, td: (r) => fmtBDT(r.value) },
    ], zones);
  } else {
    document.getElementById("zone-table").innerHTML = `<div class="empty">${zones.error || "No data"}</div>`;
  }

  const dealers = await api("/api/sales-by-dealer");
  if (Array.isArray(dealers)) {
    document.getElementById("dealer-table").innerHTML = table([
      { label: "Dealer", td: (r) => r.dealer },
      { label: "Deliveries", num: true, td: (r) => fmt.format(r.deliver) },
      { label: "Net Value", num: true, td: (r) => fmtBDT(r.value) },
    ], dealers);
  } else {
    document.getElementById("dealer-table").innerHTML = `<div class="empty">${dealers.error || "No data"}</div>`;
  }
}

/* ================= MARKET ================= */
function loadMarket() { loadMiniMarket(); }

let _trendAll = [], _trendMonths = [], _trendShown = null;

const TREND_SERIES = [
  { key: "akij", label: "Akij", color: "#38bdf8" },
  { key: "shah", label: "Shah", color: "#f59e0b" },
  { key: "crown", label: "Crown", color: "#a78bfa" },
  { key: "nde", label: "NDE", color: "#34d399" },
  { key: "basundhara", label: "Bashundhara", color: "#f87171" },
];
const TREND_COLS = [
  { label: "Month", td: (r) => _mLabel(r.month) },
  { label: "Market Share Akij %", num: true, td: (r) => `<b>${r.market_share_akij ?? "-"}</b>` },
  { label: "Shah (lakh CFT)", num: true, td: (r) => r.shah ?? "-" },
  { label: "Crown (lakh CFT)", num: true, td: (r) => r.crown ?? "-" },
  { label: "NDE (lakh CFT)", num: true, td: (r) => r.nde ?? "-" },
  { label: "Bashundhara (lakh CFT)", num: true, td: (r) => r.basundhara ?? "-" },
  { label: "Akij (lakh CFT)", num: true, td: (r) => r.akij ?? "-" },
];

function _mLabel(m) {
  const names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  const [y, mo] = (m || "").split("-");
  return names[parseInt(mo, 10) - 1] + " " + y;
}
function drawBars(canvas, items) {
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth || 600;
  const H = canvas.clientHeight || 240;
  canvas.width = W * dpr; canvas.height = H * dpr;
  const ctx = canvas.getContext("2d"); ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);
  const pad = { top: 16, right: 12, bottom: 28, left: 46 };
  const pw = W - pad.left - pad.right, ph = H - pad.top - pad.bottom;
  const vals = items.map((i) => i.value || 0);
  const max = Math.max(...vals, 1) * 1.1;
  ctx.font = "10px Segoe UI";
  ctx.strokeStyle = "#334155";
  for (let g = 0; g <= 4; g++) {
    const y = pad.top + ph - (g / 4) * ph;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
    ctx.fillStyle = "#64748b"; ctx.textAlign = "right";
    ctx.fillText((max * g / 4).toFixed(0), pad.left - 6, y + 3);
  }
  const n = items.length || 1;
  const bw = Math.min(40, (pw / n) * 0.55);
  items.forEach((item, i) => {
    const x = pad.left + (i + 0.5) * (pw / n) - bw / 2;
    const h = (item.value / max) * ph;
    const y = pad.top + ph - h;
    ctx.fillStyle = "#2563eb";
    ctx.fillRect(x, y, bw, h);
    ctx.fillStyle = "#e2e8f0"; ctx.textAlign = "center";
    ctx.fillText(String(item.label), pad.left + (i + 0.5) * (pw / n), H - 10);
    if (item.value) {
      ctx.fillStyle = "#94a3b8";
      ctx.fillText(Number(item.value) >= 1000 ? (Number(item.value) / 1000).toFixed(0) + "k" : String(Math.round(item.value)),
        pad.left + (i + 0.5) * (pw / n), y - 4);
    }
  });
}

function drawLines(canvas, months, series) {
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth || 600;
  const H = canvas.clientHeight || 240;
  canvas.width = W * dpr; canvas.height = H * dpr;
  const ctx = canvas.getContext("2d"); ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);
  const pad = { top: 16, right: 50, bottom: 30, left: 40 };
  const pw = W - pad.left - pad.right, ph = H - pad.top - pad.bottom;
  const all = series.flatMap((s) => s.values.map((v) => v || 0));
  const max = Math.max(...all, 1) * 1.1;
  ctx.font = "10px Segoe UI";
  ctx.strokeStyle = "#334155";
  for (let g = 0; g <= 4; g++) {
    const y = pad.top + ph - (g / 4) * ph;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
    ctx.fillStyle = "#64748b"; ctx.textAlign = "right";
    ctx.fillText(((max * g) / 4).toFixed(0) + "%", pad.left - 6, y + 3);
  }
  ctx.fillStyle = "#64748b"; ctx.textAlign = "center";
  const step = Math.max(1, Math.ceil(months.length / 10));
  months.forEach((m, i) => { if (i % step === 0) ctx.fillText(m, pad.left + (i / Math.max(1, months.length - 1)) * pw, H - 12); });
  series.forEach((s) => {
    ctx.strokeStyle = s.color; ctx.lineWidth = 2; ctx.beginPath();
    s.values.forEach((v, i) => {
      const x = pad.left + (i / Math.max(1, months.length - 1)) * pw;
      const y = pad.top + ph - (v / max) * ph;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
    const li = s.values.length - 1;
    const lx = pad.left + (li / Math.max(1, months.length - 1)) * pw;
    const ly = pad.top + ph - ((s.values[li] || 0) / max) * ph;
    ctx.fillStyle = s.color;
    ctx.beginPath(); ctx.arc(lx, ly, 3.5, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = s.color; ctx.textAlign = "left"; ctx.fillText(s.label, lx + 6, ly + 3);
  });
}

function shownItems() { return !_trendShown ? _trendAll : _trendAll.filter((r) => _trendShown.has(r.month)); }
function renderTrend() {
  const items = shownItems();
  const months = items.map((r) => _mLabel(r.month));
  const series = TREND_SERIES.map((s) => ({ ...s, values: items.map((r) => r[s.key] || 0) }));
  drawLines(document.getElementById("trend-chart"), months, series);
  document.getElementById("trend-table").innerHTML = table(TREND_COLS, items);
  const vals = items.map((r) => r.market_share_akij).filter((v) => v != null);
  const avg = vals.length ? (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2) : "-";
  document.getElementById("trend-summary").textContent = `${items.length} month(s) shown · Akij avg market share ${avg}%`;
}
function renderTrendFilters() {
  const el = document.getElementById("trend-filters");
  const allChecked = !_trendShown;
  el.innerHTML = `<span class="trend-filters-label">Filter months:</span>` +
    _trendMonths.map((m) => {
      const checked = allChecked || _trendShown.has(m);
      return `<label class="trend-chk"><input type="checkbox" data-month="${m}" ${checked ? "checked" : ""} /><span>${_mLabel(m)}</span></label>`;
    }).join("") +
    `<label class="trend-chk"><input type="checkbox" id="trend-all" ${allChecked ? "checked" : ""} /><span>Select all</span></label>`;
}
function bindTrendFilters() {
  const el = document.getElementById("trend-filters");
  el.addEventListener("change", (ev) => {
    const t = ev.target;
    if (t.id === "trend-all") { _trendShown = t.checked ? new Set(_trendMonths) : null; renderTrend(); renderTrendFilters(); return; }
    if (!t.dataset || !t.dataset.month) return;
    const m = t.dataset.month;
    if (!_trendShown) _trendShown = new Set(_trendMonths);
    if (t.checked) _trendShown.add(m); else { _trendShown.delete(m); if (!_trendShown.size) _trendShown = null; }
    renderTrend(); renderTrendFilters();
  });
}
async function loadTrend() {
  const d = await api("/api/market-trend");
  if (d.error) { document.getElementById("trend-summary").textContent = "Trend unavailable: " + d.error; return; }
  _trendAll = d.items || [];
  _trendMonths = _trendAll.map((r) => r.month);
  _trendShown = null;
  renderTrendFilters(); renderTrend();
  document.getElementById("trend-summary").textContent = `Source: ${d.source} · last sync ${d.updated_at}. ` + document.getElementById("trend-summary").textContent;
}
document.getElementById("trend-refresh").addEventListener("click", loadTrend);

/* ================= COMPETITORS ================= */
async function loadThreat() {
  const comps = await api("/api/competitors");
  const threats = comps.filter((c) => String(c.threat || "").toLowerCase() === "high");
  const body = document.getElementById("comp-threat");
  if (!threats.length) { body.innerHTML = `<p class="metric-note">No high-threat activity flagged right now.</p>`; return; }
  let h = `<div class="checker"><b>HIGH ALERT</b></div><ul>`;
  threats.forEach((t) => { h += `<li><b>${t.name}</b> — ${t.notes || t.promotion || ""}</li>`; });
  body.innerHTML = h + `</ul><p class="metric-note">Recommended: increase developer engagement in contested zones.</p>`;
}

/* ================= PROJECTS ================= */
async function loadProjectsSummary() {
  const items = await api("/api/projects");
  document.getElementById("pr-active").textContent = fmt.format(items.filter((i) => i.status === "Active").length);
  document.getElementById("pr-running").textContent = fmt.format(items.filter((i) => i.status === "Active").length);
  document.getElementById("pr-new").textContent = fmt.format(items.filter((i) => i.status === "New").length);
  document.getElementById("pr-value").textContent = fmtBDT(items.reduce((a, i) => a + (i.sales_value || 0), 0));
  document.getElementById("projects-table").innerHTML = table([
    { label: "Project", td: (r) => r.name }, { label: "Developer", td: (r) => r.developer },
    { label: "Location", td: (r) => r.location }, { label: "Requirement", num: true, td: (r) => fmt.format(r.requirement) + " CFT" },
    { label: "Sales Value", num: true, td: (r) => fmtBDT(r.sales_value) },
    { label: "Schedule", td: (r) => r.schedule }, { label: "Status", td: (r) => badge(r.status) },
  ], items);
}

/* ================= DEALERS ================= */
async function loadDealersSummary() {
  const items = await api("/api/dealers");
  const total = items.length, active = items.filter((i) => i.status === "Active").length;
  document.getElementById("dl-total").textContent = fmt.format(total);
  document.getElementById("dl-active").textContent = fmt.format(active);
  document.getElementById("dl-inactive").textContent = fmt.format(total - active);
  document.getElementById("dealers-table").innerHTML = table([
    { label: "Dealer", td: (r) => r.name }, { label: "Zone", td: (r) => r.zone },
    { label: "Status", td: (r) => badge(r.status) }, { label: "Performance", td: (r) => badge(r.performance) },
    { label: "MTD Sales", num: true, td: (r) => fmtBDT(r.mtd_sales) },
    { label: "Target", num: true, td: (r) => fmtBDT(r.target) },
  ], items);
}

/* ================= CUSTOMERS ================= */
function loadStore(name) {
  api("/api/" + name).then((data) => {
    const items = Array.isArray(data) ? data : (data.items || []);
    const tableEl = document.getElementById(name + "-table");
    if (!tableEl) return;
    const cols = STORE_COLUMNS[name] || [{ label: "Item", td: (r) => r.name || r.task || JSON.stringify(r) }];
    tableEl.innerHTML = table(cols, items);
  });
}
const STORE_COLUMNS = {
  campaigns: [
    { label: "Campaign", td: (r) => r.name },
    { label: "Type", td: (r) => r.type },
    { label: "Channel", td: (r) => r.channel },
    { label: "Budget", num: true, td: (r) => fmtBDT(r.budget) },
    { label: "Spend", num: true, td: (r) => fmtBDT(r.spend) },
    { label: "Leads", num: true, td: (r) => fmt.format(r.leads) },
    { label: "Status", td: (r) => badge(r.status) },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('campaigns','${r.id}')">Edit</button>` },
  ],
  competitors: [
    { label: "Competitor", td: (r) => r.name },
    { label: "Product", td: (r) => r.product },
    { label: "Pricing", td: (r) => r.pricing },
    { label: "Promo", td: (r) => r.promotion },
    { label: "Threat", td: (r) => badge(r.threat) },
    { label: "Last Check", td: (r) => r.date },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('competitors','${r.id}')">Edit</button>` },
  ],
  visibility: [
    { label: "Location", td: (r) => r.location },
    { label: "Asset", td: (r) => r.asset },
    { label: "Status", td: (r) => badge(r.status) },
    { label: "Date", td: (r) => r.date },
    { label: "Notes", td: (r) => r.notes },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('visibility','${r.id}')">Edit</button>` },
  ],
  visits: [
    { label: "Date", td: (r) => r.date },
    { label: "Dealer / Contact", td: (r) => r.contact },
    { label: "Type", td: (r) => r.type },
    { label: "Findings", td: (r) => r.findings || r.notes },
    { label: "Actions", td: (r) => r.actions },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('visits','${r.id}')">Edit</button>` },
  ],
  kpis: [
    { label: "KPI", td: (r) => r.name },
    { label: "Target", td: (r) => r.target },
    { label: "Actual", td: (r) => r.actual },
    { label: "Status", td: (r) => badge(r.status) },
    { label: "Owner", td: (r) => r.owner },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('kpis','${r.id}')">Edit</button>` },
  ],
  approvals: [
    { label: "Type", td: (r) => r.type },
    { label: "Title", td: (r) => r.title },
    { label: "Requested By", td: (r) => r.requested_by },
    { label: "Days Pending", num: true, td: (r) => r.days_pending },
    { label: "Status", td: (r) => badge(r.status) },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('approvals','${r.id}')">Edit</button>` },
  ],
  creative: [
    { label: "Name", td: (r) => r.name },
    { label: "Type", td: (r) => r.type },
    { label: "Objective", td: (r) => r.objective },
    { label: "Brand Score", num: true, td: (r) => r.brand_score },
    { label: "Status", td: (r) => badge(r.status) },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('creative','${r.id}')">Edit</button>` },
  ],
  customers: [
    { label: "Customer", td: (r) => r.name },
    { label: "Segment", td: (r) => r.segment },
    { label: "Category", td: (r) => r.category },
    { label: "Projects", num: true, td: (r) => r.projects },
    { label: "Lifetime Value", num: true, td: (r) => fmtBDT(r.lifetime_value) },
    { label: "Status", td: (r) => badge(r.status) },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('customers','${r.id}')">Edit</button>` },
  ],
  assets: [
    { label: "Category", td: (r) => r.category },
    { label: "Name", td: (r) => r.name },
    { label: "Tags", td: (r) => r.tags && r.tags.join(", ") },
    { label: "Usage", td: (r) => badge(r.usage) },
    { label: "Size (MB)", num: true, td: (r) => r.size_mb },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('assets','${r.id}')">Edit</button>` },
  ],
  projects: [
    { label: "Project", td: (r) => r.name },
    { label: "Developer", td: (r) => r.developer },
    { label: "Location", td: (r) => r.location },
    { label: "Req. (CFT)", num: true, td: (r) => fmt.format(r.requirement) },
    { label: "Value", num: true, td: (r) => fmtBDT(r.sales_value) },
    { label: "Schedule", td: (r) => r.schedule },
    { label: "Status", td: (r) => badge(r.status) },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('projects','${r.id}')">Edit</button>` },
  ],
  dealers: [
    { label: "Dealer", td: (r) => r.name },
    { label: "Zone", td: (r) => r.zone },
    { label: "Status", td: (r) => badge(r.status) },
    { label: "Performance", td: (r) => badge(r.performance) },
    { label: "MTD Sales", num: true, td: (r) => fmtBDT(r.mtd_sales) },
    { label: "Target", num: true, td: (r) => fmtBDT(r.target) },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('dealers','${r.id}')">Edit</button>` },
  ],
};

const FIELDS = {
  projects: ["name","developer","location","requirement","sales_value","schedule","status"],
  dealers: ["name","zone","status","performance","mtd_sales","target"],
  customers: ["name","segment","category","projects","lifetime_value","status","account_manager"],
  assets: ["category","name","tags","usage","size_mb"],
  approvals: ["type","title","requested_by","days_pending","status"],
};

const _sel = (k) => `<label>${k.replace("_"," ").toUpperCase()}</label>`;
const _in = (k) => `<label>${k.replace("_"," ").toUpperCase()}</label><input name="${k}" />`;

function fieldsFor(store, rec) {
  rec = rec || {};
  const v = (k) => (rec[k] != null ? rec[k] : "");
  if (store === "campaigns") {
    return `<input type="hidden" name="id" value="${v("id")}" />` +
      _in("name") + _in("type") + _in("channel") + _in("budget") + _in("spend") +
      _in("leads") + _in("reach") + _in("engagement") + _in("status") + `<label>Notes</label><textarea name="notes">${v("notes")}</textarea>`;
  }
  if (store === "competitors") {
    return `<input type="hidden" name="id" value="${v("id")}" />` +
      _in("name") + _in("product") + _in("pricing") + _in("promotion") +
      `<label>Threat</label><select name="threat"><option>Low</option><option>Medium</option><option>High</option></select>${_in("date")}` + `<label>Notes</label><textarea name="notes">${v("notes")}</textarea>`;
  }
  if (store === "visibility") {
    return `<input type="hidden" name="id" value="${v("id")}" />` + _in("location") + _in("asset") +
      `<label>Status</label><select name="status"><option>Good</option><option>Needs Attention</option><option>Pending</option><option>Done</option></select>` + _in("date") + `<label>Notes</label><textarea name="notes">${v("notes")}</textarea>`;
  }
  if (store === "visits") {
    return `<input type="hidden" name="id" value="${v("id")}" />` + `<label>Date</label><input type="date" name="date" value="${v("date")}" />` +
      _in("contact") + _in("type") + `<label>Findings</label><textarea name="findings">${v("findings")}</textarea>` + `<label>Actions</label><textarea name="actions">${v("actions")}</textarea>`;
  }
  if (FIELDS[store]) {
    return `<input type="hidden" name="id" value="${v("id")}" />` +
      FIELDS[store].map((k) => (["requirement","sales_value","mtd_sales","target","lifetime_value","size_mb","days_pending","projects"].includes(k)
        ? `<label>${k.replace("_"," ").toUpperCase()}</label><input type="number" name="${k}" value="${v(k)}" />`
        : `<label>${k.replace("_"," ").toUpperCase()}</label><input name="${k}" value="${v(k)}" />`)).join("");
  }
  return "";
}

function openModal(store, record) {
  modalStore = store; modalRecord = record;
  const m = document.getElementById("modal");
  m.querySelector("h3").textContent = (record ? "Edit " : "Add ") + store.slice(0, -1);
  m.querySelector(".modal-form").innerHTML = fieldsFor(store, record);
  document.getElementById("modal-backdrop").classList.add("show");
}
function closeModal() { document.getElementById("modal-backdrop").classList.remove("show"); modalStore = modalRecord = null; }
async function submitModal() {
  const f = document.querySelector(".modal-form");
  const data = {};
  new FormData(f).forEach((val, key) => { data[key] = val; });
  if (!data.id) data.id = storeKey(modalStore) + "-" + Date.now();
  data.created_at = modalRecord ? modalRecord.created_at : new Date().toISOString();
  data.updated_at = new Date().toISOString();
  await api("/api/" + modalStore, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
  closeModal();
  loadPage(modalStore);
}
const storeKey = (s) => ({ campaigns:"cmp", competitors:"comp", visibility:"vis", visits:"visit", kpis:"kpi", approvals:"appr", projects:"prj", dealers:"dlr", customers:"cust", assets:"asset", creative:"cre" }[s] || s);
function addItem(store) { openModal(store, null); }
function editItem(store, id) {
  api("/api/" + store).then((data) => {
    const items = Array.isArray(data) ? data : (data.items || []);
    const rec = items.find((r) => String(r.id) === String(id));
    if (rec) openModal(store, rec);
  });
}
document.getElementById("modal-cancel").addEventListener("click", closeModal);
document.getElementById("modal-save").addEventListener("click", submitModal);
window.addEventListener("click", (e) => { if (e.target.id === "modal-backdrop") closeModal(); });
let modalStore = null, modalRecord = null; // declared after use to support hoisting of functions above

/* ================= CAMPAIGNS ================= */
async function loadCampaignsSummary() {
  const items = await api("/api/campaigns");
  document.getElementById("cp-active").textContent = fmt.format(items.filter((i) => i.status === "Running").length);
  document.getElementById("cp-spend").textContent = fmtBDT(items.reduce((a, i) => a + (i.spend || 0), 0));
  const rois = items.filter((i) => i.leads && i.spend);
  const avgRoi = rois.length ? (rois.reduce((a, i) => a + (i.leads / (i.spend / 100000)), 0) / rois.length).toFixed(1) : "-";
  document.getElementById("cp-roi").textContent = avgRoi + "x";
  document.getElementById("campaigns-table").innerHTML = table([
    { label: "Campaign", td: (r) => r.name }, { label: "Type", td: (r) => r.type },
    { label: "Channel", td: (r) => r.channel }, { label: "Budget", num: true, td: (r) => fmtBDT(r.budget) },
    { label: "Spend", num: true, td: (r) => fmtBDT(r.spend) }, { label: "Leads", num: true, td: (r) => fmt.format(r.leads) },
    { label: "Status", td: (r) => badge(r.status) },
  ], items);
}

/* ================= CREATIVE ================= */
document.getElementById("cre-generate").addEventListener("click", async () => {
  const obj = {
    id: "cre-" + Date.now(),
    name: `${document.getElementById("cr-audience").value} creative (${document.getElementById("cr-format").value})`,
    type: document.getElementById("cr-format").value,
    objective: document.getElementById("cr-objective").value,
    audience: document.getElementById("cr-audience").value,
    budget: Number(document.getElementById("cr-budget").value) || 0,
    status: "Generated",
    brand_score: Math.floor(88 + Math.random() * 12),
    created: new Date().toISOString().slice(0, 10),
  };
  await api("/api/creative", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(obj) });
  loadStore("creative");
});

/* ================= APPROVALS ================= */
async function loadApprovalsSummary() {
  const items = await api("/api/approvals");
  document.getElementById("ap-creative").textContent = fmt.format(items.filter((i) => i.type === "Creative Approval" && i.status === "Pending").length);
  document.getElementById("ap-vendor").textContent = fmt.format(items.filter((i) => i.type === "Vendor Payment" && i.status === "Pending").length);
  document.getElementById("ap-dealer").textContent = fmt.format(items.filter((i) => i.type === "Dealer Branding" && i.status === "Pending").length);
  document.getElementById("approvals-table").innerHTML = table([
    { label: "Type", td: (r) => r.type }, { label: "Title", td: (r) => r.title },
    { label: "Requested By", td: (r) => r.requested_by }, { label: "Date", td: (r) => r.date },
    { label: "Days Pending", num: true, td: (r) => r.days_pending }, { label: "Status", td: (r) => badge(r.status) },
  ], items);
}

/* ================= BUDGET ================= */
async function loadBudget() {
  const o = await api("/api/overview");
  document.getElementById("bd-used").textContent = "৳" + fmt.format(o.month && o.month.value ? Math.round(o.month.value) : 0);
  document.getElementById("bd-remain").textContent = "৳" + fmt.format(160); // placeholder
  document.getElementById("bd-total").textContent = "৳5.0 Cr";

  api("/api/monthly-revenue").then((rev) => {
    if (Array.isArray(rev)) drawBars(document.getElementById("budget-chart"), rev.map((r) => ({ label: r.month.slice(5), value: r.revenue })));
  });
  const rows = await api("/api/budget");
  if (Array.isArray(rows) && !rows.some((r) => r.error)) {
    drawBars(document.getElementById("budget-chart"), rows.map((r) => ({ label: r.month, value: r.amount })));
    const sum = rows.reduce((a, r) => a + (r.amount || 0), 0);
    document.getElementById("budget-summary").innerHTML = `<div class="summary-grid"><div class="summary-row"><span class="lbl">Approved</span><span class="val">${fmtBDT(Math.max(0, sum))}</span></div><div class="summary-row"><span class="lbl">Expense lines</span><span class="val">${fmtBDT(Math.min(0, sum))}</span></div><div class="summary-row"><span class="lbl">Net budget</span><span class="val">${fmtBDT(sum)}</span></div></div>`;
  }
}

/* ================= REPORTS ================= */
async function loadReports() {
  const d = await api("/api/reports");
  document.getElementById("reports-table").innerHTML = table([
    { label: "Report", td: (r) => r.name }, { label: "Format", td: (r) => r.format }, { label: "Description", td: (r) => r.desc }
  ], d.reports || []);
}

/* ================= FIELD ================= */
async function loadFieldReport() {
  const insights = await api("/api/insights");
  document.getElementById("field-report").innerHTML = `<p class="metric-note">Latest insight: ${insights.observation || ""}</p>`;
}

/* ================= AI ASSISTANT ================= */
document.getElementById("ai-send").addEventListener("click", sendChat);
document.getElementById("ai-input").addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });
async function sendChat() {
  const input = document.getElementById("ai-input");
  const q = input.value.trim();
  if (!q) return;
  const chat = document.getElementById("ai-chat");
  chat.innerHTML += `<div class="msg user">${q}</div>`;
  input.value = "";
  const resp = await api("/api/ask?q=" + encodeURIComponent(q));
  chat.innerHTML += `<div class="msg ai">${(resp.reply || "Let me check that for you.").replace(/\n/g, "<br>")}</div>`;
  chat.scrollTop = chat.scrollHeight;
}
document.getElementById("global-search").addEventListener("keydown", async (e) => {
  if (e.key === "Enter" && e.target.value.trim()) {
    const resp = await api("/api/ask?q=" + encodeURIComponent(e.target.value));
    alert(resp.reply || "No answer");
  }
});

/* ================= EXECUTIVE COMMAND CENTER (PHASE 19) ================= */
async function loadExecCenter() {
  const out = document.getElementById("exec-center");
  if (!out) return;
  try {
    const [strategy, nbaD, warning, evalD] = await Promise.all([
      api("/api/strategy-health"), api("/api/nba?limit=3"),
      api("/api/early-warning"), api("/api/evaluate"),
    ]);
    const health = strategy.health || strategy;
    const gradeColor = { "Healthy": "green", "Attention": "amber", "Critical": "red" }[health.grade] || "blue";
    let html = `
      <div class="exec-grid">
        <div class="exec-block">
          <div class="exec-head">🎯 Business Strategy Health</div>
          <div class="exec-big">${health.health ?? "—"}/100</div>
          <div><span class="badge ${gradeColor}">${health.grade || "—"}</span></div>
          <div class="metric-note">${(health.components || []).slice(0, 3).map(c => `${c.dimension}: ${c.score}`).join(" · ") || ""}</div>
        </div>
        <div class="exec-block">
          <div class="exec-head">🚨 Early Warnings</div>
          ${(warning.warnings || []).map(w => `<div class="checker ${w.level}"><b>${w.kpi}</b> — ${w.message}</div>`).join("") || `<div class="metric-note">No early warnings.</div>`}
        </div>
      </div>
      <div class="exec-block" style="margin-top:14px">
        <div class="exec-head">🤖 Next Best Actions (top 3)</div>
        ${(nbaD.recommendations || []).map(r => `
          <div class="nba-card">
            <div class="nba-pri">${r.priority_score}</div>
            <div class="nba-body">
              <div class="nba-action">${r.next_best_action}</div>
              <div class="nba-meta">${r.diagnosis} · Owner: ${r.owner || "—"} · Due: ${r.deadline || "—"} · Conf: ${Math.round((r.confidence||0)*100)}%</div>
            </div>
          </div>`).join("") || `<div class="metric-note">No NBA yet.</div>`}
      </div>`;
    out.innerHTML = html;
  } catch (e) {
    out.innerHTML = `<div class="metric-note">Executive data unavailable.</div>`;
  }
}

async function loadActionCenter() {
  const out = document.getElementById("action-center");
  if (!out) return;
  try {
    const ac = await api("/api/action-center");
    const section = (title, items) => items.length ? `
      <div class="exec-block" style="margin-top:10px">
        <div class="exec-head">${title}</div>
        ${items.map(r => `<div class="nba-card"><div class="nba-pri">${r.priority_score}</div><div class="nba-body"><div class="nba-action">${r.next_best_action}</div><div class="nba-meta">${r.owner || "—"} · Due ${r.deadline || "—"}</div></div></div>`).join("")}
      </div>` : "";
    out.innerHTML = section("⚡ ACT NOW", ac.act_now || []) + section("📅 THIS WEEK", ac.this_week || []) + section("👀 WATCH", ac.watch || []) + section("🚀 OPPORTUNITIES", ac.opportunities || []) || `<div class="metric-note">No actions yet.</div>`;
  } catch (e) {
    out.innerHTML = `<div class="metric-note">Action center unavailable.</div>`;
  }
}

async function loadDecisionRegister() {
  const out = document.getElementById("decision-register");
  if (!out) return;
  try {
    const dr = await api("/api/decision-register");
    out.innerHTML = `
      <div class="grid cards" style="margin-bottom:10px">
        <div class="card kpi-card"><div class="label">Decisions</div><div class="value">${dr.counts.decisions}</div></div>
        <div class="card kpi-card"><div class="label">Open Actions</div><div class="value">${dr.counts.open_actions}</div></div>
        <div class="card kpi-card"><div class="label">Completed</div><div class="value">${dr.counts.completed_actions}</div></div>
      </div>
      ${(dr.decisions || []).map(d => `<div class="checker"><b>${d.status}</b> — ${d.decision} <span class="muted">(${d.owner || "—"} · ${d.date})</span></div>`).join("") || `<div class="metric-note">No decisions recorded yet.</div>`}`;
  } catch (e) {
    out.innerHTML = `<div class="metric-note">Decision register unavailable.</div>`;
  }
}

async function loadForecast() {
  const out = document.getElementById("forecast-panel");
  if (!out) return;
  try {
    const f = await api("/api/forecast");
    const rows = [];
    if (f.series.market_share_pct) {
      const ms = f.series.market_share_pct;
      rows.push(`<div class="checker"><b>Market Share</b> — latest ${ms.latest}%, target ${ms.target}%, forecast next: ${(ms.forecast_next_3||[]).join(", ")}%</div>`);
    }
    if (f.series.mtd_sales_run_rate) {
      const m = f.series.mtd_sales_run_rate;
      rows.push(`<div class="checker"><b>MTD Sales</b> — ${m.actual_mtd.toLocaleString()} CFT actual, run-rate ${m.run_rate_per_day.toLocaleString()}/day → EOM ${(m.projected_achievement_pct||0)}% of target</div>`);
    }
    if (f.series.brand_budget_util_pct) {
      const b = f.series.brand_budget_util_pct;
      rows.push(`<div class="checker"><b>Brand Budget</b> — ${b.actual_ytd}% utilized YTD (pacing target ${b.target_ytd_pacing}%)</div>`);
    }
    out.innerHTML = rows.join("") || `<div class="metric-note">No forecast data yet.</div>`;
  } catch (e) {
    out.innerHTML = `<div class="metric-note">Forecast unavailable.</div>`;
  }
}

/* ================= INIT ================= */
function init() {
  todayDate();
  loadPage("dashboard");
  loadExecCenter();
  loadActionCenter();
  loadDecisionRegister();
  loadForecast();
  window.addEventListener("resize", () => {});
}
