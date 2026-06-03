# Q-Day Leaderboard

A static scoreboard that runs every scenario in `Configs/` through `square-report`,
computes a CRQC feasibility score, and publishes a sortable table (with score
sparklines) to GitHub Pages. It is rebuilt on every push to `main`, nightly, and on
manual dispatch, so assumption drift surfaces the moment it lands.

- Build script: [`scripts/build_leaderboard.py`](../scripts/build_leaderboard.py)
- Static site: [`site/`](../site/) (vanilla HTML/CSS/JS, no framework)
- Workflow: [`.github/workflows/leaderboard.yml`](../../.github/workflows/leaderboard.yml)

## CRQC Feasibility Score

The score is a **transparent proxy for near-term threat, not an endorsement of
feasibility**. Smaller resource footprints score higher (closer to achievable).

Let `V` be the spacetime volume in **megaqubit-days**:

```
V = (physical_qubits / 1e6) * wall_clock_days
score = clamp(20 * (1 - log10(V)), 0, 100)
```

The mapping is anchored on an absolute log scale (it does not depend on the other
scenarios on the board, so the number is comparable across time):

| Spacetime volume `V` | Score |
|----------------------|-------|
| 1e-4 megaqubit-days  | 100   |
| 1e-1 megaqubit-days  | 80    |
| 1.0 megaqubit-days   | 20    |
| 1e1 megaqubit-days   | 0 (clamped) |

On the current flagship scenarios this yields roughly: ECDLP secp256k1
(superconducting) ~88, Oratomic gold path ~60, RSA-2048 (Gidney & Ekerå parallel) ~4 —
matching intuition that RSA-2048 at ~20M physical qubits is the furthest from feasible.

This is the "simpler proxy" option from the issue. It is intentionally **not** the
deck slide-10 prioritisation formula `P = Value(Importance) × Vulnerability(Urgency)`,
which ranks *which problems matter*, not *how achievable a quantum attack is*. If a
value/urgency weighting is wanted later, multiply this resource score by a per-problem
weight.

## Column provenance (fallback chains)

RSA and ECDLP reports populate different `dashboard` fields, so two headline columns use
a documented fallback chain — the first present (non-null) value wins. The chosen source
is shown on hover in the table and stored per row in `leaderboard.json`.

**Physical qubits** (`physical_qubits`, `physical_qubits_source`):

1. `reported_rsa2048_physical_qubits_millions` × 1e6  (paper Table 2 end-to-end total)
2. `ecdlp_paper_headline_physical_qubits_upper_bound`  (paper headline upper bound)
3. `approximate_data_plane_physical_qubits`  (data-plane proxy; omits factories/routing)

**Wall-clock days** (`wall_clock_days`, `wall_clock_source`):

1. `reported_rsa2048_wall_clock_days`  (paper Table 2 pinned)
2. `schedule_model_v1_wall_clock_days`  (heuristic parallel schedule)
3. `naive_serial_time_days_from_depth_times_cycle`  (depth × cycle; optimistic, no parallelism)

Other columns map directly: `code_distance_d`, `logical_qubits_at_n`, `target.problem`,
`layers.modality.document_id`, `report_contract_version`, `generated_at`, and the count of
report `warnings`.

## Historical view

Each build appends a snapshot `{commit, timestamp, scores}` to `data/history.json`,
fetched from the previously published site so it survives across deploys (a first run with
no prior history simply starts fresh). The table renders a per-scenario sparkline of score
over the last `MAX_HISTORY_POINTS` runs (default 60). A single run shows the bare value;
two or more draw the trend line.

## Running it locally

```bash
cd SQUARE
pip install -e .
python scripts/build_leaderboard.py            # writes site/data/{leaderboard,history}.json
python -m http.server -d site 8000             # open http://localhost:8000
```

The script exits non-zero (failing CI) if any scenario's report errors, so the board never
publishes partial results.
