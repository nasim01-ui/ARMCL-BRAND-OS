/* Brand Custodian Dashboard - frontend logic */

const fmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const fmtBDT = (n) => "৳" + fmt.format(n);

async function api(path, opts) {
  const res = await fetch(path, opts);
  return res.json();
}

/* ---------------- tabs ---------------- */
document.querySelectorAll(".tab").forEach((t) => {
  t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    document.querySelectorAll(".pane").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    document.getElementById("pane-" + t.dataset.tab).classList.add("active");
  });
});

/* ---------------- charts (pure canvas bars) ---------------- */
function drawBars(canvas, items, color = "rgba(56,189,248,.85)") {
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth || 600;
  const H = canvas.clientHeight || 240;
  canvas.width = W * dpr; canvas.height = H * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);
  const pad = { top: 24, right: 16, bottom: 34, left: 60 };
  const max = Math.max(...items.map((i) => Math.abs(i.value || 0)), 1);
  const cw = (W - pad.left - pad.right) / items.length;
  const bh = H - pad.top - pad.bottom;

  ctx.font = "11px Segoe UI";
  ctx.fillStyle = "#94a3b8";
  items.forEach((it, idx) => {
    const x = pad.left + idx * cw;
    const val = it.value || 0;
    const h = (Math.abs(val) / max) * bh;
    const y = val < 0 ? pad.top + bh / 2 : pad.top + bh - h;
    const colorFill = val < 0 ? "rgba(248,113,113,.85)" : color;
    ctx.fillStyle = colorFill;
    ctx.fillRect(x + cw * 0.18, y, cw * 0.64, Math.max(h, val === 0 ? 2 : 1));
    ctx.fillStyle = "#cbd5e1";
    ctx.fillText(Math.abs(val) >= 1e6 ? (Math.abs(val) / 1e6).toFixed(1) + "M" : fmt.format(Math.abs(val)), x + cw * 0.18, y - 4);
    ctx.fillStyle = "#94a3b8";
    ctx.fillText(it.label, x + cw / 2, H - 14);
    ctx.textAlign = "center";
  });
  // axis
  ctx.strokeStyle = "#334155";
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, pad.top + bh);
  ctx.lineTo(W - pad.right, pad.top + bh);
  ctx.stroke();
  ctx.textAlign = "right";
}

/* ---------------- helpers ---------------- */
function table(cols, rows) {
  if (!rows.length) return '<div class="empty">No data yet.</div>';
  let html = "<table><thead><tr>" + cols.map((c) => `<th class="${c.num ? "num" : ""}">${c.label}</th>`).join("") + "</tr></thead><tbody>";
  for (const r of rows) {
    html += "<tr>" + cols.map((c) => `<td class="${c.num ? "num" : ""}">${c.td(r)}</td>`).join("") + "</tr>";
  }
  html += "</tbody></table>";
  return html;
}

function badge(status) {
  const map = {
    active: ["green", "Active"], running: ["green", "Running"],
    completed: ["blue", "Completed"], done: ["blue", "Done"],
    pending: ["amber", "Pending"], review: ["amber", "In Review"],
    paused: ["amber", "Paused"], low: ["red", "Low"], high: ["green", "High"],
  };
  const [c, l] = map[String(status || "").toLowerCase()] || ["blue", status || "-"];
  return `<span class="badge ${c}">${l}</span>`;
}

/* ---------------- overview ---------------- */
async function loadOverview() {
  const d = await api("/api/overview");
  const dateEl = document.getElementById("report-date");
  dateEl.textContent = "Report: " + (d.report_date || "--");

  const cards = document.getElementById("overview-cards");
  const card = (label, value, delta, up = true) => `
    <div class="card kpi-card">
      <div class="label">${label}</div>
      <div class="value">${value}</div>
      ${delta ? `<div class="delta ${up ? "up" : "down"}">${delta}</div>` : ""}
    </div>`;

  const t = d.today || {}, w = d.week || {}, m = d.month || {};
  cards.innerHTML =
    card("Deliveries Today", fmt.format(t.deliveries || 0)) +
    card("Volume Today (m³)", fmt.format(t.volume || 0)) +
    card("Net Value Today", fmtBDT(t.value || 0)) +
    card("This Week Net Value", fmtBDT(w.value || 0)) +
    card("Month-to-Date Value", fmtBDT(m.value || 0));

  const rev = await api("/api/monthly-revenue");
  if (Array.isArray(rev)) {
    drawBars(document.getElementById("revenue-chart"), rev.map((r) => ({ label: r.month.slice(5), value: r.revenue })));
  }
}

/* ---------------- sales ---------------- */
async function loadSales() {
  const zones = await api("/api/sales-by-zone");
  if (Array.isArray(zones)) {
    document.getElementById("zone-table").innerHTML = table(
      [
        { label: "Zone", td: (r) => r.zone },
        { label: "Deliveries", num: true, td: (r) => fmt.format(r.deliveries) },
        { label: "Volume", num: true, td: (r) => fmt.format(r.volume) },
        { label: "Net Value", num: true, td: (r) => fmtBDT(r.value) },
      ],
      zones
    );
  } else {
    document.getElementById("zone-table").innerHTML = `<div class="empty">${zones.error || "No data"}</div>`;
  }

  const dealers = await api("/api/sales-by-dealer");
  if (Array.isArray(dealers)) {
    document.getElementById("dealer-table").innerHTML = table(
      [
        { label: "Dealer", td: (r) => r.dealer },
        { label: "Deliveries", num: true, td: (r) => fmt.format(r.deliver) },
        { label: "Net Value", num: true, td: (r) => fmtBDT(r.value) },
      ],
      dealers
    );
  } else {
    document.getElementById("dealer-table").innerHTML = `<div class="empty">${dealers.error || "No data"}</div>`;
  }
}

/* ---------------- budget ---------------- */
async function loadBudget() {
  const rows = await api("/api/budget");
  if (!Array.isArray(rows) || rows.some((r) => r.error)) {
    document.getElementById("budget-chart").parentElement.innerHTML =
      `<div class="empty">Budget data unavailable: ${(rows[0] && rows[0].error) || "DB error"}</div>`;
    return;
  }
  const sum = rows.reduce((a, r) => a + (r.amount || 0), 0);
  drawBars(document.getElementById("budget-chart"), rows.map((r) => ({ label: r.month, value: r.amount })));
  const pos = rows.filter((r) => r.amount > 0).reduce((a, r) => a + r.amount, 0);
  const neg = rows.filter((r) => r.amount < 0).reduce((a, r) => a + r.amount, 0);
  document.getElementById("budget-summary").innerHTML = `
    <div class="summary-grid">
      <div class="summary-row"><span class="lbl">Approved (income)</span><span class="val">${fmtBDT(pos)}</span></div>
      <div class="summary-row"><span class="lbl">Expense lines</span><span class="val">${fmtBDT(neg)}</span></div>
      <div class="summary-row"><span class="lbl">Net budget</span><span class="val">${fmtBDT(sum)}</span></div>
    </div>
    <p class="metric-note">Source: bgt.tblBudgetIncomeExpenseRowArc · FY 2026-27 · ARMCL (unit 175).</p>`;
}

/* ---------------- editable stores ---------------- */
const STORE_COLUMNS = {
  campaigns: [
    { label: "Campaign", td: (r) => r.name || r.campaign || "-" },
    { label: "Type", td: (r) => r.type || "-" },
    { label: "Channel", td: (r) => r.channel || "-" },
    { label: "Budget", num: true, td: (r) => fmtBDT(r.budget || 0) },
    { label: "Spend", num: true, td: (r) => fmtBDT(r.spend || 0) },
    { label: "Leads", num: true, td: (r) => fmt.format(r.leads || 0) },
    { label: "Status", td: (r) => badge(r.status) },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('campaigns','${r.id}')">Edit</button>` },
  ],
  competitors: [
    { label: "Competitor", td: (r) => r.name || "-" },
    { label: "Product", td: (r) => r.product || "-" },
    { label: "Pricing", td: (r) => r.pricing || "-" },
    { label: "Promotion", td: (r) => r.promotion || "-" },
    { label: "Last Check", td: (r) => r.date || "-" },
    { label: "Notes", td: (r) => r.notes || "-" },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('competitors','${r.id}')">Edit</button>` },
  ],
  visibility: [
    { label: "Location", td: (r) => r.location || "-" },
    { label: "Asset", td: (r) => r.asset || "-" },
    { label: "Status", td: (r) => badge(r.status) },
    { label: "Date", td: (r) => r.date || "-" },
    { label: "Notes", td: (r) => r.notes || "-" },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('visibility','${r.id}')">Edit</button>` },
  ],
  visits: [
    { label: "Date", td: (r) => r.date || "-" },
    { label: "Dealer / Contact", td: (r) => r.contact || r.dealer || "-" },
    { label: "Type", td: (r) => r.type || "-" },
    { label: "Findings", td: (r) => r.findings || r.notes || "-" },
    { label: "Action Items", td: (r) => r.actions || "-" },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('visits','${r.id}')">Edit</button>` },
  ],
  kpis: [
    { label: "KPI", td: (r) => r.name || "-" },
    { label: "Target", td: (r) => r.target || "-" },
    { label: "Actual", td: (r) => r.actual || "-" },
    { label: "Status", td: (r) => badge(r.status) },
    { label: "Owner", td: (r) => r.owner || "-" },
    { label: "", td: (r) => `<button class="btn small" onclick="editItem('kpis','${r.id}')">Edit</button>` },
  ],
};

async function loadStore(name) {
  const data = await api("/api/" + name);
  const items = Array.isArray(data) ? data : (data.items || []);
  document.getElementById(name + "-table").innerHTML = table(STORE_COLUMNS[name], items);
}

function loadStores() {
  Object.keys(STORE_COLUMNS).forEach(loadStore);
}

/* ---------------- market share ---------------- */
const MARKET_COLUMNS = [
  { label: "Company", td: (r) => r.company || r.name || "-" },
  { label: "Plants", num: true, td: (r) => r.total_plants ?? "-" },
  { label: "Batching", num: true, td: (r) => r.batching_plants ?? "-" },
  { label: "Monthly Delivery (CFT)", num: true, td: (r) => r.avg_monthly_delivery_cft ?? "-" },
  { label: "Mixers", num: true, td: (r) => r.transit_mixers ?? "-" },
  { label: "Pumps", num: true, td: (r) => r.pumps ?? "-" },
  { label: "Coverage", td: (r) => r.coverage || "-" },
  { label: "Share", num: true, td: (r) => (r.share_pct ? r.share_pct + "%" : "-") },
];

async function loadMarket() {
  const d = await api("/api/market-share");
  const items = d.items || (Array.isArray(d) ? d : []);
  document.getElementById("market-table").innerHTML = table(MARKET_COLUMNS, items);
  document.getElementById("market-summary").innerHTML = `
    <p class="metric-note">Total actual sales of rated Ready-Mix players: ${fmt.format(d.total_sales_lakh || 0)} lakh CFT/month.
    ARMCL = ${(items.find((x) => (x.company || "").toLowerCase().includes("akij")) || {}).share_pct ?? "-"}% share.</p>`;
  drawBars(
    document.getElementById("market-chart"),
    items
      .filter((r) => r.share_pct)
      .sort((a, b) => b.actual_sales_avg - a.actual_sales_avg)
      .map((r) => ({ label: (r.company || r.name || "").slice(0, 10), value: r.actual_sales_avg }))
  );
}

/* ---------------- monthwise market-share trend (from Google Sheet) ---------------- */
const TREND_SERIES = [
  { key: "akij", label: "Akij", color: "#38bdf8" },
  { key: "shah", label: "Shah", color: "#f59e0b" },
  { key: "crown", label: "Crown", color: "#a78bfa" },
  { key: "nde", label: "NDE", color: "#34d399" },
  { key: "basundhara", label: "Bashundhara", color: "#f87171" },
];

function drawLines(canvas, months, series) {
  const dpr = window.devicePixelRatio || 1;
  const W = canvas.clientWidth || 600;
  const H = canvas.clientHeight || 240;
  canvas.width = W * dpr; canvas.height = H * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, W, H);
  const pad = { top: 16, right: 50, bottom: 30, left: 40 };
  const pw = W - pad.left - pad.right;
  const ph = H - pad.top - pad.bottom;
  const all = series.flatMap((s) => s.values.map((v) => v || 0));
  const max = Math.max(...all, 1) * 1.1;

  // grid + y labels
  ctx.font = "10px Segoe UI";
  ctx.fillStyle = "#64748b";
  ctx.strokeStyle = "#1e293b";
  for (let g = 0; g <= 4; g++) {
    const y = pad.top + ph - (g / 4) * ph;
    ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(W - pad.right, y); ctx.stroke();
    ctx.textAlign = "right";
    ctx.fillText(((max * g) / 4).toFixed(0) + "%", pad.left - 6, y + 3);
  }
  // x labels
  ctx.textAlign = "center";
  const step = Math.max(1, Math.ceil(months.length / 12));
  months.forEach((m, i) => {
    if (i % step === 0) {
      ctx.fillStyle = "#64748b";
      ctx.fillText(m, pad.left + (i / Math.max(1, months.length - 1)) * pw, H - 12);
    }
  });
  // series lines
  series.forEach((s) => {
    ctx.strokeStyle = s.color; ctx.lineWidth = 2;
    ctx.beginPath();
    s.values.forEach((v, i) => {
      const x = pad.left + (i / Math.max(1, months.length - 1)) * pw;
      const y = pad.top + ph - (v / max) * ph;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
    // last point dot + label
    const li = s.values.length - 1;
    const lx = pad.left + (li / Math.max(1, months.length - 1)) * pw;
    const ly = pad.top + ph - ((s.values[li] || 0) / max) * ph;
    ctx.fillStyle = s.color;
    ctx.beginPath(); ctx.arc(lx, ly, 3.5, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = s.color; ctx.textAlign = "left";
    ctx.fillText(s.label, lx + 6, ly + 3);
  });
}

let _trendAll = [];
let _trendMonths = [];
let _trendShown = null; // null = all shown, else Set of month keys to show

function trendLabel(r) {
  return _trendLabel(r.month);
}

function _trendLabel(m) {
  const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const [y, mo] = (m || "").split("-");
  return names[parseInt(mo, 10) - 1] + " " + y;
}

const TREND_COLS = [
  { label: "Month", td: (r) => trendLabel(r) },
  { label: "Market Share Akij %", num: true, td: (r) => `<b>${r.market_share_akij ?? "-"}</b>` },
  { label: "Shah (lakh CFT)", num: true, td: (r) => r.shah ?? "-" },
  { label: "Crown (lakh CFT)", num: true, td: (r) => r.crown ?? "-" },
  { label: "NDE (lakh CFT)", num: true, td: (r) => r.nde ?? "-" },
  { label: "Bashundhara (lakh CFT)", num: true, td: (r) => r.basundhara ?? "-" },
  { label: "Akij Sales (lakh CFT)", num: true, td: (r) => r.akij ?? "-" },
];

function shownItems() {
  if (!_trendShown) return _trendAll;
  return _trendAll.filter((r) => _trendShown.has(r.month));
}

function renderTrend() {
  const items = shownItems();
  const months = items.map((r) => trendLabel(r));
  const series = TREND_SERIES.map((s) => ({ ...s, values: items.map((r) => r[s.key] || 0) }));
  drawLines(document.getElementById("trend-chart"), months, series);
  document.getElementById("trend-table").innerHTML = table(TREND_COLS, items);
  const akijList = items.map((r) => r.market_share_akij).filter((v) => v != null);
  const avgAkij = akijList.length ? (akijList.reduce((a, b) => a + b, 0) / akijList.length).toFixed(2) : "-";
  const akijRows = items.filter((r) => r.akij != null);
  const avgAkijSales = akijRows.length
    ? (akijRows.reduce((a, r) => a + (r.akij || 0), 0) / akijRows.length).toFixed(2)
    : "-";
  document.getElementById("trend-summary").textContent =
    `${shownItems().length} month(s) shown · Akij avg market share ${avgAkij}% · avg monthly sales ${avgAkijSales} lakh CFT`;
}

function renderTrendFilters() {
  const el = document.getElementById("trend-filters");
  const allChecked = !_trendShown;
  el.innerHTML = `<span class="trend-filters-label">Filter months:</span>` +
    _trendMonths.map((m) => {
      const checked = allChecked || _trendShown.has(m);
      return `<label class="trend-chk"><input type="checkbox" data-month="${m}" ${checked ? "checked" : ""} /><span>${_trendLabel(m)}</span></label>`;
    }).join("") +
    `<label class="trend-chk"><input type="checkbox" id="trend-all" ${allChecked ? "checked" : ""} /><span>Select all</span></label>`;
}

function applyFilter() {
  const boxes = [...document.querySelectorAll("#trend-filters input[data-month]")];
  _trendShown = new Set(boxes.filter((b) => b.checked).map((b) => b.dataset.month));
  renderTrend();
  renderTrendFilters();
}

function bindTrendFilters() {
  const el = document.getElementById("trend-filters");
  el.addEventListener("change", (ev) => {
    const target = ev.target;
    if (target.id === "trend-all") {
      _trendShown = target.checked ? new Set(_trendMonths) : null;
      renderTrend();
      renderTrendFilters();
      return;
    }
    if (target.dataset && target.dataset.month) {
      const m = target.dataset.month;
      if (!_trendShown) _trendShown = new Set(_trendMonths);
      if (target.checked) _trendShown.add(m);
      else _trendShown.delete(m);
      renderTrend();
      renderTrendFilters();
    }
  });
}

async function loadTrend(refresh) {
  const d = await api(refresh ? "/api/market-trend?refresh=1" : "/api/market-trend");
  if (!d || d.error) {
    document.getElementById("trend-summary").textContent = "Could not load trend: " + (d && d.error);
    return;
  }
  _trendAll = d.items || [];
  _trendMonths = _trendAll.map((r) => r.month);
  _trendShown = null;
  renderTrendFilters();
  renderTrend();
  document.getElementById("trend-summary").textContent =
    `Source: ${d.source} (live Google Sheet) · last sync ${d.updated_at}. ` + document.getElementById("trend-summary").textContent;
}

/* ---------------- modal add/edit ---------------- */
let modalStore = null;
let modalRecord = null;

function openModal(store, record) {
  modalStore = store;
  modalRecord = record;
  const m = document.getElementById("modal");
  m.querySelector("h3").textContent = (record ? "Edit " : "Add ") + store.slice(0, -1);
  const f = m.querySelector(".modal-form");
  f.innerHTML = fieldsFor(store, record);
  document.getElementById("modal-backdrop").classList.add("show");
}

function closeModal() {
  document.getElementById("modal-backdrop").classList.remove("show");
  modalStore = modalRecord = null;
}

function fieldsFor(store, rec) {
  rec = rec || {};
  const v = (k) => (rec[k] != null ? rec[k] : "");
  const input = (k, label, type = "text") =>
    `<label>${label}</label><input type="${type}" name="${k}" value="${v(k)}" />`;
  const textarea = (k, label) => `<label>${label}</label><textarea name="${k}">${v(k)}</textarea>`;
  const sel = (k, label, opts) =>
    `<label>${label}</label><select name="${k}">${opts.map((o) => `<option ${String(v(k)).toLowerCase() === String(o).toLowerCase() ? "selected" : ""}>${o}</option>`).join("")}</select>`;

  const common = `<input type="hidden" name="id" value="${v("id")}" />`;
  switch (store) {
    case "campaigns":
      return common + input("name", "Campaign name") + sel("type", "Type", ["ATL", "BTL", "TTL", "Digital"])
        + sel("channel", "Channel", ["TV", "Radio", "Billboard", "Digital", "Social", "Print", "Events", "POSM"])
        + input("budget", "Budget (BDT)", "number") + input("spend", "Spend (BDT)", "number")
        + input("leads", "Leads", "number") + input("reach", "Reach", "number") + input("engagement", "Engagement", "number")
        + sel("status", "Status", ["Running", "Planned", "Paused", "Completed"]) + textarea("notes", "Notes");
    case "competitors":
      return common + input("name", "Competitor") + input("product", "Product") + input("pricing", "Pricing")
        + input("promotion", "Promotion") + input("date", "Last checked", "date")
        + sel("threat", "Threat level", ["Low", "Medium", "High"]) + textarea("notes", "Notes");
    case "visibility":
      return common + input("location", "Location") + input("asset", "Asset type")
        + sel("status", "Status", ["Good", "Needs Attention", "Pending", "Done"])
        + input("date", "Check date", "date") + textarea("notes", "Notes");
    case "visits":
      return common + input("date", "Visit date", "date") + input("contact", "Dealer / Contact")
        + sel("type", "Visit type", ["Dealer", "Contractor", "Engineer", "Site"])
        + textarea("findings", "Findings") + textarea("actions", "Action items");
    case "kpis":
      return common + input("name", "KPI name") + input("target", "Target") + input("actual", "Actual")
        + sel("status", "Status", ["On Track", "At Risk", "Behind", "Met"])
        + input("owner", "Owner") + textarea("notes", "Notes");
  }
}

function addItem(store) {
  openModal(store, null);
}
function editItem(store, id) {
  api("/api/" + store).then((data) => {
    const items = Array.isArray(data) ? data : (data.items || []);
    const rec = items.find((r) => String(r.id) === String(id));
    if (rec) openModal(store, rec);
  });
}

async function submitModal() {
  const f = document.querySelector(".modal-form");
  const data = {};
  new FormData(f).forEach((val, key) => { data[key] = val; });
  if (!data.id) data.id = "id-" + Date.now();
  await api("/api/" + modalStore, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
  closeModal();
  loadStores();
}

document.getElementById("modal-cancel").addEventListener("click", closeModal);
document.getElementById("modal-save").addEventListener("click", submitModal);
window.addEventListener("click", (e) => {
  if (e.target.id === "modal-backdrop") closeModal();
});

/* ---------------- init ---------------- */
function init() {
  loadOverview();
  loadSales();
  loadBudget();
  loadStores();
  loadMarket();
  loadTrend(false);
  bindTrendFilters();
  document.getElementById("trend-refresh").addEventListener("click", () => loadTrend(true));
  window.addEventListener("resize", () => {
    api("/api/monthly-revenue").then((rev) => {
      if (Array.isArray(rev)) drawBars(document.getElementById("revenue-chart"), rev.map((r) => ({ label: r.month.slice(5), value: r.revenue })));
    });
    api("/api/budget").then((rows) => {
      if (Array.isArray(rows) && !rows.some((r) => r.error)) drawBars(document.getElementById("budget-chart"), rows.map((r) => ({ label: r.month, value: r.amount })));
    });
  });
}

init();