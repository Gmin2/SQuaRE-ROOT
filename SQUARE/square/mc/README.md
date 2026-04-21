# `square.mc` — Monte Carlo / prior predictive

## Responsibilities

- **Forward model:** `evaluate_forward_model` = patch numeric modality/QEC parameters → `build_scenario_report`.
- **Study YAML:** `load_monte_carlo_study_spec` — priors (`uniform`, `log_uniform`, `fixed`) and optional `sampling.strategy` (`independent` | `latin_hypercube`).
- **Sampling:** `run_monte_carlo_study` — draws θ, evaluates `f(θ)` (sequential or threaded `--jobs`).
- **Outputs:** CSV rows + JSON summary (`mc_summary_contract_version`, `quantiles`, `moments`, pairwise `correlations` on metrics). Bump `MC_SUMMARY_CONTRACT_VERSION` in `run_sampling.py` when the summary shape changes.

## Variance reduction

- **Latin hypercube** (`sampling.strategy: latin_hypercube`): requires **every** parameter block to be `distribution: uniform`. Use `Configs/monte_carlo_study_ecdlp_lhs.yaml` as a template. For log-spaced physical quantities, prefer **independent** draws with `log_uniform` per parameter.

## Parallelism

`n_jobs > 1` uses `ThreadPoolExecutor` and a **shared** loaded `ScenarioBundle`. Each draw calls `apply_numeric_overrides`, which builds **shallow** copies of the modality/QEC document roots and **`deepcopy`s only the overridden `parameter_entry` nodes** (not full trees). Speedup is **not** guaranteed on CPU-bound CPython due to the GIL; use for moderate `n_samples` or profile on your machine.

## CLI

See repo `docs/monte_carlo.md` and `square-mc` in `pyproject.toml`.
