# Scenarios

Scenario YAML files compose assumptions from `Assumptions/Modalities/`, `Assumptions/QEC_Codes/`, `Assumptions/MagicStateProduction/`, and `Algorithms/` by path or `document_id`. Optionally add `paths.qcvv` and/or `paths.qem` for separate characterization and mitigation profiles (see `Assumptions/QCVV/` and `Assumptions/QEM/`).

Use the same `schema_version` as `Assumptions/Schemas.yaml`. See `scenario_file` hints in that schema.

**Baseline vs QCVV/QEM-wired:** Flagship files without `paths.qcvv` / `paths.qem` keep reports minimal (`VER` / `mitigated_operations_ceiling` omitted when paths absent). Companion `*_qcvv_qem.yaml` scenarios duplicate a stack with **identity** placeholders (σ=s=Γ=1) so layers load without changing Table-2-style numbers. Use `ecdlp_secp256k1_babbush_2026_low_toffoli_illustrative_qcvv_qem.yaml` for non-identity illustrative multipliers.

## Scenarios

| File | Composes |
|------|----------|
| `rsa2048_gidney_ekera_2021_parallel.yaml` | Gidney & Ekerå 2021 superconducting + surface + CCZ (+ T fallback aux) + RSA algorithm (Table 2 parallel row intent) |
| `rsa2048_gidney_ekera_2021_parallel_qcvv_qem.yaml` | Same as parallel RSA + `identity_no_overhead` QCVV/QEM (wires paths; same multipliers as baseline) |
| `ecdlp_secp256k1_babbush_2026_low_toffoli.yaml` | Babbush et al. 2026 superconducting + surface + ECDLP algorithm (low-Toffoli envelope) |
| `ecdlp_secp256k1_babbush_2026_low_toffoli_qcvv_qem.yaml` | Same ECDLP stack + identity QCVV/QEM |
| `ecdlp_secp256k1_babbush_2026_low_toffoli_illustrative_qcvv_qem.yaml` | Same ECDLP stack + illustrative σ=1.15 QCVV and ZNE-style QEM stub (s=0.85, Γ=4) |
| `ecdlp_secp256k1_cain_2026_neutral_atom_qldpc.yaml` | Cain et al. 2026 neutral-atom modality + QLDPC + same ECDLP algorithm + G&E magic (arXiv:2603.28627 stack) |
| `oratomic_gold_path.yaml` | **Gold path (Oratomic)** — same stack as the Cain row above; stable `scenario: oratomic_gold_path` for tutorials and CI |
| `oratomic_gold_path_qcvv_qem.yaml` | Same as gold path + identity QCVV/QEM |
