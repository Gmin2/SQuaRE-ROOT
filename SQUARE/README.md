# SQuaRE

This repository is for the Standard Quantum Resource Estimation tool, known as SQuaRE, for gauging the resources needed to break encryption schemes, specifically ECC but others as well. The purpose of this tool is to inform and educate people on the threat of quantum computing enhanced attacks.

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

Example scenarios: `Configs/rsa2048_gidney_ekera_2021_parallel.yaml` (RSA-2048), `Configs/ecdlp_secp256k1_babbush_2026_low_toffoli.yaml` (ECDLP secp256k1, Babbush et al. envelope). **Validation / literature comparison:** add entries to `docs/validation_index.yaml` and prose under `docs/validation_overview.md` (one overview file + structured index, not one `.md` per paper).

New YAML contributions must satisfy `Schemas.yaml` (document header + provenance on every parameter: `value`, `unit`, `confidence`, `source`, `date`; add `doi` / `section` / `notes` when useful).

### Reports (JSON / Markdown)

The **output contract** for machine-readable reports is `docs/output-contract.md` (`report_contract_version`).

Reports include:

- **`qec_distance_resolution`** — how code distance `d` was chosen: CLI `--d`, explicit `qec_code_distance` / `qec.code_distance`, or `qec.distance_policy: heuristic_union_bound` (phenomenological union bound over logical qubits × depth proxy; **not** the Gidney & Ekerå optimizer).
- **`layout_estimate`** — naive data-plane qubit product; **derived non-data overhead** = Table 2 pinned total minus data plane when both exist; optional `physical_qubits_per_ccz_factory_approximate` in magic YAML for an explicit factory footprint.
- **`layout_optimization`** — scans odd code distances: union-bound mass vs budget and patch formula → data-plane qubits (optional `qec.emit_optimization_trace: true` for the full table). Distance selection uses the same discrete scan by default (`qec.distance_optimizer: discrete_scan`).
- **`timing`** — Table 2 pins, naive depth×cycle, **`schedule_model_v1`** (depth × effective layer time ÷ CCZ count, reaction-aware when inferred), and **calibration ratios** vs pinned wall-clock (see `docs/output-contract.md` non-goals).

After install, load a scenario and print a report:

```bash
square-report Configs/rsa2048_gidney_ekera_2021_parallel.yaml
square-report Configs/rsa2048_gidney_ekera_2021_parallel.yaml --markdown
python -m square Configs/rsa2048_gidney_ekera_2021_parallel.yaml
# Optional: override heuristic d (scenario may set qec.distance_policy or explicit qec_code_distance)
python -m square Configs/rsa2048_gidney_ekera_2021_parallel.yaml --d 17
```

From Python: `square.build_scenario_report(square.load_scenario_bundle(path))` and optional `square.report_to_markdown(...)`.
