# Scenarios (MVP)

Scenario YAML files compose assumptions from `Assumptions/Modalities/`, `Assumptions/QEC_Codes/`, `Assumptions/MagicStateProduction/`, and `Algorithms/` by path or `document_id`. The MVP flagship files also set `paths.qcvv` and `paths.qem` to **identity** profiles so reports include characterization and mitigation layers without changing Table-2-style multipliers.

Use the same `schema_version` as `Assumptions/Schemas.yaml`. See `scenario_file` hints in that schema.

**Monte Carlo study YAMLs** for tests and local experiments live under `tests/fixtures/monte_carlo_study_*.yaml` (not in `Configs/`).

## Files

| File | Composes |
|------|----------|
| `rsa2048_gidney_ekera_2021_parallel.yaml` | Gidney & Ekerå 2021 superconducting + surface + CCZ (+ T fallback aux) + RSA algorithm (Table 2 parallel row intent) + identity QCVV/QEM |
| `ecdlp_secp256k1_babbush_2026_low_toffoli.yaml` | Babbush et al. 2026 superconducting + surface + ECDLP algorithm (low-Toffoli envelope) + identity QCVV/QEM |
| `oratomic_gold_path.yaml` | **Gold path (Oratomic):** Cain et al. 2026 neutral-atom modality + QLDPC + same ECDLP algorithm + G&E magic + identity QCVV/QEM; stable `scenario: oratomic_gold_path` for demos and CI |

For **illustrative** non-identity QCVV/QEM multipliers (tests only), see `tests/fixtures/ecdlp_illustrative_qcvv_qem.yaml`.
