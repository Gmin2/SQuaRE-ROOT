# `square.mc` — Monte Carlo / prior predictive

## Responsibilities

- **Forward model:** `evaluate_forward_model` = patch numeric modality/QEC parameters → `build_scenario_report`.
- **Study YAML:** `load_monte_carlo_study_spec` — priors (`uniform`, `log_uniform`, `fixed`) and optional `sampling.strategy` (`independent` | `latin_hypercube`).
- **Sampling:** `run_monte_carlo_study` — draws θ, evaluates `f(θ)` (sequential or threaded `--jobs`).
- **Outputs:** CSV rows + JSON summary (`mc_summary_contract_version`, `quantiles`, `moments`, pairwise `correlations` on metrics). Bump `MC_SUMMARY_CONTRACT_VERSION` in `run_sampling.py` when the summary shape changes.

## Variance reduction

- **Latin hypercube** (`sampling.strategy: latin_hypercube`): requires **every** parameter block to be `distribution: uniform`. Use `tests/fixtures/monte_carlo_study_ecdlp_lhs.yaml` as a template. For log-spaced physical quantities, prefer **independent** draws with `log_uniform` per parameter.

## Parallelism

`n_jobs > 1` uses `ThreadPoolExecutor`. Each draw receives a **`deepcopy` of the loaded `ScenarioBundle`** before `evaluate_forward_model`, so concurrent tasks do not share mutable nested YAML dicts if the report pipeline ever mutates them. That trades CPU and memory for isolation (acceptable for moderate `n_samples`). `n_jobs == 1` reuses the original bundle reference sequentially. Speedup is **not** guaranteed on CPU-bound CPython due to the GIL; profile on your machine.

## CLI

See repo `docs/monte_carlo.md` and `square-mc` in `pyproject.toml`. With optional **matplotlib** (`pip install -e ".[plots]"`), pass **`--plot`** to write a semantics PNG next to the CSV; or run `python scripts/plot_mc_csv.py` on an existing sample file.
