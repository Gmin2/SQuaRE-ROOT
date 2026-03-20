# SQuaRE report output contract

This document defines the **machine-readable report** produced after loading a scenario bundle (`ScenarioBundle`). Tooling and UIs should treat `report_contract_version` as the compatibility anchor.

## Versioning

| Field | Meaning |
|-------|---------|
| `report_contract_version` | Integer. Bump when top-level keys or semantics change in a breaking way. |
| `schema_version` (inside `scenario`) | Assumptions / scenario YAML version from `Assumptions/Schemas.yaml`. |

## Top-level envelope

Every report is a JSON-serializable object with at least:

| Key | Type | Description |
|-----|------|-------------|
| `report_contract_version` | `number` | Contract version (currently `1`). |
| `engine` | `object` | `{ "name": "square", "version": "<package version>" }`. |
| `generated_at` | `string` | ISO-8601 UTC timestamp when the report was built. |
| `warnings` | `array` | Human-readable strings for caveats (missing distance `d`, symbolic formulas, branch flags). |
| `scenario` | `object` | Subset of the scenario YAML (identity, description, paths, `schema_version`). |
| `target` | `object` | Resolved problem target, e.g. `modulus_bit_length`, `problem`. |
| `table2_reference` | `object \| null` | Optional scenario block such as `table2_reference_row` when present. |
| `sources` | `object` | Per-layer document headers (`document_id`, `primary_reference`, `doi`, `arxiv`, `date_issued`, `notes`). |
| `layers` | `object` | Structured view of modality, QEC, magic, optional `magic_aux`, and algorithm (see below). |
| `algorithm_metrics` | `object` | Numeric roll-up at the scenario’s `n` (and optional pinned table entries from YAML). |
| `dashboard` | `object` | Cross-layer headline numbers for quick comparison (may include `null` where data is missing). |
| `qec_overhead` | `object` | Slots for code-distance-dependent overhead (e.g. patch qubit formula + `d`); see below. |
| `physical_rollup` | `object` | End-to-end **data-plane** physical qubit roll-up when both `n` and `d` are available; see below. |

## Scenario inputs for `d`

Reports fill QEC patch metrics when **code distance** is supplied:

| Source | Precedence |
|--------|------------|
| CLI `--d` | Highest (override). |
| `qec_code_distance` | Top-level scenario integer. |
| `qec.code_distance` | Nested under `qec:` in the scenario file. |

## `layers` shape

Each of `modality`, `qec`, `magic`, `algorithm` contains:

| Key | Type | Description |
|-----|------|-------------|
| `document_id` | `string` | From the loaded YAML. |
| `header` | `object` | Header fields only (no per-parameter maps). |
| `parameters` | `object` | Map of parameter name → full YAML entry (`value`, `unit`, `confidence`, `source`, `date`, optional `section`, `notes`, `layer`). |

`magic_aux` uses the same shape when the scenario lists `paths.magic_aux`; otherwise it is `null`.

## `algorithm_metrics`

| Key | Type | Description |
|-----|------|-------------|
| `n` | `number` | Modulus bit length used for evaluation (from `target.modulus_bit_length` or override). |
| `evaluated` | `object` | Per-metric objects when the YAML formula is a **closed-form expression in `n`** using `+ - * / // % **` and `log2(...)`. Each value is `{ "value": number, "source_parameter": string, "provenance": "computed_from_yaml_formula" }`. |
| `evaluated_skipped` | `array` | Parameter keys not evaluated (e.g. strings containing `O(1)`). |
| `pinned_in_algorithm_yaml` | `object` | Map of parameter key → entry for paper-pinned values at specific `n` (e.g. billions of Toffoli+T/2, megaqubit-days) when `n` matches. |

## `dashboard`

Headline fields (all optional / nullable):

| Key | Description |
|-----|-------------|
| `ccz_factory_count` | Inferred from scenario `table2_reference_row` when the value matches `*_(\d+)_ccz`. |
| `reported_rsa2048_physical_qubits_millions` | From magic YAML when the CCZ count matches a `rsa_2048_reported_physical_qubits_millions_*_ccz` key. |
| `logical_qubits_at_n` | Evaluated abstract logical qubits at `n`. |
| `toffoli_plus_t_halves_billions_at_n` | From pinned row at `n` when available, else `null`. |
| `minimum_spacetime_volume_megaqubitdays_at_n` | From pinned row at `n` when available. |
| `logical_qubit_physical_qubits_if_distance_d` | Physical qubits per logical from the QEC profile patch formula evaluated at scenario/CLI `d`; `null` if `d` or formula missing. |
| `approximate_data_plane_physical_qubits` | `abstract_logical_qubits × physical_qubits_per_logical` when both exist; `null` otherwise. Naive data-qubit proxy (see warnings). |
| `t_factory_fallback_recommended` | From `magic_aux` when `n` exceeds the documented CCZ error-budget transition scale. |
| `t_factory_transition_modulus_bits_order_of_magnitude` | From `magic_aux` when present (paper’s approximate transition scale). |
| `ccz_factory_parameter_key` | Magic YAML parameter key whose `value` matches the inferred CCZ count, when found. |
| `rsa_2048_reported_physical_qubits_millions_key` | Magic YAML key used for the RSA-2048 headline, when resolved. |

## `qec_overhead`

`qec_overhead.logical_qubit_patch_physical_qubit_count` holds:

| Key | Description |
|-----|-------------|
| `formula` | String from the QEC profile when available. |
| `distance_d` | Code distance when supplied by the scenario/engine; otherwise `null`. |
| `physical_qubits_per_logical` | Evaluated patch formula at `d` when possible; otherwise `null`. |
| `status` | `"evaluated"` \| `"pending_distance_d"` \| `"no_formula_in_profile"` \| `"eval_failed"`. |
| `provenance` | When evaluated: `"computed_from_yaml_formula"`. |
| `source_parameter` | When evaluated: e.g. `logical_qubit_patch_physical_qubit_count_formula`. |

## `physical_rollup`

| Key | Description |
|-----|-------------|
| `code_distance_d` | Resolved `d` or `null`. |
| `physical_qubits_per_logical` | Same as `qec_overhead.logical_qubit_patch_physical_qubit_count.physical_qubits_per_logical`. |
| `abstract_logical_qubits_at_n` | From `algorithm_metrics.evaluated.abstract_logical_qubits.value` when present. |
| `approximate_data_plane_physical_qubits` | Product when both factors exist; mirrors `dashboard.approximate_data_plane_physical_qubits`. |
| `patch_formula_status` | Same string as `qec_overhead...status`. |

## Provenance

Per-parameter `source`, `date`, `doi`, `section`, and `confidence` are **passed through** from YAML; the report does not invent citations. Values computed only for display (e.g. formula evaluation) appear under `algorithm_metrics.evaluated` with `provenance: "computed_from_yaml_formula"` in the implementation’s internal structure where applicable.

Evaluable formula strings follow **Python** syntax for powers (`**`, not `^`).

## Serial formats

- **JSON**: Canonical interchange; `build_scenario_report` returns a structure suitable for `json.dumps`.
- **Markdown**: Optional human summary via `report_to_markdown(report)` — same information density is not guaranteed; use JSON for completeness.

## Non-goals (current contract)

- `approximate_data_plane_physical_qubits` is **not** a full device layout count (magic factories, routing, distillation footprint, etc.).
- No endorsement of feasibility; warnings highlight missing inputs, naive products, and branch cuts (e.g. T-factory fallback).
