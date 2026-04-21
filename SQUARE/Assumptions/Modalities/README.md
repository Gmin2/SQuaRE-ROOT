# Modalities

YAML profiles for hardware platforms (e.g. superconducting, trapped ion). Each file must declare the header fields required by `../Schemas.yaml` and use `parameter_entry` rules for every numeric or symbolic assumption.

**OSRE extended physical layer (required for every profile in this directory):** Each modality file must define all eight canonical `parameter_entry` keys (`coherence_time_t1_microseconds`, `coherence_time_t2_microseconds`, `single_qubit_gate_error_rate`, `two_qubit_gate_error_rate`, `measurement_error_rate`, `idle_error_rate_per_cycle`, `correlated_noise_parameter`, `leakage_error_rate`) with `value`, `unit`, `confidence`, `source`, and `date` per `../Schemas.yaml`. Use `confidence: speculative` and honest `notes` when the primary reference does not pin a quantity. Reports copy these into top-level `physical_layer` (see `docs/output-contract.md` § `physical_layer`). Regression: `tests/test_modalities_osre_physical_parity.py`.

Place one logical profile per file (e.g. `superconducting_gidney_ekera_2021.yaml`).

## Profiles

| File | Reference |
|------|-----------|
| `superconducting_gidney_ekera_2021.yaml` | Gidney & Ekerå, *Quantum* 5, 433 (2021); Table 2 physical assumptions |
| `superconducting_babbush_et_al_2026.yaml` | Babbush et al. (2026); ~10⁻³ gate error + planar superconducting headline baseline (cycle/reaction placeholders documented) |
| `neutral_atom_cain_et_al_2026.yaml` | Cain et al. (2026), arXiv:2603.28627; neutral-atom / reconfigurable headline (effective QEC-cycle proxies documented) |
