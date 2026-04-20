# Scenarios

Scenario YAML files compose assumptions from `Assumptions/Modalities/`, `Assumptions/QEC_Codes/`, `Assumptions/MagicStateProduction/`, and `Algorithms/` by path or `document_id`. Optionally add `paths.qcvv` and/or `paths.qem` for separate characterization and mitigation profiles.

Use the same `schema_version` as `Assumptions/Schemas.yaml`. See `scenario_file` hints in that schema.

## Scenarios

| File | Composes |
|------|----------|
| `rsa2048_gidney_ekera_2021_parallel.yaml` | Gidney & Ekerå 2021 superconducting + surface + CCZ (+ T fallback aux) + RSA algorithm (Table 2 parallel row intent) |
| `ecdlp_secp256k1_babbush_2026_low_toffoli.yaml` | Babbush et al. 2026 superconducting + surface + ECDLP algorithm (low-Toffoli envelope) |
| `ecdlp_secp256k1_cain_2026_neutral_atom_qldpc.yaml` | Cain et al. 2026 neutral-atom modality + QLDPC + same ECDLP algorithm + G&E magic (arXiv:2603.28627 stack) |
| `oratomic_gold_path.yaml` | **Gold path (Oratomic)** — same stack as the Cain row above; stable `scenario: oratomic_gold_path` for tutorials and CI |
