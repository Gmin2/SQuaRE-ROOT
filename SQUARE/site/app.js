"use strict";

const SVGNS = "http://www.w3.org/2000/svg";
// css var() doesnt resolve inside svg presentation attributes, so keep hex here
const C = {
  grid: "#eef0f3",
  faint: "#94a3b8",
  borderStrong: "#d4d8df",
  accent: "#15803d",
};
const NUMERIC_KEYS = new Set([
  "feasibility_score", "code_distance_d", "logical_qubits",
  "physical_qubits", "wall_clock_days", "warnings_count",
]);

let rows = [];
let history = [];
let selected = null;          // scenario name shown in the chart
let sortKey = "feasibility_score";
let sortDir = -1;             // -1 desc, 1 asc

// ---------- data + formatting ----------

async function loadJSON(path) {
  const resp = await fetch(path, { cache: "no-store" });
  if (!resp.ok) throw new Error(`${path}: HTTP ${resp.status}`);
  return resp.json();
}

function fmtInt(n) {
  if (n === null || n === undefined) return "—";
  return Math.round(n).toLocaleString("en-US");
}

function fmtNum(n, digits) {
  if (n === null || n === undefined) return "—";
  if (n !== 0 && (Math.abs(n) < 1e-3 || Math.abs(n) >= 1e7)) return n.toExponential(2);
  return n.toLocaleString("en-US", { maximumFractionDigits: digits });
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function fmtDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function scoreClass(s) {
  if (s === null || s === undefined) return "";
  if (s >= 66) return "score-good";
  if (s >= 33) return "score-mid";
  return "score-bad";
}

function seriesFor(scenario) {
  return history
    .map((r) => ({ t: r.timestamp, v: r.scores ? r.scores[scenario] : null }))
    .filter((p) => typeof p.v === "number");
}

// ---------- hero cards ----------

function renderCards(board) {
  const lead = rows.reduce((best, r) =>
    (r.feasibility_score ?? -1) > (best?.feasibility_score ?? -1) ? r : best, null);

  document.getElementById("lead-score").textContent = lead?.feasibility_score ?? "—";
  document.getElementById("lead-name").textContent = lead?.scenario ?? "—";

  // leader delta vs the previous run
  const trendEl = document.getElementById("trend");
  const s = lead ? seriesFor(lead.scenario) : [];
  if (s.length >= 2) {
    const delta = s[s.length - 1].v - s[s.length - 2].v;
    const cls = delta > 0.05 ? "up" : delta < -0.05 ? "down" : "flat";
    const arrow = cls === "up" ? "↗" : cls === "down" ? "↘" : "→";
    trendEl.className = `trend ${cls}`;
    trendEl.textContent = `${arrow} ${delta >= 0 ? "+" : ""}${delta.toFixed(1)}`;
  } else {
    trendEl.textContent = "";
  }

  const modalities = new Set(rows.map((r) => r.modality).filter(Boolean));
  const problems = new Set(rows.map((r) => r.problem).filter(Boolean));
  document.getElementById("count").textContent = rows.length;
  document.getElementById("count-sub").textContent =
    `${modalities.size} ${modalities.size === 1 ? "modality" : "modalities"} · ${problems.size} target ${problems.size === 1 ? "problem" : "problems"}`;

  document.getElementById("updated").textContent = fmtDateTime(board.generated_at);
  document.getElementById("commit").textContent = board.commit ? `commit ${board.commit}` : "";
}

// ---------- chart ----------

function smoothPath(pts) {
  // catmull-rom to cubic bezier so the line stays smooth through every point
  if (pts.length < 2) return "";
  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i - 1] || pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[i + 2] || p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${c1x.toFixed(1)} ${c1y.toFixed(1)}, ${c2x.toFixed(1)} ${c2y.toFixed(1)}, ${p2.x.toFixed(1)} ${p2.y.toFixed(1)}`;
  }
  return d;
}

function el(name, attrs) {
  const node = document.createElementNS(SVGNS, name);
  for (const k in attrs) node.setAttribute(k, attrs[k]);
  return node;
}

function renderChart() {
  const svg = document.getElementById("chart");
  const empty = document.getElementById("chart-empty");
  const tooltip = document.getElementById("tooltip");
  svg.innerHTML = "";
  tooltip.hidden = true;

  const data = seriesFor(selected);
  if (data.length < 2) {
    empty.hidden = false;
    return;
  }
  empty.hidden = true;

  const rect = svg.getBoundingClientRect();
  const W = Math.max(320, rect.width);
  const H = Math.max(200, rect.height);
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  const m = { l: 44, r: 14, t: 16, b: 28 };
  const plotW = W - m.l - m.r;
  const plotH = H - m.t - m.b;

  const xAt = (i) => m.l + (data.length === 1 ? plotW / 2 : (i * plotW) / (data.length - 1));
  const yAt = (v) => m.t + plotH - (v / 100) * plotH;

  // gridlines + y labels, score axis is fixed 0..100
  for (const v of [0, 25, 50, 75, 100]) {
    const y = yAt(v);
    svg.appendChild(el("line", { x1: m.l, y1: y, x2: W - m.r, y2: y, stroke: C.grid, "stroke-width": 1 }));
    const t = el("text", { x: m.l - 8, y: y + 4, "text-anchor": "end", fill: C.faint, "font-size": 11 });
    t.textContent = v;
    svg.appendChild(t);
  }

  // x labels, up to ~5 evenly spaced dates
  const step = Math.max(1, Math.ceil(data.length / 5));
  for (let i = 0; i < data.length; i += step) {
    const t = el("text", { x: xAt(i), y: H - 8, "text-anchor": "middle", fill: C.faint, "font-size": 11 });
    t.textContent = fmtDate(data[i].t);
    svg.appendChild(t);
  }

  const pts = data.map((p, i) => ({ x: xAt(i), y: yAt(p.v) }));
  const linePath = smoothPath(pts);

  const areaPath = `${linePath} L ${pts[pts.length - 1].x} ${m.t + plotH} L ${pts[0].x} ${m.t + plotH} Z`;
  const grad = el("linearGradient", { id: "area-grad", x1: 0, y1: 0, x2: 0, y2: 1 });
  grad.appendChild(el("stop", { offset: "0%", "stop-color": C.accent, "stop-opacity": 0.18 }));
  grad.appendChild(el("stop", { offset: "100%", "stop-color": C.accent, "stop-opacity": 0 }));
  const defs = el("defs", {});
  defs.appendChild(grad);
  svg.appendChild(defs);
  svg.appendChild(el("path", { d: areaPath, fill: "url(#area-grad)", stroke: "none" }));
  svg.appendChild(el("path", { d: linePath, fill: "none", stroke: C.accent, "stroke-width": 2.5, "stroke-linejoin": "round", "stroke-linecap": "round" }));

  const last = pts[pts.length - 1];
  svg.appendChild(el("circle", { cx: last.x, cy: last.y, r: 4, fill: C.accent, stroke: "#fff", "stroke-width": 2 }));

  const guide = el("line", { y1: m.t, y2: m.t + plotH, stroke: C.borderStrong, "stroke-width": 1, "stroke-dasharray": "3 3", visibility: "hidden" });
  const hoverDot = el("circle", { r: 4.5, fill: C.accent, stroke: "#fff", "stroke-width": 2, visibility: "hidden" });
  svg.appendChild(guide);
  svg.appendChild(hoverDot);

  const overlay = el("rect", { x: m.l, y: m.t, width: plotW, height: plotH, fill: "transparent" });
  svg.appendChild(overlay);

  overlay.addEventListener("mousemove", (ev) => {
    const bb = svg.getBoundingClientRect();
    const px = ((ev.clientX - bb.left) / bb.width) * W;
    let i = Math.round(((px - m.l) / plotW) * (data.length - 1));
    i = Math.max(0, Math.min(data.length - 1, i));
    const p = pts[i];
    guide.setAttribute("x1", p.x);
    guide.setAttribute("x2", p.x);
    guide.setAttribute("visibility", "visible");
    hoverDot.setAttribute("cx", p.x);
    hoverDot.setAttribute("cy", p.y);
    hoverDot.setAttribute("visibility", "visible");
    tooltip.hidden = false;
    tooltip.style.left = `${(p.x / W) * 100}%`;
    tooltip.style.top = `${(p.y / H) * 100}%`;
    tooltip.innerHTML = `<span class="tt-label">${fmtDateTime(data[i].t)}</span><br><b>${data[i].v}</b> score`;
  });
  overlay.addEventListener("mouseleave", () => {
    guide.setAttribute("visibility", "hidden");
    hoverDot.setAttribute("visibility", "hidden");
    tooltip.hidden = true;
  });
}

function renderChips() {
  const group = document.getElementById("scenario-chips");
  group.innerHTML = "";
  for (const r of rows) {
    const chip = document.createElement("button");
    chip.className = "chip" + (r.scenario === selected ? " active" : "");
    chip.textContent = r.scenario;
    chip.addEventListener("click", () => {
      selected = r.scenario;
      renderChips();
      renderChart();
    });
    group.appendChild(chip);
  }
}

// ---------- table ----------

function sortRows() {
  rows.sort((a, b) => {
    const av = a[sortKey], bv = b[sortKey];
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    if (typeof av === "number") return (av - bv) * sortDir;
    return String(av).localeCompare(String(bv)) * sortDir;
  });
}

function renderTable() {
  sortRows();
  const tbody = document.querySelector("#board tbody");
  tbody.innerHTML = "";
  rows.forEach((r, idx) => {
    const tr = document.createElement("tr");

    const rank = document.createElement("td");
    rank.className = "num rank";
    rank.textContent = idx + 1;

    const score = document.createElement("td");
    score.className = "num";
    const pill = document.createElement("span");
    pill.className = `score-pill ${scoreClass(r.feasibility_score)}`;
    pill.textContent = r.feasibility_score ?? "—";
    score.appendChild(pill);

    const scen = document.createElement("td");
    scen.innerHTML = `<span class="scenario-name">${r.scenario}</span>`;
    if (r.description) scen.title = r.description;

    const problem = document.createElement("td");
    problem.textContent = r.problem ?? "—";

    const modality = document.createElement("td");
    modality.className = "mod";
    modality.textContent = r.modality ?? "—";

    const dist = document.createElement("td");
    dist.className = "num";
    dist.textContent = r.code_distance_d ?? "—";

    const lq = document.createElement("td");
    lq.className = "num";
    lq.textContent = fmtInt(r.logical_qubits);

    const pq = document.createElement("td");
    pq.className = "num";
    pq.textContent = fmtInt(r.physical_qubits);
    if (r.physical_qubits_source) pq.title = `source: ${r.physical_qubits_source}`;

    const wc = document.createElement("td");
    wc.className = "num";
    wc.textContent = fmtNum(r.wall_clock_days, 4);
    if (r.wall_clock_source) wc.title = `source: ${r.wall_clock_source}`;

    const warn = document.createElement("td");
    warn.className = "num";
    warn.textContent = r.warnings_count ?? "—";

    tr.append(rank, score, scen, problem, modality, dist, lq, pq, wc, warn);
    tbody.appendChild(tr);
  });

  document.querySelectorAll("#board th").forEach((th) => {
    th.classList.remove("sorted-asc", "sorted-desc");
    if (th.dataset.key === sortKey) th.classList.add(sortDir === 1 ? "sorted-asc" : "sorted-desc");
  });
}

function wireSorting() {
  document.querySelectorAll("#board th[data-key]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (sortKey === key) sortDir = -sortDir;
      else { sortKey = key; sortDir = NUMERIC_KEYS.has(key) ? -1 : 1; }
      renderTable();
    });
  });
}

// ---------- init ----------

async function init() {
  try {
    const [board, hist] = await Promise.all([
      loadJSON("data/leaderboard.json"),
      loadJSON("data/history.json").catch(() => ({ runs: [] })),
    ]);
    rows = board.rows || [];
    history = hist.runs || [];
    selected = rows.reduce((best, r) =>
      (r.feasibility_score ?? -1) > (best?.feasibility_score ?? -1) ? r : best, null)?.scenario
      || (rows[0] && rows[0].scenario) || null;

    document.getElementById("meta").textContent =
      `${rows.length} scenarios · ${history.length} historical run${history.length === 1 ? "" : "s"} · last updated ${fmtDateTime(board.generated_at)}`;

    document.getElementById("frame").hidden = false;
    document.getElementById("board-panel").hidden = false;

    renderCards(board);
    renderChips();
    renderChart();
    wireSorting();
    renderTable();

    let resizeTimer;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(renderChart, 150);
    });
  } catch (err) {
    const box = document.getElementById("error");
    box.hidden = false;
    box.textContent = `Failed to load leaderboard data: ${err.message}`;
    document.getElementById("meta").textContent = "";
  }
}

init();
