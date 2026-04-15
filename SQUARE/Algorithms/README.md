# Algorithms

YAML (or future formats) describing cryptographic problem targets, Shor-style constructions, logical qubit counts, T/Toffoli counts, and related algorithm-level assumptions.

Each file should declare a `document_header` consistent with `Assumptions/Schemas.yaml` and cite primary references with `doi` / `arxiv` where possible. Paper-pinned headline numbers at fixed `n` can live in one structured block (e.g. `paper_table1_pins_by_modulus_bit_length`) instead of many flat `*_n_*` keys.

## Profiles

| File | Reference |
|------|-----------|
| `shor_rsa_gidney_ekera_2021.yaml` | Gidney & Ekerå, *Quantum* 5, 433 (2021); Table 1 abstract costs + RSA / Ekerå–Håstad context |
| `ecdlp_secp256k1_babbush_et_al_2026.yaml` | Babbush et al. (2026), ECDLP on secp256k1; abstract logical qubit / Toffoli envelopes + narrative physical-qubit headline |
