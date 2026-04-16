# Modalities

YAML profiles for hardware platforms (e.g. superconducting, trapped ion). Each file must declare the header fields required by `../Schemas.yaml` and use `parameter_entry` rules for every numeric or symbolic assumption.

**OSRE extended physical layer (optional):** Headline modalities may define additional `parameter_entry` rows (T1/T2, single- and two-qubit errors, measurement, idle proxy, correlated-noise multiplier, leakage) documented in `docs/output-contract.md` § `physical_layer`. Reports surface them under top-level `physical_layer` as a curated passthrough.

Place one logical profile per file (e.g. `superconducting_gidney_ekera_2021.yaml`).

## Profiles

| File | Reference |
|------|-----------|
| `superconducting_gidney_ekera_2021.yaml` | Gidney & Ekerå, *Quantum* 5, 433 (2021); Table 2 physical assumptions |
| `superconducting_babbush_et_al_2026.yaml` | Babbush et al. (2026); ~10⁻³ gate error + planar superconducting headline baseline (cycle/reaction placeholders documented) |
| `neutral_atom_cain_et_al_2026.yaml` | Cain et al. (2026), arXiv:2603.28627; neutral-atom / reconfigurable headline (effective QEC-cycle proxies documented) |
