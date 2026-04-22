# Contributing to SQuaRE

## Setup

```bash
cd SQUARE
python -m pip install -e ".[dev]"
```

## Lint and types

```bash
cd SQUARE
python -m ruff check square tests
python -m mypy square
```

## Tests

Run the full suite before opening a PR:

```bash
cd SQUARE
python -m pytest
```

CI runs **ruff**, **mypy**, **pytest**, and a short `square-mc` smoke test (outputs under the runner temp directory).

## Layout

- `Assumptions/` — versioned YAML assumptions (`Schemas.yaml` is the contract).
- `Algorithms/` — algorithm-level resource envelopes and formulas.
- `Configs/` — scenarios and Monte Carlo study files.
- `square/` — Python package: loader, `report`, `mc` (Monte Carlo).
- `docs/` — output contract, validation overview, Monte Carlo notes.

## Monte Carlo studies

- Study YAML: `Configs/monte_carlo_study_*.yaml`.
- CLI: `square-mc <study.yaml> --samples N --seed S` (after `pip install -e .`).
- Optional: `--jobs` for threaded parallel evaluation, `sampling.strategy: latin_hypercube` in YAML (uniform parameters only).

## Pull requests

- Keep changes focused; extend `Schemas.yaml` / `docs/output-contract.md` when report JSON shape changes in a breaking way.
- Prefer tests for new report or MC behavior.
