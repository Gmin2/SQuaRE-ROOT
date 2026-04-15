# Monte Carlo (prior predictive)

## Purpose

Sample uncertain parameters **θ** from priors declared in a study YAML, evaluate the deterministic forward model **f(θ, scenario)** once per draw, and aggregate **CSV samples** plus **p05 / p50 / p95** summaries.

**Scope:** prior predictive only (no experimental likelihood / posterior in this slice).

## Forward model

- :func:`square.mc.evaluate_forward_model` — patches modality/QEC numeric `parameter_entry` values, runs :func:`square.report.build_scenario_report`.
- Supported θ keys: :data:`square.mc.PARAMETER_LAYERS`.

## Study YAML

- ``base_scenario``: path under SQuaRE root to a scenario file.
- ``parameters``: list of blocks with ``parameter_key`` and ``distribution`` (`uniform`, `log_uniform`, `fixed`).

Example: ``Configs/monte_carlo_study_ecdlp_example.yaml``.

## Sampling loop

- :func:`square.mc.run_monte_carlo_study` — ``n_samples`` draws; independent marginals per parameter.
- :func:`square.mc.write_mc_samples_csv` / :func:`square.mc.write_mc_summary_json` — export.

## CLI

From the ``SQUARE/`` directory (or pass ``--root``):

```bash
square-mc Configs/monte_carlo_study_ecdlp_example.yaml --samples 200 --seed 42
```

Writes ``mc_samples_<study_id>.csv`` and ``mc_summary_<study_id>.json`` in the current working directory unless ``--output-csv`` / ``--summary-json`` are set.

## Future work

Correlated priors, Sobol indices, and posterior updates are out of scope for this module.
