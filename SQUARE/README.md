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

Algorithm recipes and logical-depth / T-count style data belong under `Algorithms/`. **Scenarios** that compose modality + QEC + magic + algorithm belong under `Configs/` and should reference the same `schema_version` as `Schemas.yaml` once loaders exist.

New YAML contributions must satisfy `Schemas.yaml` (document header + provenance on every parameter: `value`, `unit`, `confidence`, `source`, `date`; add `doi` / `section` / `notes` when useful).
