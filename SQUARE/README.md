# SQuaRE

This repository is for the Sentried Quantum Resource Estimation tool, known as SQuaRE, for gauging the resources needed to break encryption schemes, specifically ECC but others as well. The purpose of this tool is to inform and educate people on the threat of quantum computing enhanced attacks.

## Assumptions database

Versioned quantitative assumptions live under `Assumptions/`:

| Path | Role |
|------|------|
| `Assumptions/Schemas.yaml` | **Contract** — `schema_version`, allowed `confidence` values, required fields for document headers and per-parameter entries, plus optional scenario-file hints. |
| `Assumptions/Modalities/` | Hardware / platform YAML profiles (one primary reference per file where possible). |
| `Assumptions/QEC_Codes/` | Quantum error correction family and layout assumptions. |
| `Assumptions/MagicStateProduction/` | Magic state factory and throughput assumptions. |

Algorithm recipes and logical-depth / T-count style data belong under `Algorithms/`. **Scenarios** that compose modality + QEC + magic + algorithm belong under `Configs/` and should reference the same `schema_version` as `Schemas.yaml`.

### Python loader

Install from the `SQUARE/` directory:

```bash
pip install -e ".[dev]"
pytest
```

Build metadata (`*.egg-info/`, `__pycache__/`, `.pytest_cache/`) is gitignored and hidden in the workspace editor settings at the repo root so local installs do not clutter the tree.

Use `square_re.loader.load_scenario_bundle` with a YAML under `Configs/` that lists relative `paths` to modality, `qec_code`, `magic`, `algorithm`, and optional `magic_aux`. Paths are resolved from the repo root (the directory that contains `Assumptions/Schemas.yaml`).

Example scenario: `Configs/rsa2048_gidney_ekera_2021_parallel.yaml`.

New YAML contributions must satisfy `Schemas.yaml` (document header + provenance on every parameter: `value`, `unit`, `confidence`, `source`, `date`; add `doi` / `section` / `notes` when useful).
