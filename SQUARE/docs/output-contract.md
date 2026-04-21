# SQuaRE report output contract

This document defines the **machine-readable report** produced after loading a scenario bundle (`ScenarioBundle`). Tooling and UIs should treat `report_contract_version` as the compatibility anchor.

## Versioning

| Field | Meaning |
|-------|---------|
| `report_contract_version` | Integer. Bump when top-level keys or semantics change in a breaking way. |
| `schema_version` (inside `scenario`) | Assumptions / scenario YAML version from `Assumptions/Schemas.yaml`. |

## Internal: Monte Carlo metrics slice (`outputs="mc_metrics"`)

Monte Carlo (`square-mc`) calls `build_scenario_report(..., outputs="mc_metrics")` when it only needs default forward-model metrics. The implementation still runs formula evaluation, distance resolution, patch/rollup, timing, and dashboard assembly for each evaluation; the slice only **drops** later sections from the returned dict. That path returns a **non-contract** object containing exactly:

| Key | Purpose |
|-----|---------|
| `dashboard` | Same shape as the full report’s `dashboard` (headline fields for MC extraction). |
| `algorithm_metrics` | Same shape as the full report’s `algorithm_metrics` (including optional `ecdlp` when applicable). |

It omits layout optimization, logical fault model, system metrics, parameter sensitivity, sources/layers assembly, and other full-report sections. Tooling must not treat this object as a full `report_contract_version` document. If `extract_default_mc_metrics` (or equivalent) gains new dependencies, update this slice and its tests together. Regression: `tests/test_report.py` → `test_build_scenario_report_mc_metrics_slice_matches_full_for_mc_extract`.

## Top-level envelope

Every report is a JSON-serializable object with at least:

| Key | Type | Description |
|-----|------|-------------|
| `report_contract_version` | `number` | Contract version (currently `15`). |
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
| `logical_fault_model` | `object` | Phenomenological **logical error per QEC cycle** and **logical cycle time** proxy (OSRE-style); see § `logical_fault_model`. |
| `physical_rollup` | `object` | End-to-end **data-plane** physical qubit roll-up when both `n` and `d` are available; see below. |
| `physical_layer` | `object` | Curated **native physical** parameters (OSRE memo alignment) copied from modality YAML; see § `physical_layer`. |
| `system_metrics` | `object` | OSRE-style **LQC / LOB / QOT** (and related); see § `system_metrics`. Metrics are filled when inputs exist (`computed` / `partial`); otherwise `insufficient_inputs` with explanatory `notes`. |
| `parameter_sensitivity` | `object` | Local finite-difference sensitivities (heuristic ``d``, naive serial time); see § `parameter_sensitivity`. |
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
| `n` | `number \| null` | Modulus bit length for RSA-style scenarios (`target.modulus_bit_length` or override). **`null`** for fixed-problem ECDLP profiles (algorithm `document_id` in the ECDLP set), which do not use `n`. |
| `evaluated` | `object` | Per-metric objects when the YAML formula is a **closed-form expression in `n`** using `+ - * / // % **` and `log2(...)`. Each value is `{ "value": number, "source_parameter": string, "provenance": "computed_from_yaml_formula" }`. For ECDLP, entries use `provenance: "ecdlp_envelope_fixed_problem"` and populate `abstract_logical_qubits` and `abstract_measurement_depth_layers` (Toffoli-derived depth proxy). |
| `evaluated_skipped` | `array` | Parameter keys not evaluated (e.g. strings containing `O(1)`). |
| `pinned_in_algorithm_yaml` | `object` | Map of parameter key → entry for paper-pinned values at specific `n`. May include synthetic keys (e.g. `toffoli_plus_t_halves_count_billions_n_<n>`) resolved from a consolidated `paper_table1_pins_by_modulus_bit_length` block when present. |
| `ecdlp` | `object \| omitted` | Present when the algorithm is a fixed-problem ECDLP document. Includes `variant`, `logical_qubits_upper_bound`, `toffoli_gates_upper_bound`, `ecdlp_measurement_depth_layers_per_toffoli_gate`, `abstract_measurement_depth_layers_proxy`, `depth_proxy_rule`, and optional `paper_headline_physical_qubits_upper_bound_narrative`. |

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
| `logical_failure_probability_union_depth_proxy` | `min(1, D × p_L)` when ``D`` = evaluated ``abstract_measurement_depth_layers.value`` and ``p_L`` = ``logical_fault_model.logical_error_rate_per_cycle`` (phenomenological). Union-style **proxy** for cumulative logical failure risk; `null` if either input is missing or ``p_L`` is omitted (e.g. ``p_phys ≥ p_th``). Not a decoder-accurate fault simulation. |
| `code_distance_d` | Resolved distance used for patch evaluation (mirror of `qec_overhead...distance_d`). |
| `qec_distance_resolution_mode` | Short string from `qec_distance_resolution.mode`. |
| `derived_non_data_overhead_physical_qubits` | When Table 2 total qubits and data-plane proxy exist: `reported_total − approximate_data_plane` (remainder lumped: factories, routing, etc.). |
| `factory_footprint_physical_qubits_from_yaml` | `ccz_factory_count × physical_qubits_per_ccz_factory_approximate` when the magic YAML parameter is present. |
| `schedule_model_v1_wall_clock_days` | Heuristic parallel-depth schedule (see `timing.schedule_model_v1`). |
| `schedule_calibration_ratio_table2_over_model_v1` | Pinned Table 2 wall-clock divided by `schedule_model_v1` days when both exist (highlights model mismatch). |
| `magic_supply_adequate` | `true` / `false` / `null`. When magic YAML supplies `ccz_factory_supply_abstract_measurement_depth_layers_per_second_per_factory` and timing + CCZ width exist: compares demand proxy `D/T` (evaluated depth over wall-clock seconds from `timing.schedule_model_v1.wall_clock_days` if present, else `timing.naive_serial_from_measurement_depth.serial_time_days`) to supply proxy `N_ccz × R` (`N_ccz` from Table-2-inferred count or `schedule_model_v1.ccz_factory_count`). `null` when skipped (missing inputs or absent rate); see `warnings`. |
| `magic_limited_runtime_multiplier` | `number` / `null`. When the check runs and supply is below demand: `min(1e6, demand/supply)` (notional wall-clock scale vs this proxy); `1.0` when adequate; `null` when the check is skipped. Does **not** rewrite `timing` blocks. |
| `ecdlp_active` | `true` when the scenario uses an ECDLP algorithm profile; otherwise omitted. |
| `ecdlp_variant` | Named envelope key (e.g. `low_toffoli_variant`) when ECDLP mode is active. |
| `ecdlp_toffoli_gates_upper_bound` | Upper bound from the algorithm YAML envelope when ECDLP mode is active. |
| `ecdlp_paper_headline_physical_qubits_upper_bound` | Narrative physical-qubit headline from the algorithm YAML when present. |

## `qec_distance_resolution`

| Key | Type | Description |
|-----|------|-------------|
| `mode` | `string` | `cli_override` \| `explicit_scenario` \| `heuristic_union_bound` \| `unset` \| failure modes (`heuristic_failed_*`). |
| `distance_d` | `number \| null` | Resolved `d` when available. |
| `heuristic` | `object` | Present for `heuristic_union_bound`; includes `scan_rows` when using discrete scan, plus `closed_form_distance_d` for comparison. |
| `logical_error_budget` | `number` | Budget passed into the heuristic when applicable. |
| `distance_optimizer` | `string` | `discrete_scan` or `closed_form` (which engine selected `d`). |
| `physical_gate_error_rate_effective` | `number \| null` | When ``mode`` is ``heuristic_union_bound``, the **effective** physical gate error used in the union bound (nominal × QCVV × scaling penalty); otherwise often omitted. |

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

## `logical_fault_model`

Phenomenological **logical error rate per QEC cycle** and a **logical cycle time** estimate aligned with the OSRE memo (logical error scaling; τ_cycle as max of available timing components).

| Key | Type | Description |
|-----|------|-------------|
| `schema` | `string` | `logical_fault_model_v1`. |
| `status` | `string` | `computed` when both per-cycle logical error and cycle time are available; `partial` if only one; `insufficient_inputs` if neither. |
| `logical_error_rate_per_cycle` | `number \| null` | `A·(p_phys/p_th)^ceil((d+1)/2)` via ``square.qec_distance_heuristic.phenomenological_logical_error_per_cycle`` when `d` and effective physical gate error exist and `p_phys < p_th`. **`p_phys`** is **`p_effective`** = **``p_nominal`` × QCVV σ × scaling penalty** when those factors are configured (see `inputs`); **`null`** if `p_phys ≥ p_th` or inputs missing. |
| `logical_error_model` | `string` | Model id (`phenomenological_prefactor_times_p_over_pth_to_half_distance`). |
| `exponent_half_distance` | `number \| null` | Integer `(d+1)//2` used in the exponent when `logical_error_rate_per_cycle` is computed. |
| `inputs` | `object` | Includes `code_distance_d`, `physical_gate_error_rate` (same as **`p_effective`**, the rate passed into the phenomenological model), **`physical_gate_error_rate_nominal`** (always the modality headline **`characteristic_physical_gate_error_rate`** for Table-2-style traceability, even when the heuristic uses a different base), optional stack keys **`p_nominal`** (base rate before σ and penalty: ``max(1Q,2Q)`` when both extended gate rates are usable, else one extended rate, else characteristic), **`p_nominal_gate_proxy_method`** (`max_1q_2q` \| `single_1q_only` \| `two_2q_only` \| `characteristic_fallback`), **`characteristic_physical_gate_error_rate`** (headline characteristic value for comparison), **`ver_grounded_on_characteristic_only`** (`true` when **VER** uses headline characteristic × σ regardless of heuristic ``p_nominal``), plus **VER/scaling** keys (`qcvv_multiplier_sigma`, `scaling_penalty_*`, `scaling_reference_physical_qubits`, `p_effective`), and heuristic QEC parameters. |

**Nominal vs characteristic:** ``p_nominal`` drives heuristic distance and ``p_effective``. ``physical_gate_error_rate_nominal`` in this block remains the **headline** ``characteristic_physical_gate_error_rate`` from modality YAML. **``system_metrics.validated_error_rate_ver``** (VER) continues to use **characteristic × σ** when `paths.qcvv` is set, not ``p_nominal``.
| `logical_cycle_time` | `object` | `logical_cycle_time_microseconds`: **`max`** of available components; `components_microseconds` lists each; `provenance` describes the aggregation rule. |

**Components for `logical_cycle_time_microseconds`:** modality `surface_code_cycle_time`, `classical_control_reaction_time`, and optional QEC YAML `parameter_entry` keys `qec_decode_latency_microseconds`, `qec_measurement_round_time_microseconds` (positive values only). Not a full compiled schedule.

## `physical_layer` (OSRE native physical)

Curated passthrough of **extended** modality parameters (T1/T2, native gate and readout errors, idle proxy, correlated-noise multiplier, leakage proxy, plus optional memo-aligned richness slots) that follow the OSRE memo’s physical-layer checklist. Only keys listed below are copied from `layers.modality.parameters`; the full modality map remains authoritative.

| Key | Type | Description |
|-----|------|-------------|
| `schema` | `string` | Sub-schema tag (currently `physical_layer_v1`). |
| `document_id` | `string \| null` | Modality `document_id` for traceability. |
| `status` | `string` | `passthrough_from_modality` when at least one extended key is present; otherwise `no_extended_keys_in_profile`. |
| `notes` | `array` of `string` | Fixed transparency strings (e.g. optional richness keys are **not** used in heuristic `p_effective` / distance in this version). |
| `parameter_keys` | `array` | Sorted list of keys included in `parameters`. |
| `parameters` | `object` | Map of parameter name → full YAML `parameter_entry` (same shape as under `layers.modality.parameters`). |

**Canonical key set** (required in bundled modality YAML; when present they are copied): `coherence_time_t1_microseconds`, `coherence_time_t2_microseconds`, `single_qubit_gate_error_rate`, `two_qubit_gate_error_rate`, `measurement_error_rate`, `idle_error_rate_per_cycle`, `correlated_noise_parameter`, `leakage_error_rate`.

**Optional richness key set** (copied when present; transparency / future modeling only in v14): `fabrication_variability_proxy`, `thermal_load_index_proxy`, `control_plane_saturation_proxy`.

## `system_metrics` (OSRE-aligned)

**System-level** quantities aligned with the OSRE Product Requirements Memorandum (LQC, LOB, QOT, headroom, VER, mitigated ceiling). **Contract v8+** (`system_metrics_v2`) fills **LQC**, **LOB**, **headroom**, and **QOT**; **v9+** adds **VER** / **mitigated_operations_ceiling** from optional `paths.qcvv` / `paths.qem`; **v10** ties **LOB** to QEM suppression on ``p_L`` and **mitigated_operations_ceiling** to sampling overhead only (see field table). Formulas are **proxies** (see `notes`).

### Scenario inputs

Optional block **`scenario.system_metrics`** (when present on the scenario YAML merged into `report.scenario`):

| Key | Type | Description |
|-----|------|-------------|
| `routing_margin_logical_qubits` | `number` | Non-negative logical slots subtracted from the LQC proxy (default `0`). |

### Block fields

| Key | Type | Description |
|-----|------|-------------|
| `schema` | `string` | Sub-schema tag (currently `system_metrics_v2`). |
| `status` | `string` | `computed` if LQC, LOB, and QOT are all non-`null`; `partial` if at least one is non-`null`; `insufficient_inputs` if all three are `null`. |
| `notes` | `array` of `string` | Caveats: missing inputs per metric and model limits. |
| `logical_qubit_capacity_lqc` | `number \| null` | **LQC** proxy: `floor(max(0, P_total/ρ − F/ρ − margin))` when `P_total` (`layout_estimate.reported_end_to_end_physical_qubits`), factory footprint `F` (`layout_estimate.factory_footprint_physical_qubits_from_yaml`), and per-logical patch size `ρ` (`physical_qubits_per_logical`) are all valid; else `null`. |
| `logical_qubit_capacity_lqc_method` | `string \| null` | Short formula id when LQC is computed; otherwise `null`. |
| `logical_operations_budget_lob` | `number \| null` | **LOB** proxy: `ε / (p_L × s_QEM)` with `qec.logical_error_budget` as ε, phenomenological `p_L` from `logical_fault_model`, and QEM `effective_logical_error_rate_suppression_factor` as `s_QEM` (`1` when no QEM path). |
| `headroom_logical_depth` | `number \| null` | `LOB − D` when both LOB and `abstract_measurement_depth_layers` exist; else `null`. |
| `quantum_operations_throughput_qot` | `number \| null` | **QOT** proxy: `parallel_width / τ` (abstract layer-proxies per second), with `τ` = `logical_fault_model.logical_cycle_time.logical_cycle_time_microseconds` × 10⁻⁶ s, and `parallel_width` = `max(1, timing.schedule_model_v1.ccz_factory_count)` when the schedule block exists, else `max(1, ccz_factory_count)` from Table 2 row, else `1`. |
| `validated_error_rate_ver` | `number \| null` | **VER** (QCVV-grounded proxy): `p_nominal × σ` when `paths.qcvv` is set, modality supplies `characteristic_physical_gate_error_rate`, and QCVV supplies `effective_physical_error_rate_multiplier_from_characterization` (`σ` > 0). Else `null`. Heuristic ``d`` and `logical_fault_model` use **effective** physical error (VER × scaling penalty on QEC YAML). |
| `mitigated_operations_ceiling` | `number \| null` | **QEM sampling proxy**: `LOB / Γ` when `paths.qem` is set and LOB exists, with `sampling_shot_overhead_multiplier` as `Γ` (suppression `s` is already in LOB). Else `null`. |

**Consumers:** Treat nullable metrics as **absent** when `null`. Prefer JSON over Markdown summaries; `report_to_markdown` surfaces headline LQC/LOB/QOT lines when present.

## `parameter_sensitivity`

Local **symmetric relative finite-difference** sensitivities (OSRE memo style) for a few headline knobs. Emitted when ``qec.emit_parameter_sensitivity`` is not ``false`` and the distance policy produced ``heuristic_union_bound`` with resolved ``d`` and effective gate error.

| Key | Type | Description |
|-----|------|-------------|
| `schema` | `string` | `parameter_sensitivity_v1`. |
| `status` | `string` | `computed` \| `skipped` \| `insufficient_inputs`. |
| `method` | `string \| null` | e.g. `symmetric_relative_finite_difference`. |
| `relative_perturbation` | `number \| null` | Relative step on parameters (implementation default `1e-5`). |
| `rows` | `array` | Each row: `parameter`, `layer`, `metric`, `baseline_parameter_value`, `baseline_metric_value`, optional `derivative_metric_per_parameter`, optional `elasticity_metric_times_parameter_over_value`. |
| `ranking_by_abs_derivative_code_distance_d` | `array` | Parameter names sorted by \|∂(code_distance_d)/∂param\| when that derivative exists. |
| `notes` | `array` of `string` | Model limits (discrete ``d``, secant between perturbed optima, etc.). |

**QEC YAML (optional) for scaling + opt-out:**

| Key | Type | Description |
|-----|------|-------------|
| `heuristic_scaling_penalty_log_coefficient` | `parameter_entry` | Coefficient ``α`` in ``1 + α log N + β N`` applied to **nominal** gate error after QCVV (``N`` = Table-2 total physical qubits when pinned, else evaluated logical width proxy). Default ``0``. |
| `heuristic_scaling_penalty_linear_coefficient` | `parameter_entry` | Coefficient ``β`` in the same penalty. Default ``0``. |
| `emit_parameter_sensitivity` | `boolean` | If ``false``, ``parameter_sensitivity.status`` is ``skipped``. |

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
- `parameter_sensitivity` uses **discrete** heuristic distances; derivatives are secants and can be zero across flat regions.
- No endorsement of feasibility; warnings highlight missing inputs, naive products, and branch cuts (e.g. T-factory fallback).

## Contract history

| `report_contract_version` | Summary |
|---------------------------|---------|
| `1` | Initial report envelope (no `timing.schedule_model_v1`, `layout_estimate`, or heuristic `d`). |
| `2` | Adds `qec_distance_resolution`, `layout_estimate`, extended `timing`, and heuristic distance policy. |
| `3` | Consolidated magic Table 2 (`paper_table2_rsa2048_reference_rows`) and algorithm Table 1 pins (`paper_table1_pins_by_modulus_bit_length`); dashboard adds `table2_pinned_source_parameter` / `table2_pinned_row_layout_descriptor`; `ccz_factory_parameter_key` is now the row’s `layout_descriptor`. |
| `4` | Optional scenario `paths.qcvv` / `paths.qem`; `sources` and `layers` include `qcvv` and `qem` (or `null`) as separate stacks from `qcvv_qem`. |
| `5` | Adds top-level `system_metrics` (OSRE LQC/LOB/QOT slots); prior to **v8**, metric fields were **`null`** with `status: not_computed` until roll-ups landed. |
| `6` | Adds top-level `physical_layer` — curated passthrough of OSRE extended native physical parameters from modality YAML (`passthrough_from_modality` or `no_extended_keys_in_profile`). |
| `7` | Adds `logical_fault_model`: phenomenological logical error per cycle + logical cycle time as max(modality cycle/reaction, optional QEC decode/measurement latencies). |
| `8` | `system_metrics` → **`system_metrics_v2`**: computed **LQC** (pinned total + YAML factory footprint + patch ρ), **LOB** / **headroom** (ε/p_L vs measurement depth), **QOT** (parallel width / τ); `notes` as `array`; optional `scenario.system_metrics.routing_margin_logical_qubits` for LQC. |
| `9` | `system_metrics`: **VER** from QCVV × modality gate error when `paths.qcvv` is present; **mitigated_operations_ceiling** from QEM suppression and sampling multipliers when `paths.qem` is present (see § `system_metrics`). |
| `10` | **Effective physical error stack** (QCVV × optional QEC scaling penalty on ``N``) drives heuristic ``d``, `logical_fault_model`, and `layout_optimization`; **LOB** includes QEM ``s`` on ``p_L``; **mitigated_operations_ceiling** = LOB/Γ; top-level **`parameter_sensitivity`** (finite differences); optional `qec.emit_parameter_sensitivity: false` to skip. |
| `11` | **Modality nominal gate proxy for heuristics:** ``p_nominal`` = ``max(single_qubit_gate_error_rate, two_qubit_gate_error_rate)`` when both OSRE extended rates are usable; else a single extended rate with a warning; else ``characteristic_physical_gate_error_rate`` with a fallback warning. ``p_effective = p_nominal × σ × (penalty)`` unchanged. ``logical_fault_model.inputs`` gains ``p_nominal``, ``p_nominal_gate_proxy_method``, and ``characteristic_physical_gate_error_rate`` from the stack. **VER** still uses headline characteristic × σ. |
| `12` | **Shorter proxy method IDs** (`max_1q_2q`, `single_1q_only`, `two_2q_only`, `characteristic_fallback`). Adds ``ver_grounded_on_characteristic_only: true`` under ``logical_fault_model.inputs``. **Monte Carlo** ``PARAMETER_LAYERS`` includes ``single_qubit_gate_error_rate`` and ``two_qubit_gate_error_rate`` so ``square-mc`` can vary the same rates the heuristic uses for ``p_nominal``. |
| `13` | **Dashboard** adds ``logical_failure_probability_union_depth_proxy`` = ``min(1, D×p_L)`` (depth proxy × phenomenological ``p_L``). **Monte Carlo** default metric slice includes this key when present. |
| `14` | **``physical_layer``** adds fixed ``notes`` and passthrough of optional OSRE richness keys (``fabrication_variability_proxy``, ``thermal_load_index_proxy``, ``control_plane_saturation_proxy``) when present in modality YAML; they do **not** feed heuristic ``p_effective`` or distance in this version. |
| `15` | **Dashboard** adds optional magic throughput proxies: ``magic_supply_adequate`` and ``magic_limited_runtime_multiplier`` when magic YAML includes ``ccz_factory_supply_abstract_measurement_depth_layers_per_second_per_factory`` and CCZ width + honest timing exist; otherwise ``null`` with explanatory ``warnings``. **Monte Carlo** default metric slice includes ``magic_limited_runtime_multiplier`` when present. |
