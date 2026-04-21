# Monte Carlo (prior predictive)

## Purpose

Sample uncertain parameters **θ** from priors in a study YAML, evaluate the deterministic forward model **f(θ, scenario)** once per draw, and aggregate:

- Per-sample **CSV**
- JSON **summary**: **`mc_summary_contract_version`** (bump when summary shape changes), **quantiles** (p05 / p50 / p95), **moments** (mean, std, min, max), pairwise **Pearson correlations** among metric columns (complete rows only)

**Scope:** prior predictive only (no experimental likelihood / posterior here).

## Forward model

- :func:`square.mc.evaluate_forward_model` — patches modality/QEC numeric `parameter_entry` values, runs :func:`square.report.build_scenario_report`.
- Supported θ keys: :data:`square.mc.PARAMETER_LAYERS`.

## Study YAML

- ``base_scenario``: path under SQuaRE root to a scenario file.
- ``parameters``: blocks with ``parameter_key`` and ``distribution`` (`uniform`, `log_uniform`, `fixed`).
- Optional ``sampling: { strategy: independent | latin_hypercube }`` (or top-level ``sampling_strategy``).

**Latin hypercube** reduces variance for **uniform** marginals only: **every** parameter must be `distribution: uniform`. Example: ``Configs/monte_carlo_study_ecdlp_lhs.yaml``. For log-spaced positive quantities, keep **independent** sampling and use ``log_uniform`` per parameter.

## Sampling loop

- :func:`square.mc.run_monte_carlo_study` — builds θ list (independent or LHS), evaluates forward model.
- ``n_jobs > 1`` — thread pool over evaluations (shared bundle; see ``square/mc/README.md`` for GIL caveats).
- :func:`square.mc.write_mc_samples_csv` / :func:`square.mc.write_mc_summary_json` — export.

## CLI

From ``SQUARE/`` (or pass ``--root``):

```bash
square-mc Configs/monte_carlo_study_ecdlp_example.yaml --samples 200 --seed 42
square-mc Configs/monte_carlo_study_ecdlp_lhs.yaml --samples 100 --jobs 4
square-mc Configs/monte_carlo_study_ecdlp_example.yaml --samples 50 --sampling latin_hypercube
```

Writes ``mc_samples_<study_id>.csv`` and ``mc_summary_<study_id>.json`` in the cwd unless ``--output-csv`` / ``--summary-json`` are set.

### Exit codes (`square-mc`)

| Code | Meaning |
|------|---------|
| `0` | Success. |
| `1` | Operational failure (missing files, path containment, invalid study YAML, bundle load / MC run / export errors). Messages are prefixed with `square-mc:` on stderr. |
| `2` | Invalid CLI usage (e.g. ``--samples`` or ``--jobs`` less than 1). |

## Demo script

```bash
python scripts/mc_demo.py
```

Optional histogram: ``SQUARE_MC_PLOT=1 python scripts/mc_demo.py`` (requires ``matplotlib``).

## Future work

Correlated priors (Gaussian copula), quasi-Monte Carlo (Sobol), process-pool parallelism, posterior updates.
