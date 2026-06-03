"use strict";

// Vanilla JS Q-Day Leaderboard renderer: fetch data, render a sortable table with
// per-scenario score sparklines. No framework, no build step.

const NUMERIC_KEYS = new Set([
  "feasibility_score",
  "code_distance_d",
  "logical_qubits",
  "physical_qubits",
  "wall_clock_days",
  "warnings_count",
]);

let rows = [];
let history = [];
let sortKey = "feasibility_score";
let sortDir = -1; // -1 desc, 1 asc

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

function scoreClass(score) {
  if (score === null || score === undefined) return "";
  if (score >= 66) return "score-good";
  if (score >= 33) return "score-mid";
  return "score-bad";
}

// Build an SVG sparkline of a scenario's score across history runs (oldest -> newest).
function sparkline(scenario) {
  const series = history
    .map((run) => (run.scores ? run.scores[scenario] : null))
    .filter((v) => v !== null && v !== undefined);
  if (series.length < 2) {
    const span = document.createElement("span");
    span.className = "muted";
    span.textContent = series.length === 1 ? `${series[0]}` : "—";
    return span;
  }
  const w = 90, h = 24, pad = 2;
  const min = Math.min(...series), max = Math.max(...series);
  const range = max - min || 1;
  const pts = series.map((v, i) => {
    const x = pad + (i * (w - 2 * pad)) / (series.length - 1);
    const y = h - pad - ((v - min) / range) * (h - 2 * pad);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "spark");
  svg.setAttribute("width", w);
  svg.setAttribute("height", h);
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  const poly = document.createElementNS(svg.namespaceURI, "polyline");
  poly.setAttribute("points", pts.join(" "));
  poly.setAttribute("fill", "none");
  poly.setAttribute("stroke", "#58a6ff");
  poly.setAttribute("stroke-width", "1.5");
  svg.appendChild(poly);
  const last = series[series.length - 1];
  const lastPt = pts[pts.length - 1].split(",");
  const dot = document.createElementNS(svg.namespaceURI, "circle");
  dot.setAttribute("cx", lastPt[0]);
  dot.setAttribute("cy", lastPt[1]);
  dot.setAttribute("r", "2");
  dot.setAttribute("fill", last >= series[0] ? "#3fb950" : "#f85149");
  svg.appendChild(dot);
  svg.appendChild(document.createElementNS(svg.namespaceURI, "title"))
    .textContent = `${series.length} runs: ${series.join(" → ")}`;
  return svg;
}

function sortRows() {
  rows.sort((a, b) => {
    const av = a[sortKey], bv = b[sortKey];
    if (av === null || av === undefined) return 1;
    if (bv === null || bv === undefined) return -1;
    if (typeof av === "number") return (av - bv) * sortDir;
    return String(av).localeCompare(String(bv)) * sortDir;
  });
}

function render() {
  sortRows();
  const tbody = document.querySelector("#board tbody");
  tbody.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");

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

    const trend = document.createElement("td");
    trend.className = "num";
    trend.appendChild(sparkline(r.scenario));

    const warn = document.createElement("td");
    warn.className = "num";
    warn.textContent = r.warnings_count ?? "—";

    tr.append(score, scen, problem, modality, dist, lq, pq, wc, trend, warn);
    tbody.appendChild(tr);
  }
  updateHeaderIndicators();
}

function updateHeaderIndicators() {
  document.querySelectorAll("#board th").forEach((th) => {
    th.classList.remove("sorted-asc", "sorted-desc");
    if (th.dataset.key === sortKey) {
      th.classList.add(sortDir === 1 ? "sorted-asc" : "sorted-desc");
    }
  });
}

function wireSorting() {
  document.querySelectorAll("#board th[data-key]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (sortKey === key) {
        sortDir = -sortDir;
      } else {
        sortKey = key;
        sortDir = NUMERIC_KEYS.has(key) ? -1 : 1;
      }
      render();
    });
  });
}

async function init() {
  try {
    const [board, hist] = await Promise.all([
      loadJSON("data/leaderboard.json"),
      loadJSON("data/history.json").catch(() => ({ runs: [] })),
    ]);
    rows = board.rows || [];
    history = hist.runs || [];
    const when = board.generated_at || "unknown";
    const commit = board.commit ? ` · commit ${board.commit}` : "";
    document.getElementById("meta").textContent =
      `${rows.length} scenarios · last updated ${when}${commit} · ${history.length} historical runs`;
    document.getElementById("board").hidden = false;
    wireSorting();
    render();
  } catch (err) {
    const box = document.getElementById("error");
    box.hidden = false;
    box.textContent = `Failed to load leaderboard data: ${err.message}`;
    document.getElementById("meta").textContent = "";
  }
}

init();
