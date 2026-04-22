# QCVV (quantum characterization, verification, and validation)

YAML profiles for calibration uncertainty, tomography-derived error models, SPAM and gate characterization bounds, and related stack assumptions that sit **between** raw hardware modality and QEC/magic layers.

Each file must declare the header fields required by `../Schemas.yaml` and use `parameter_entry` rules for every quantified assumption.

Place one logical profile per file (e.g. `identity_no_overhead.yaml` for a no-op placeholder until paper-specific QCVV blocks are added).

## Profiles

| File | Role |
|------|------|
| `identity_no_overhead.yaml` | Placeholder: explicit unit multipliers of 1.0 so scenarios can wire QCVV without changing downstream math yet |
| `benchmarking_operational_error_sigma_1_15.yaml` | Illustrative σ=1.15 multiplier for VER and effective-error stack (speculative provenance; swap for device-specific QCVV) |
