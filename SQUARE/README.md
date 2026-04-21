# SQuaRE

This repository is for the Standard Quantum Resource Estimation tool, known as SQuaRE, for gauging the resources needed to break encryption schemes, specifically ECC but others as well. The purpose of this tool is to inform and educate people on the threat of quantum computing enhanced attacks.

## MVP (scope and stakeholder demo)

**MVP today** means: a **transparent, YAML-driven** resource stack, a **versioned JSON report** (`docs/output-contract.md`), and **three flagship scenarios** documented in [`docs/mvp.md`](docs/mvp.md). It is **not** a browser UI with sliders, **not** every hardware modality or QEC family, and **not** automatic proof of every paper headline (see [`docs/validation_overview.md`](docs/validation_overview.md)).

**One command** after install (from this `SQUARE/` directory) to print a readable Markdown report for your boss:

```bash
python -m pip install -e .
square-mvp-demo
```

Same report as JSON: `square-mvp-demo --json`. RSA flagship instead of Oratomic: `square-mvp-demo Configs/rsa2048_gidney_ekera_2021_parallel.yaml`. If `square-mvp-demo` is not on `PATH`, use `python -m square.cli_demo` (same flags) from `SQUARE/` with the package installed.

## Assumptions database

Versioned quantitative assumptions live under `Assumptions/`:

| Path | Role |
|------|------|
| `Assumptions/Schemas.yaml` | **Contract** — `schema_version`, allowed `confidence` values, required fields for document headers and per-parameter entries, plus optional scenario-file hints. |
| `Assumptions/Modalities/` | Hardware / platform YAML profiles (one primary reference per file where possible). |
| `Assumptions/QEC_Codes/` | Quantum error correction family and layout assumptions. |
| `Assumptions/MagicStateProduction/` | Magic state factory and throughput assumptions. |
| `Assumptions/QCVV/` | Characterization / verification / validation assumptions (optional in scenarios). |
| `Assumptions/QEM/` | Error-mitigation assumptions (optional; separate file from QCVV). |

Algorithm recipes and logical-depth / T-count style data belong under `Algorithms/`. **Scenarios** that compose modality + QEC + magic + algorithm belong under `Configs/` and should reference the same `schema_version` as `Schemas.yaml`. Optional `paths.qcvv` and `paths.qem` load additional YAML profiles when present.

### Python loader

Install from the `SQUARE/` directory:

```bash
pip install -e ".[dev]"
pytest
```

Build metadata (`*.egg-info/`, `__pycache__/`, `.pytest_cache/`) is gitignored and hidden in the workspace editor settings at the repo root so local installs do not clutter the tree.

Use `square.loader.load_scenario_bundle` with a YAML under `Configs/` that lists relative `paths` to modality, `qec_code`, `magic`, `algorithm`, and optional `magic_aux`, `qcvv`, `qem`. Paths are resolved from the repo root (the directory that contains `Assumptions/Schemas.yaml`).

Example scenarios: `Configs/rsa2048_gidney_ekera_2021_parallel.yaml` (RSA-2048), `Configs/ecdlp_secp256k1_babbush_2026_low_toffoli.yaml` (ECDLP secp256k1, Babbush et al. envelope), `Configs/ecdlp_secp256k1_cain_2026_neutral_atom_qldpc.yaml` (same ECDLP algorithm envelope; Cain et al. neutral-atom modality + QLDPC). **Gold path (Oratomic):** `Configs/oratomic_gold_path.yaml` — identical composition to the Cain ECDLP scenario with stable scenario id `oratomic_gold_path` for demos and tests. **Validation / literature comparison:** add entries to `docs/validation_index.yaml` and prose under `docs/validation_overview.md` (one overview file + structured index, not one `.md` per paper).

New YAML contributions must satisfy `Schemas.yaml` (document header + provenance on every parameter: `value`, `unit`, `confidence`, `source`, `date`; add `doi` / `section` / `notes` when useful).

### Reports (JSON / Markdown)

The **output contract** for machine-readable reports is `docs/output-contract.md` (`report_contract_version`).

**Monte Carlo (prior predictive):** `docs/monte_carlo.md`, `square/mc/README.md`, module `square.mc`. After `pip install -e .`: `square-mc Configs/monte_carlo_study_ecdlp_example.yaml --samples 100 --seed 42` (add `--jobs 4` for threaded runs; LHS example: `Configs/monte_carlo_study_ecdlp_lhs.yaml`). Demo: `python scripts/mc_demo.py`.

Reports include:

- **`qec_distance_resolution`** — how code distance `d` was chosen: CLI `--d`, explicit `qec_code_distance` / `qec.code_distance`, or `qec.distance_policy: heuristic_union_bound` (phenomenological union bound over logical qubits × depth proxy; **not** the Gidney & Ekerå optimizer).
- **`layout_estimate`** — naive data-plane qubit product; **derived non-data overhead** = Table 2 pinned total minus data plane when both exist; optional `physical_qubits_per_ccz_factory_approximate` in magic YAML for an explicit factory footprint.
- **`layout_optimization`** — scans odd code distances: union-bound mass vs budget and patch formula → data-plane qubits (optional `qec.emit_optimization_trace: true` for the full table). Distance selection uses the same discrete scan by default (`qec.distance_optimizer: discrete_scan`).
- **`timing`** — Table 2 pins, naive depth×cycle, **`schedule_model_v1`** (depth × effective layer time ÷ CCZ count, reaction-aware when inferred), and **calibration ratios** vs pinned wall-clock (see `docs/output-contract.md` non-goals).

After install, load a scenario and print a report:

The scenario YAML path must resolve **under** the SQuaRE project root (the directory containing `Assumptions/Schemas.yaml`). Use `--root <path>` when your cwd or scenario path would otherwise leave the file outside that tree (same containment as `paths.*` references). Exit codes: `0` success; `1` load/build/Markdown/JSON errors (stderr prefixed `square-report:`); `2` invalid flags (e.g. `--d` / `--n` less than 1).

```bash
square-report Configs/rsa2048_gidney_ekera_2021_parallel.yaml
square-report Configs/oratomic_gold_path.yaml
square-report Configs/rsa2048_gidney_ekera_2021_parallel.yaml --markdown
python -m square Configs/rsa2048_gidney_ekera_2021_parallel.yaml
# Optional: override heuristic d (scenario may set qec.distance_policy or explicit qec_code_distance)
python -m square Configs/rsa2048_gidney_ekera_2021_parallel.yaml --d 17
```

From Python: `square.build_scenario_report(square.load_scenario_bundle(path))` and optional `square.report_to_markdown(...)`.

### Charts and interactive exploration

- **CLI plots (optional):** after `pip install -e ".[plots]"` (or add `matplotlib`), append **`--plot`** to `square-report` to write a PNG of the union failure proxy, magic throughput multiplier / adequacy, and schedule text. Default path: `<scenario_stem>_report_semantics.png`; override with **`--plot-output PATH`**. The same flag on **`square-mc`** writes `mc_samples_<study_id>_semantics.png` (or `--plot-output`) from the just-generated samples.
- **Script:** `python scripts/plot_mc_csv.py path/to/mc_samples.csv` re-renders that figure from an existing CSV.
- **Notebook:** `notebooks/osre_interactive_report.ipynb` — sliders only override keys in `PARAMETER_LAYERS` that exist in the loaded stack; **Build report** shows `extract_report_plot_frame` plus warnings and the same semantics PNG (`pip install -e ".[interactive]"`).
- **Thin web UI:** `pip install -e ".[web]"` then from `SQUARE/`: `streamlit run scripts/interactive_report_streamlit.py` — same binding rules as the notebook.
