# QEC codes

YAML profiles for error-correcting code families and implementation choices (surface, color, etc.). Each file must follow `../Schemas.yaml` (`document_header` + `parameter_entry` per assumption).

Place one logical profile per file (e.g. `surface_gidney_ekera_2021.yaml`).

## Profiles

| File | Reference |
|------|-----------|
| `surface_gidney_ekera_2021.yaml` | Gidney & Ekerå, *Quantum* 5, 433 (2021); surface patches + lattice surgery |
| `qldpc_cain_et_al_2026.yaml` | Cain et al. (2026), arXiv:2603.28627; quantum LDPC headline + phenomenological patch proxy in `d` |
