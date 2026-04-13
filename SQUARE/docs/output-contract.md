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
| `report_contract_version` | `number` | Contract version (currently `4`). |
| `engine` | `object` | `{ "name": "square", "version": "<package version>" }`. |
| `generated_at` | `string` | ISO-8601 UTC timestamp when the report was built. |
| `warnings` | `array` | Human-readable strings for caveats (missing distance `d`, symbolic formulas, branch flags). |
| `scenario` | `object` | Subset of the scenario YAML (identity, description, paths, `schema_version`). |
| `target` | `object` | Resolved problem target, e.g. `modulus_bit_length`, `problem`. |
| `table2_reference` | `object \| null` | Optional scenario block such as `table2_reference_row` when present. |
| `sources` | `object` | Per-layer document headers (`document_id`, `primary_reference`, `doi`, `arxiv`, `date_issued`, `notes`). Includes optional `qcvv` and `qem` when scenario `paths` list them. |
| `layers` | `object` | Structured view of modality, QEC, magic, optional `magic_aux`, optional `qcvv` / `qem`, and algorithm (see below). |
| `algorithm_metrics` | `object` | Numeric roll-up at the scenario’s `n` (and optional pinned table entries from YAML). |
| `dashboard` | `object` | Cross-layer headline numbers for quick comparison (may include `null` where data is missing). |
| `qec_overhead` | `object` | Slots for code-distance-dependent overhead (e.g. patch qubit formula + `d`); see below. |
| `physical_rollup` | `object` | End-to-end **data-plane** physical qubit roll-up when both `n` and `d` are available; see below. |
| `timing` | `object` | Table 2 pins, naive depth×cycle, optional schedule heuristic + calibration; see below. |
| `qec_distance_resolution` | `object` | How `d` was chosen (`cli_override`, `explicit_scenario`, `heuristic_union_bound`, etc.). |
| `layout_estimate` | `object` | Data-plane proxy, pinned end-to-end qubits, derived non-data overhead, optional YAML factory footprint; see below. |
| `layout_optimization` | `object \| null` | Per-distance scan: union-bound mass and patch/data-plane proxies; see below. |

## Scenario inputs for `d`

Reports fill QEC patch metrics when **code distance** is resolved:

| Source | Precedence |
|--------|------------|
| CLI `--d` | Highest (override). |
| `qec_code_distance` | Top-level scenario integer. |
| `qec.code_distance` | Nested under `qec:` in the scenario file. |
| `qec.distance_policy` | If set to `heuristic_union_bound` (aliases: `optimize_heuristic`, `heuristic`) and explicit `d` is absent, use phenomenological heuristic (see `qec_distance_resolution`). |

Optional scenario keys for the heuristic: `qec.logical_error_budget` (default `0.1`). Tunables live on the QEC profile (`heuristic_*` parameters in YAML).

- `qec.distance_optimizer`: `discrete_scan` (default) runs a **discrete odd-`d` scan** for the smallest distance meeting the union bound; `closed_form` uses the legacy closed-form inversion + clamping.
- `qec.emit_optimization_trace`: if true, `layout_optimization.candidates` lists every scanned `d` (union-bound mass, data-plane proxy, optional residual vs reported total).
- `qec.emit_layout_optimization`: if false, omits the entire `layout_optimization` block.

Optional schedule steering: `schedule.reaction_limited` (`boolean`); otherwise inferred from `table2_reference_row` / factory key text (`distillation` → not reaction-limited for the simple model).

## `layers` shape

Each of `modality`, `qec`, `magic`, `algorithm` contains:

| Key | Type | Description |
|-----|------|-------------|
| `document_id` | `string` | From the loaded YAML. |
| `header` | `object` | Header fields only (no per-parameter maps). |
| `parameters` | `object` | Map of parameter name → full YAML entry (`value`, `unit`, `confidence`, `source`, `date`, optional `section`, `notes`, `layer`). |

`magic_aux` uses the same shape when the scenario lists `paths.magic_aux`; otherwise it is `null`.

`qcvv` and `qem` use the same shape when the scenario lists `paths.qcvv` / `paths.qem` respectively; otherwise each is `null`. Downstream resource math may ignore these until wired; they are loaded and exposed for provenance and future roll-ups.

## `algorithm_metrics`

| Key | Type | Description |
|-----|------|-------------|
| `n` | `number` | Modulus bit length used for evaluation (from `target.modulus_bit_length` or override). |
| `evaluated` | `object` | Per-metric objects when the YAML formula is a **closed-form expression in `n`** using `+ - * / // % **` and `log2(...)`. Each value is `{ "value": number, "source_parameter": string, "provenance": "computed_from_yaml_formula" }`. |
| `evaluated_skipped` | `array` | Parameter keys not evaluated (e.g. strings containing `O(1)`). |
| `pinned_in_algorithm_yaml` | `object` | Map of parameter key → entry for paper-pinned values at specific `n`. May include synthetic keys (e.g. `toffoli_plus_t_halves_count_billions_n_<n>`) resolved from a consolidated `paper_table1_pins_by_modulus_bit_length` block when present. |

## `dashboard`

Headline fields (all optional / nullable):

| Key | Description |
|-----|-------------|
| `ccz_factory_count` | Inferred from scenario `table2_reference_row` when the value matches `*_(\d+)_ccz`. |
| `reported_rsa2048_physical_qubits_millions` | From magic YAML `paper_table2_rsa2048_reference_rows` when the scenario’s inferred CCZ count matches a row’s `ccz_factories`. |
| `logical_qubits_at_n` | Evaluated abstract logical qubits at `n`. |
| `toffoli_plus_t_halves_billions_at_n` | From `paper_table1_pins_by_modulus_bit_length` for string key `str(n)` when present, else `null`. |
| `minimum_spacetime_volume_megaqubitdays_at_n` | From the same Table 1 consolidated block when present. |
| `logical_qubit_physical_qubits_if_distance_d` | Physical qubits per logical from the QEC profile patch formula evaluated at scenario/CLI `d`; `null` if `d` or formula missing. |
| `approximate_data_plane_physical_qubits` | `abstract_logical_qubits × physical_qubits_per_logical` when both exist; `null` otherwise. Naive data-qubit proxy (see warnings). |
| `t_factory_fallback_recommended` | From `magic_aux` when `n` exceeds the documented CCZ error-budget transition scale. |
| `t_factory_transition_modulus_bits_order_of_magnitude` | From `magic_aux` when present (paper’s approximate transition scale). |
| `ccz_factory_parameter_key` | Table 2 row `layout_descriptor` from the matched `paper_table2_rsa2048_reference_rows` entry (used for simple schedule inference), when present. |
| `table2_pinned_source_parameter` | Name of the consolidated magic YAML parameter (`paper_table2_rsa2048_reference_rows`) when CCZ count is inferred; otherwise `null`. |
| `table2_pinned_row_layout_descriptor` | Same as `ccz_factory_parameter_key` (explicit slot for UIs). |
| `rsa_2048_reported_physical_qubits_millions_key` | Logical ref: `paper_table2_rsa2048_reference_rows#ccz_factories=<n>` when resolved (mirrors mega/wall keys). |
| `rsa_2048_reported_megaqubit_days_key` | Same logical ref as physical qubits key when megaqubit-days are present. |
| `reported_rsa2048_megaqubit_days` | `megaqubit_days` field from the matched Table 2 row. |
| `rsa_2048_reported_wall_clock_days_key` | Same logical ref as physical qubits key when wall-clock days are present. |
| `reported_rsa2048_wall_clock_days` | `wall_clock_days` field from the matched Table 2 row. |
| `naive_serial_time_days_from_depth_times_cycle` | `abstract_measurement_depth_layers × surface_code_cycle_time` (µs) converted to days; `null` if inputs missing. **Not** the paper’s scheduled wall time. |
| `code_distance_d` | Resolved distance used for patch evaluation (mirror of `qec_overhead...distance_d`). |
| `qec_distance_resolution_mode` | Short string from `qec_distance_resolution.mode`. |
| `derived_non_data_overhead_physical_qubits` | When Table 2 total qubits and data-plane proxy exist: `reported_total − approximate_data_plane` (remainder lumped: factories, routing, etc.). |
| `factory_footprint_physical_qubits_from_yaml` | `ccz_factory_count × physical_qubits_per_ccz_factory_approximate` when the magic YAML parameter is present. |
| `schedule_model_v1_wall_clock_days` | Heuristic parallel-depth schedule (see `timing.schedule_model_v1`). |
| `schedule_calibration_ratio_table2_over_model_v1` | Pinned Table 2 wall-clock divided by `schedule_model_v1` days when both exist (highlights model mismatch). |

## `qec_distance_resolution`

| Key | Type | Description |
|-----|------|-------------|
| `mode` | `string` | `cli_override` \| `explicit_scenario` \| `heuristic_union_bound` \| `unset` \| failure modes (`heuristic_failed_*`). |
| `distance_d` | `number \| null` | Resolved `d` when available. |
| `heuristic` | `object` | Present for `heuristic_union_bound`; includes `scan_rows` when using discrete scan, plus `closed_form_distance_d` for comparison. |
| `logical_error_budget` | `number` | Budget passed into the heuristic when applicable. |
| `distance_optimizer` | `string` | `discrete_scan` or `closed_form` (which engine selected `d`). |

## `layout_estimate`

| Key | Description |
|-----|-------------|
| `approximate_data_plane_physical_qubits` | Same idea as `dashboard.approximate_data_plane_physical_qubits`. |
| `reported_end_to_end_physical_qubits` | Table 2 pinned millions × `1e6` when available. |
| `derived_non_data_overhead_physical_qubits` | `max(0, reported_end_to_end − data_plane)` when both exist. |
| `factory_footprint_physical_qubits_from_yaml` | Optional explicit factory footprint from magic YAML. |
| `physical_qubits_per_ccz_factory_approximate_key` | Name of the magic YAML key when used. |
| `provenance` | `layout_proxy_v1`. |

## `layout_optimization`

Present when patch formula, logical qubits, measurement depth, and physical gate error are available (unless `qec.emit_layout_optimization: false`).

| Key | Type | Description |
|-----|------|-------------|
| `summary` | `object` | `objective` (`minimize_odd_code_distance_subject_to_union_bound`), `selected_code_distance_d`, `selected_row`, counts, `best_fit_distance_d_by_reported_total_residual` (among budget-satisfying `d`, minimizes \|data+factories − reported total\| when inputs exist). |
| `candidates` | `array \| null` | Full scan table when `qec.emit_optimization_trace: true`; otherwise `null`. Each row: `distance_d`, `union_bound_mass`, `satisfies_budget`, optional patch/data-plane/total/residual fields. |

## `timing`

| Key | Type | Description |
|-----|------|-------------|
| `reported_table2_pinned` | `object \| null` | When CCZ count is inferred from `table2_reference_row`: `physical_qubits_millions`, `megaqubit_days`, `wall_clock_days`, logical `*_key` refs (`paper_table2_rsa2048_reference_rows#ccz_factories=…`), `source_parameter`, `layout_descriptor`. `provenance`: `pinned_in_magic_yaml_table2`. |
| `naive_serial_from_measurement_depth` | `object \| null` | When evaluated abstract measurement depth and modality `surface_code_cycle_time` exist: `abstract_measurement_depth_layers`, `surface_code_cycle_time_microseconds`, `serial_time_microseconds`, `serial_time_days`, `source_parameters`, `provenance`: `computed_from_measurement_depth_times_surface_cycle`. |
| `schedule_model_v1` | `object \| null` | `parallel_depth_over_ccz_paths_v1`: `depth × effective_layer_time / max(1, ccz_count)` with `effective_layer_time = max(cycle, reaction)` when reaction-limited. Includes `reaction_limited_inferred_from`. |
| `schedule_calibration` | `object \| null` | Ratios comparing naive serial vs model and Table 2 pinned wall-clock vs model (`ratio_table2_pinned_over_model_v1`). |

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
- `timing.naive_serial_from_measurement_depth` is **not** comparable to Table 2 wall-clock; it ignores parallelism, reaction vs distillation limits, and magic-state scheduling.
- `qec_distance_resolution` **heuristic_union_bound** is a phenomenological proxy, **not** the paper-specific distance optimizer in Gidney & Ekerå (2021).
- `timing.schedule_model_v1` is a coarse bound (depth scaling ÷ factory count); use pinned Table 2 wall-clock for regression against the paper.
- `layout_estimate.derived_non_data_overhead_physical_qubits` is a residual (total minus naive data plane), not a decomposed factory layout.
- `layout_optimization` is a **tabular scan** over `d`, not a placement or routing optimizer.
- No endorsement of feasibility; warnings highlight missing inputs, naive products, and branch cuts (e.g. T-factory fallback).

## Contract history

| `report_contract_version` | Summary |
|---------------------------|---------|
| `1` | Initial report envelope (no `timing.schedule_model_v1`, `layout_estimate`, or heuristic `d`). |
| `2` | Adds `qec_distance_resolution`, `layout_estimate`, extended `timing`, and heuristic distance policy. |
| `3` | Consolidated magic Table 2 (`paper_table2_rsa2048_reference_rows`) and algorithm Table 1 pins (`paper_table1_pins_by_modulus_bit_length`); dashboard adds `table2_pinned_source_parameter` / `table2_pinned_row_layout_descriptor`; `ccz_factory_parameter_key` is now the row’s `layout_descriptor`. |
| `4` | Optional scenario `paths.qcvv` / `paths.qem`; `sources` and `layers` include `qcvv` and `qem` (or `null`) as separate stacks from `qcvv_qem`. |
