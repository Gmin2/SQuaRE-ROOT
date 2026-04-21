"""
Build structured reports from a :class:`~square.loader.ScenarioBundle`.

Output shape is documented in ``docs/output-contract.md`` (``report_contract_version``).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, Literal

from square.heuristic_union_inputs import read_heuristic_union_bound_inputs
from square.layout_optimization import (
    build_layout_distance_candidates,
    summarize_layout_optimization,
)
from square.loader import ScenarioBundle
from square.qec_distance_heuristic import (
    phenomenological_logical_error_per_cycle,
    suggest_union_bound_code_distance,
)
from square.report_assembly import assemble_report_shell
from square.report_dashboard import build_dashboard_fields
from square.report_distance import resolve_code_distance_full
from square.report_formula_pins import (
    TABLE2_RSA2048_ROWS_KEY,
    build_formula_evaluation_and_pins,
    parse_table2_pins_early,
    table1_pin_row,
)
from square.report_layers import build_report_sources_and_layers
from square.report_markdown import report_to_markdown
from square.report_physical_layout import build_physical_rollup_and_layout_estimate
from square.report_qec_patch import evaluate_patch_physical_per_logical
from square.report_system_metrics import build_system_metrics_block
from square.report_timing import build_timing_section
from square.yaml_numeric import (
    read_evaluated_metric_float,
    read_modality_characteristic_gate_error,
    read_parameter_entry_float,
    read_parameter_entry_float_default,
    read_positive_parameter_microseconds,
)

_REPORT_CONTRACT_VERSION = 10

# Curated modality keys surfaced under top-level ``physical_layer`` (OSRE native physical layer).
OSRE_EXTENDED_PHYSICAL_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "coherence_time_t1_microseconds",
        "coherence_time_t2_microseconds",
        "single_qubit_gate_error_rate",
        "two_qubit_gate_error_rate",
        "measurement_error_rate",
        "idle_error_rate_per_cycle",
        "correlated_noise_parameter",
        "leakage_error_rate",
    }
)


def _build_physical_layer_snapshot(
    modality_parameters: Mapping[str, Any],
    *,
    document_id: Any,
) -> dict[str, Any]:
    """
    Passthrough of extended physical parameters from modality YAML into a stable report envelope.

    Full modality parameters remain under ``layers.modality.parameters``; this block duplicates only
    OSRE-aligned keys for tooling. See ``docs/output-contract.md`` § ``physical_layer``.
    """
    picked: dict[str, Any] = {}
    for key in OSRE_EXTENDED_PHYSICAL_PARAMETER_KEYS:
        entry = modality_parameters.get(key)
        if isinstance(entry, dict):
            picked[key] = entry
    doc_raw = document_id
    doc_id: str | None = (
        str(doc_raw).strip()
        if doc_raw is not None and str(doc_raw).strip()
        else None
    )
    status = "passthrough_from_modality" if picked else "no_extended_keys_in_profile"
    return {
        "schema": "physical_layer_v1",
        "document_id": doc_id,
        "status": status,
        "parameter_keys": sorted(picked.keys()),
        "parameters": picked,
    }


def _scaling_reference_physical_qubits(
    rsa_phys_millions: float | None,
    evaluated: Mapping[str, Any],
    warnings: list[str],
) -> float:
    """
    Device-size proxy ``N`` for OSRE-style scaling penalty ``1 + α log N + β N``.

    Prefers Table-2 pinned end-to-end physical qubits when available; otherwise falls back to
    evaluated ``abstract_logical_qubits`` (weak proxy, documented in sensitivity notes).
    """
    if rsa_phys_millions is not None:
        return max(1.0, float(rsa_phys_millions) * 1e6)
    v = read_evaluated_metric_float(
        evaluated,
        "abstract_logical_qubits",
        warnings,
        context="scaling_reference_physical_qubits",
    )
    if v is not None:
        return max(1.0, v)
    return 1.0


def _effective_physical_gate_error_stack(
    *,
    modality: Mapping[str, Any],
    qcvv_doc: Mapping[str, Any] | None,
    qec: Mapping[str, Any],
    rsa_phys_millions: float | None,
    evaluated: Mapping[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    """
    Nominal modality gate error, QCVV multiplier, scaling penalty, and effective ``p`` for heuristics.

    ``p_effective = p_nominal × σ_QCVV × (1 + α log N + β N)`` when ``p_nominal`` is defined; ``N`` is
    :func:`_scaling_reference_physical_qubits`. Coefficients ``α``, ``β`` default to ``0`` from QEC YAML
    ``heuristic_scaling_penalty_log_coefficient`` / ``heuristic_scaling_penalty_linear_coefficient``.
    """
    p_nominal = read_modality_characteristic_gate_error(modality, warnings, context="paths.modality")
    sigma = 1.0
    if qcvv_doc is not None:
        s_opt = read_parameter_entry_float(
            qcvv_doc,
            "effective_physical_error_rate_multiplier_from_characterization",
            warnings,
            context="paths.qcvv",
        )
        if s_opt is not None and s_opt > 0.0:
            sigma = float(s_opt)
        elif s_opt is not None:
            warnings.append("effective_physical_error_rate_multiplier_from_characterization <= 0; using 1.0.")

    alpha = read_parameter_entry_float_default(
        qec.get("heuristic_scaling_penalty_log_coefficient"),
        0.0,
        warnings,
        context="paths.qec",
        param_name="heuristic_scaling_penalty_log_coefficient",
    )
    beta = read_parameter_entry_float_default(
        qec.get("heuristic_scaling_penalty_linear_coefficient"),
        0.0,
        warnings,
        context="paths.qec",
        param_name="heuristic_scaling_penalty_linear_coefficient",
    )
    n_ref = _scaling_reference_physical_qubits(rsa_phys_millions, evaluated, warnings)
    penalty = 1.0 + alpha * math.log(n_ref) + beta * n_ref
    if penalty <= 0.0:
        warnings.append("Scaling penalty (1 + α log N + β N) <= 0; clamping to 1.0 for p_effective.")
        penalty = 1.0

    p_effective: float | None = None
    if p_nominal is not None:
        p_effective = float(p_nominal * sigma * penalty)
        if alpha != 0.0 or beta != 0.0:
            warnings.append(
                "physical_gate_error_rate_effective applies heuristic_scaling_penalty_* on QEC YAML; "
                "see parameter_sensitivity.scaling_reference_physical_qubits for N."
            )

    return {
        "p_nominal": p_nominal,
        "qcvv_multiplier_sigma": sigma,
        "scaling_penalty_log_coefficient_alpha": alpha,
        "scaling_penalty_linear_coefficient_beta": beta,
        "scaling_reference_physical_qubits": n_ref,
        "scaling_penalty_factor": penalty,
        "p_effective": p_effective,
    }


def _scenario_public_dict(scenario: Mapping[str, Any]) -> dict[str, Any]:
    return dict(scenario)


def _algorithm_metrics_block(
    *,
    n: int | None,
    evaluated: Mapping[str, Any],
    evaluated_skipped: list[str],
    pinned: Mapping[str, Any],
    ecdlp_block: dict[str, Any] | None,
) -> dict[str, Any]:
    """Assemble ``algorithm_metrics``; include ``ecdlp`` when in fixed-problem ECDLP mode."""
    out: dict[str, Any] = {
        "n": n,
        "evaluated": dict(evaluated),
        "evaluated_skipped": list(evaluated_skipped),
        "pinned_in_algorithm_yaml": dict(pinned),
    }
    if ecdlp_block is not None:
        out["ecdlp"] = ecdlp_block
    return out


def _build_layout_optimization_block(
    *,
    scenario: Mapping[str, Any],
    modality: Mapping[str, Any],
    qec: Mapping[str, Any],
    evaluated: Mapping[str, Any],
    patch_formula: str | None,
    logical_qubits: float | None,
    selected_d: int | None,
    reported_total_physical_qubits: float | None,
    factory_footprint_physical_qubits: float | None,
    warnings: list[str],
    physical_gate_error_rate_effective: float | None = None,
) -> dict[str, Any] | None:
    """
    Per-distance layout proxy: union-bound mass + patch formula → data-plane qubits (+ optional fit to reported total).
    """
    _raw_qec = scenario.get("qec")
    qec_block: dict[str, Any] = _raw_qec if isinstance(_raw_qec, dict) else {}
    if qec_block.get("emit_layout_optimization") is False:
        return None

    if patch_formula is None or logical_qubits is None or selected_d is None:
        return None

    p: float | None = physical_gate_error_rate_effective
    if p is None:
        p = read_modality_characteristic_gate_error(modality, warnings, context="paths.modality")

    dp_val = read_evaluated_metric_float(
        evaluated,
        "abstract_measurement_depth_layers",
        warnings,
        context="layout_optimization",
    )

    if p is None or dp_val is None:
        return None

    hu = read_heuristic_union_bound_inputs(
        qec, qec_block, warnings, budget_warning_context="layout_optimization"
    )

    candidates = build_layout_distance_candidates(
        patch_formula=patch_formula,
        logical_qubits=float(logical_qubits),
        physical_gate_error_rate=p,
        qec_cycle_count_proxy=dp_val,
        logical_error_budget=hu.logical_error_budget,
        phenomenological_p_th=hu.phenomenological_p_th,
        phenomenological_prefactor=hu.phenomenological_prefactor,
        min_d=hu.min_d,
        max_d=hu.max_d,
        reported_total_physical_qubits=reported_total_physical_qubits,
        factory_footprint_physical_qubits=factory_footprint_physical_qubits,
    )
    summary = summarize_layout_optimization(
        selected_d=int(selected_d),
        candidates=candidates,
        logical_error_budget=hu.logical_error_budget,
        patch_formula=patch_formula,
    )
    emit_trace = bool(qec_block.get("emit_optimization_trace", False))
    warnings.append(
        "layout_optimization scans patch scaling vs d; it is not a full device placement optimizer."
    )
    return {
        "summary": summary,
        "candidates": candidates if emit_trace else None,
    }


def _build_logical_fault_model_block(
    *,
    distance_d: int | None,
    modality: Mapping[str, Any],
    qec: Mapping[str, Any],
    warnings: list[str],
    physical_gate_error_rate_effective: float | None = None,
    physical_error_stack: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Phenomenological logical error per QEC cycle and logical-cycle-time proxy (OSRE memo).

    Logical error uses :func:`~square.qec_distance_heuristic.phenomenological_logical_error_per_cycle`
    (same as heuristic distance selection). Cycle time uses ``max`` of modality
    ``surface_code_cycle_time`` and ``classical_control_reaction_time``, plus optional QEC
    ``qec_decode_latency_microseconds`` and ``qec_measurement_round_time_microseconds`` when present.
    """

    p_phys: float | None = physical_gate_error_rate_effective
    if p_phys is None:
        p_phys = read_modality_characteristic_gate_error(modality, warnings, context="paths.modality")

    p_nominal_for_inputs = read_modality_characteristic_gate_error(modality, warnings, context="paths.modality")

    p_th = read_parameter_entry_float_default(
        qec.get("heuristic_surface_code_physical_threshold_order_of_magnitude"),
        0.01,
        warnings,
        context="paths.qec",
        param_name="heuristic_surface_code_physical_threshold_order_of_magnitude",
    )
    pref_a = read_parameter_entry_float_default(
        qec.get("heuristic_logical_error_prefactor"),
        0.05,
        warnings,
        context="paths.qec",
        param_name="heuristic_logical_error_prefactor",
    )

    pl: float | None = None
    exponent_half_distance: int | None = None
    if distance_d is not None and int(distance_d) > 0 and p_phys is not None:
        d_int = int(distance_d)
        exponent_half_distance = (d_int + 1) // 2
        if p_phys >= p_th:
            warnings.append(
                "logical_fault_model: characteristic_physical_gate_error_rate >= "
                "heuristic_surface_code_physical_threshold_order_of_magnitude; phenomenological "
                "logical_error_rate_per_cycle omitted (model assumes p_phys < p_th)."
            )
        else:
            pl = phenomenological_logical_error_per_cycle(
                d_int,
                physical_gate_error_rate=p_phys,
                phenomenological_p_th=p_th,
                phenomenological_prefactor=pref_a,
            )

    cycle_us = read_positive_parameter_microseconds(
        modality, "surface_code_cycle_time", warnings, context="paths.modality"
    )
    reaction_us = read_positive_parameter_microseconds(
        modality, "classical_control_reaction_time", warnings, context="paths.modality"
    )
    decode_us = read_positive_parameter_microseconds(
        qec, "qec_decode_latency_microseconds", warnings, context="paths.qec"
    )
    measure_us = read_positive_parameter_microseconds(
        qec, "qec_measurement_round_time_microseconds", warnings, context="paths.qec"
    )

    named_vals: list[tuple[str, float]] = []
    if cycle_us is not None:
        named_vals.append(("surface_code_cycle_time_microseconds", cycle_us))
    if reaction_us is not None:
        named_vals.append(("classical_control_reaction_time_microseconds", reaction_us))
    if decode_us is not None:
        named_vals.append(("qec_decode_latency_microseconds", decode_us))
    if measure_us is not None:
        named_vals.append(("qec_measurement_round_time_microseconds", measure_us))

    tau_us: float | None = None
    if named_vals:
        tau_us = max(v for _, v in named_vals)
        warnings.append(
            "logical_fault_model.logical_cycle_time_microseconds is max(available components); "
            "not a compiled schedule. Add qec_decode_latency_microseconds / "
            "qec_measurement_round_time_microseconds on QEC YAML when pinning OSRE τ_cycle pieces."
        )

    if pl is not None:
        warnings.append(
            "logical_fault_model.logical_error_rate_per_cycle is a phenomenological proxy "
            "A·(p/p_th)^ceil((d+1)/2), not a paper-calibrated logical channel."
        )

    if pl is not None and tau_us is not None:
        status = "computed"
    elif pl is not None or tau_us is not None:
        status = "partial"
    else:
        status = "insufficient_inputs"

    components_map: dict[str, float | None] = {
        "surface_code_cycle_time_microseconds": cycle_us,
        "classical_control_reaction_time_microseconds": reaction_us,
        "qec_decode_latency_microseconds": decode_us,
        "qec_measurement_round_time_microseconds": measure_us,
    }

    inputs: dict[str, Any] = {
        "code_distance_d": distance_d,
        "physical_gate_error_rate": p_phys,
        "physical_gate_error_rate_nominal": p_nominal_for_inputs,
        "heuristic_threshold_p_th": p_th,
        "heuristic_prefactor_a": pref_a,
    }
    if physical_error_stack is not None:
        for key in (
            "qcvv_multiplier_sigma",
            "scaling_penalty_log_coefficient_alpha",
            "scaling_penalty_linear_coefficient_beta",
            "scaling_reference_physical_qubits",
            "scaling_penalty_factor",
            "p_effective",
        ):
            if key in physical_error_stack:
                inputs[key] = physical_error_stack[key]

    return {
        "schema": "logical_fault_model_v1",
        "status": status,
        "logical_error_rate_per_cycle": pl,
        "logical_error_model": "phenomenological_prefactor_times_p_over_pth_to_half_distance",
        "exponent_half_distance": exponent_half_distance,
        "inputs": inputs,
        "logical_cycle_time": {
            "logical_cycle_time_microseconds": tau_us,
            "components_microseconds": components_map,
            "provenance": "max_of_available_modality_and_optional_qec_latency_v1",
        },
    }


_SENSITIVITY_REL_EPS = 1e-5


def _build_parameter_sensitivity_block(
    *,
    scenario: Mapping[str, Any],
    qec: Mapping[str, Any],
    evaluated: Mapping[str, Any],
    qec_distance_resolution: Mapping[str, Any],
    physical_stack: Mapping[str, Any],
    naive_serial_timing: Mapping[str, Any] | None,
    warnings: list[str],
) -> dict[str, Any]:
    """
    Local OSRE-style sensitivities: symmetric relative finite differences on heuristic ``d`` and naive serial time.

    Controlled by ``qec.emit_parameter_sensitivity`` (default: emit when inputs exist). Uses the same
    phenomenological union-bound driver as :func:`square.report_distance.resolve_code_distance_full`.
    """
    _raw = scenario.get("qec")
    qec_block: dict[str, Any] = _raw if isinstance(_raw, dict) else {}
    if qec_block.get("emit_parameter_sensitivity") is False:
        return {
            "schema": "parameter_sensitivity_v1",
            "status": "skipped",
            "method": None,
            "relative_perturbation": None,
            "rows": [],
            "notes": ["parameter_sensitivity skipped: qec.emit_parameter_sensitivity is false."],
        }

    mode = str(qec_distance_resolution.get("mode") or "")
    d0_any = qec_distance_resolution.get("distance_d")
    p0_raw = physical_stack.get("p_effective")
    if mode != "heuristic_union_bound" or d0_any is None or p0_raw is None:
        return {
            "schema": "parameter_sensitivity_v1",
            "status": "insufficient_inputs",
            "method": "symmetric_relative_finite_difference",
            "relative_perturbation": _SENSITIVITY_REL_EPS,
            "rows": [],
            "notes": [
                "Local sensitivity needs heuristic_union_bound with resolved distance_d and p_effective."
            ],
        }

    d0 = int(d0_any)
    p0 = float(p0_raw)

    lq_val = read_evaluated_metric_float(
        evaluated,
        "abstract_logical_qubits",
        warnings,
        context="parameter_sensitivity",
    )
    dp_val = read_evaluated_metric_float(
        evaluated,
        "abstract_measurement_depth_layers",
        warnings,
        context="parameter_sensitivity",
    )
    if lq_val is None or dp_val is None:
        return {
            "schema": "parameter_sensitivity_v1",
            "status": "insufficient_inputs",
            "method": "symmetric_relative_finite_difference",
            "relative_perturbation": _SENSITIVITY_REL_EPS,
            "rows": [],
            "notes": ["Local sensitivity needs evaluated abstract_logical_qubits and abstract_measurement_depth_layers."],
        }

    hu = read_heuristic_union_bound_inputs(
        qec, qec_block, warnings, budget_warning_context="parameter_sensitivity"
    )

    def _d_at(*, p_eff: float, p_th_use: float) -> int:
        d_out, _ = suggest_union_bound_code_distance(
            physical_gate_error_rate=p_eff,
            logical_qubit_count=lq_val,
            qec_cycle_count_proxy=dp_val,
            logical_error_budget=hu.logical_error_budget,
            phenomenological_p_th=p_th_use,
            phenomenological_prefactor=hu.phenomenological_prefactor,
            min_d=hu.min_d,
            max_d=hu.max_d,
            use_discrete_scan=hu.use_discrete_scan,
        )
        return int(d_out)

    eps = _SENSITIVITY_REL_EPS
    d_p_up = _d_at(p_eff=p0 * (1.0 + eps), p_th_use=hu.phenomenological_p_th)
    d_p_down = _d_at(p_eff=p0 / (1.0 + eps), p_th_use=hu.phenomenological_p_th)
    denom_p = 2.0 * p0 * eps
    d_distance_d_dphys = (float(d_p_up) - float(d_p_down)) / denom_p if denom_p > 0 else None

    d_th_up = _d_at(p_eff=p0, p_th_use=hu.phenomenological_p_th * (1.0 + eps))
    d_th_down = _d_at(p_eff=p0, p_th_use=hu.phenomenological_p_th / (1.0 + eps))
    denom_th = 2.0 * hu.phenomenological_p_th * eps
    d_distance_d_dpth = (float(d_th_up) - float(d_th_down)) / denom_th if denom_th > 0 else None

    rows: list[dict[str, Any]] = [
        {
            "parameter": "physical_gate_error_rate_effective",
            "layer": "derived",
            "metric": "code_distance_d",
            "baseline_parameter_value": p0,
            "baseline_metric_value": float(d0),
            "derivative_metric_per_parameter": d_distance_d_dphys,
            "elasticity_metric_times_parameter_over_value": (d_distance_d_dphys * p0 / float(d0))
            if (d_distance_d_dphys is not None and d0 != 0)
            else None,
        },
        {
            "parameter": "heuristic_surface_code_physical_threshold_order_of_magnitude",
            "layer": "qec",
            "metric": "code_distance_d",
            "baseline_parameter_value": hu.phenomenological_p_th,
            "baseline_metric_value": float(d0),
            "derivative_metric_per_parameter": d_distance_d_dpth,
            "elasticity_metric_times_parameter_over_value": (d_distance_d_dpth * hu.phenomenological_p_th / float(d0))
            if (d_distance_d_dpth is not None and d0 != 0)
            else None,
        },
    ]

    if naive_serial_timing is not None:
        dep = naive_serial_timing.get("abstract_measurement_depth_layers")
        cyc = naive_serial_timing.get("surface_code_cycle_time_microseconds")
        nsd = naive_serial_timing.get("serial_time_days")
        if dep is not None and cyc is not None and nsd is not None:
            try:
                dep_f = float(dep)
                cyc_f = float(cyc)
                d_serial_d_cycle = dep_f / (1e6 * 86400.0)
            except (TypeError, ValueError):
                d_serial_d_cycle = None
            if d_serial_d_cycle is not None:
                rows.append(
                    {
                        "parameter": "surface_code_cycle_time",
                        "layer": "modality",
                        "metric": "naive_serial_time_days",
                        "baseline_parameter_value": cyc_f,
                        "baseline_metric_value": float(nsd),
                        "derivative_metric_per_parameter": d_serial_d_cycle,
                        "elasticity_metric_times_parameter_over_value": d_serial_d_cycle * cyc_f / float(nsd)
                        if float(nsd) != 0
                        else None,
                    }
                )

    ranked = sorted(
        (r for r in rows if r.get("derivative_metric_per_parameter") is not None),
        key=lambda r: abs(float(r["derivative_metric_per_parameter"])),
        reverse=True,
    )
    ranking = [r["parameter"] for r in ranked]

    notes = [
        "Finite differences use relative step 1e-5 on effective gate error and threshold; "
        "code_distance_d is discrete so derivatives are secants between perturbed optima.",
        f"scaling_reference_physical_qubits for penalty: {physical_stack.get('scaling_reference_physical_qubits')}",
    ]
    warnings.append(
        "parameter_sensitivity: local finite differences are coarse proxies; use Monte Carlo for global uncertainty."
    )

    return {
        "schema": "parameter_sensitivity_v1",
        "status": "computed",
        "method": "symmetric_relative_finite_difference",
        "relative_perturbation": _SENSITIVITY_REL_EPS,
        "rows": rows,
        "ranking_by_abs_derivative_code_distance_d": ranking,
        "notes": notes,
    }


def build_scenario_report(
    bundle: ScenarioBundle,
    *,
    modulus_bits_override: int | None = None,
    code_distance_override: int | None = None,
    outputs: Literal["full", "mc_metrics"] = "full",
) -> dict[str, Any]:
    """
    Assemble a JSON-serializable report dict for the given bundle.

    :param bundle: Loaded scenario documents.
    :param modulus_bits_override: If set, use this ``n`` instead of ``target.modulus_bit_length``.
    :param code_distance_override: If set, use this QEC distance ``d`` instead of scenario fields.
    :param outputs: ``full`` (default) contract report; ``mc_metrics`` returns only keys required by
        :func:`square.mc.forward_model.extract_default_mc_metrics` (cheaper for Monte Carlo draws).
    """
    warnings: list[str] = []
    scenario = bundle.scenario
    table2_block = scenario.get("table2_reference_row")
    _raw_target = scenario.get("target")
    target: dict[str, Any] = _raw_target if isinstance(_raw_target, dict) else {}
    algo = bundle.algorithm

    fe = build_formula_evaluation_and_pins(
        algo,
        scenario,
        target,
        warnings,
        modulus_bits_override=modulus_bits_override,
    )
    evaluated = fe.evaluated
    evaluated_skipped = fe.evaluated_skipped
    n = fe.n
    ecdlp_block_for_metrics = fe.ecdlp_block_for_metrics
    pinned = fe.pinned

    early_pins, early_table2_warnings = parse_table2_pins_early(scenario, bundle.magic)
    warnings.extend(early_table2_warnings)
    physical_stack = _effective_physical_gate_error_stack(
        modality=bundle.modality,
        qcvv_doc=bundle.qcvv,
        qec=bundle.qec,
        rsa_phys_millions=early_pins.get("rsa2048_phys"),
        evaluated=evaluated,
        warnings=warnings,
    )
    p_effective_for_heuristic = physical_stack.get("p_effective")
    if p_effective_for_heuristic is not None:
        p_effective_for_heuristic = float(p_effective_for_heuristic)

    d_resolved, qec_distance_resolution = resolve_code_distance_full(
        scenario,
        override=code_distance_override,
        modality=bundle.modality,
        qec=bundle.qec,
        evaluated=evaluated,
        warnings=warnings,
        physical_gate_error_rate_effective=p_effective_for_heuristic,
    )

    patch_formula, patch_physical_per_logical, qec_patch_status, qec_patch_eval_meta = (
        evaluate_patch_physical_per_logical(bundle.qec, d_resolved, warnings)
    )

    ccz_count = early_pins["ccz_count"]
    rsa2048_phys = early_pins["rsa2048_phys"]
    phys_key = early_pins["phys_key"]
    rsa2048_megaqd = early_pins["rsa2048_megaqd"]
    mega_key = early_pins["mega_key"]
    rsa2048_wall_days = early_pins["rsa2048_wall_days"]
    wall_key = early_pins["wall_key"]
    factory_param_key = early_pins["factory_param_key"]
    table2_row_layout_descriptor = early_pins["table2_row_layout_descriptor"]

    toffoli_b = None
    megaqd = None
    if n is not None:
        t1 = table1_pin_row(algo, n)
        if t1 is not None:
            raw_tb = t1.get("toffoli_plus_t_halves_billions")
            if raw_tb is not None:
                try:
                    toffoli_b = float(raw_tb)
                except (TypeError, ValueError):
                    warnings.append(
                        f"paper_table1_pins: toffoli_plus_t_halves_billions for n={n} is not numeric; "
                        "dashboard toffoli_plus_t_halves_billions_at_n omitted."
                    )
            raw_mq = t1.get("minimum_spacetime_volume_megaqubit_days")
            if raw_mq is not None:
                try:
                    megaqd = float(raw_mq)
                except (TypeError, ValueError):
                    warnings.append(
                        f"paper_table1_pins: minimum_spacetime_volume_megaqubit_days for n={n} is not numeric; "
                        "dashboard minimum_spacetime_volume_megaqubitdays_at_n omitted."
                    )

    t_fallback_recommended = False
    t_transition: int | None = None
    if bundle.magic_aux:
        trans = bundle.magic_aux.get("modulus_bit_length_ccz_to_t_transition_order_of_magnitude")
        if isinstance(trans, dict) and trans.get("value") is not None:
            try:
                t_transition = int(trans["value"])
            except (TypeError, ValueError):
                t_transition = None
        if n is not None and t_transition is not None and n >= t_transition:
            t_fallback_recommended = True
            warnings.append(
                f"n={n} is at or above the documented CCZ→T factory transition scale (~{t_transition} bits); "
                "magic_aux flags a different non-Clifford supply model."
            )

    phys = build_physical_rollup_and_layout_estimate(
        magic=bundle.magic,
        evaluated=evaluated,
        early_pins=early_pins,
        d_resolved=d_resolved,
        patch_physical_per_logical=patch_physical_per_logical,
        qec_patch_status=qec_patch_status,
        warnings=warnings,
    )
    logical_qubits_val = phys.logical_qubits_val
    approx_data_physical = phys.approx_data_physical
    reported_total_physical_qubits = phys.reported_total_physical_qubits
    derived_non_data_overhead_physical_qubits = phys.derived_non_data_overhead_physical_qubits
    factory_footprint_from_yaml = phys.factory_footprint_from_yaml
    layout_estimate = phys.layout_estimate
    physical_rollup = phys.physical_rollup

    if outputs == "full":
        layout_optimization = _build_layout_optimization_block(
            scenario=scenario,
            modality=bundle.modality,
            qec=bundle.qec,
            evaluated=evaluated,
            patch_formula=patch_formula,
            logical_qubits=logical_qubits_val,
            selected_d=d_resolved,
            reported_total_physical_qubits=reported_total_physical_qubits,
            factory_footprint_physical_qubits=factory_footprint_from_yaml,
            warnings=warnings,
            physical_gate_error_rate_effective=p_effective_for_heuristic,
        )
    else:
        layout_optimization = None

    timing_out = build_timing_section(
        evaluated=evaluated,
        modality=bundle.modality,
        scenario=scenario,
        table2_block=table2_block,
        table2_rsa2048_rows_key=TABLE2_RSA2048_ROWS_KEY,
        ecdlp_block_for_metrics=ecdlp_block_for_metrics,
        early_pins=early_pins,
        warnings=warnings,
    )
    timing_block = timing_out.timing_block
    naive_serial_timing = timing_out.naive_serial_timing
    schedule_model_v1 = timing_out.schedule_model_v1
    schedule_calibration = timing_out.schedule_calibration

    algo_metrics = _algorithm_metrics_block(
        n=n,
        evaluated=evaluated,
        evaluated_skipped=evaluated_skipped,
        pinned=pinned,
        ecdlp_block=ecdlp_block_for_metrics,
    )

    dashboard = build_dashboard_fields(
        ccz_count=ccz_count,
        factory_param_key=factory_param_key,
        table2_pinned_source_parameter=TABLE2_RSA2048_ROWS_KEY if ccz_count is not None else None,
        table2_row_layout_descriptor=table2_row_layout_descriptor,
        phys_key=phys_key,
        rsa2048_phys=rsa2048_phys,
        mega_key=mega_key,
        rsa2048_megaqd=rsa2048_megaqd,
        wall_key=wall_key,
        rsa2048_wall_days=rsa2048_wall_days,
        naive_serial_timing=naive_serial_timing,
        evaluated=evaluated,
        toffoli_b=toffoli_b,
        megaqd=megaqd,
        patch_physical_per_logical=patch_physical_per_logical,
        approx_data_physical=approx_data_physical,
        t_fallback_recommended=t_fallback_recommended,
        t_transition=t_transition,
        d_resolved=d_resolved,
        qec_distance_resolution_mode=qec_distance_resolution.get("mode"),
        derived_non_data_overhead_physical_qubits=derived_non_data_overhead_physical_qubits,
        factory_footprint_from_yaml=factory_footprint_from_yaml,
        schedule_model_v1=schedule_model_v1,
        schedule_calibration=schedule_calibration,
        ecdlp_block_for_metrics=ecdlp_block_for_metrics,
    )

    if outputs == "mc_metrics":
        return {"dashboard": dashboard, "algorithm_metrics": algo_metrics}

    lfm = _build_logical_fault_model_block(
        distance_d=d_resolved,
        modality=bundle.modality,
        qec=bundle.qec,
        warnings=warnings,
        physical_gate_error_rate_effective=p_effective_for_heuristic,
        physical_error_stack=physical_stack,
    )
    system_metrics_block = build_system_metrics_block(
        scenario=scenario,
        modality=bundle.modality,
        qcvv_doc=bundle.qcvv,
        qem_doc=bundle.qem,
        reported_total_physical_qubits=reported_total_physical_qubits,
        factory_footprint_physical_qubits=factory_footprint_from_yaml,
        patch_physical_per_logical=patch_physical_per_logical,
        logical_fault_model=lfm,
        evaluated=evaluated,
        schedule_model_v1=schedule_model_v1,
        ccz_factory_count=ccz_count,
        warnings=warnings,
    )

    parameter_sensitivity_block = _build_parameter_sensitivity_block(
        scenario=scenario,
        qec=bundle.qec,
        evaluated=evaluated,
        qec_distance_resolution=qec_distance_resolution,
        physical_stack=physical_stack,
        naive_serial_timing=naive_serial_timing,
        warnings=warnings,
    )

    sl = build_report_sources_and_layers(bundle, algo)

    qec_overhead = {
        "logical_qubit_patch_physical_qubit_count": {
            "formula": patch_formula,
            "distance_d": d_resolved,
            "physical_qubits_per_logical": patch_physical_per_logical,
            "status": qec_patch_status,
            **(qec_patch_eval_meta or {}),
        }
    }

    return assemble_report_shell(
        report_contract_version=_REPORT_CONTRACT_VERSION,
        warnings=warnings,
        scenario=_scenario_public_dict(scenario),
        target=dict(target) if isinstance(target, dict) else {},
        table2_reference=table2_block if isinstance(table2_block, dict) else None,
        sources=sl.sources,
        layers=sl.layers,
        algorithm_metrics=algo_metrics,
        qec_overhead=qec_overhead,
        logical_fault_model=lfm,
        physical_rollup=physical_rollup,
        physical_layer=_build_physical_layer_snapshot(
            sl.modality_parameters,
            document_id=sl.modality_header.get("document_id"),
        ),
        system_metrics=system_metrics_block,
        parameter_sensitivity=parameter_sensitivity_block,
        qec_distance_resolution=qec_distance_resolution,
        layout_estimate=layout_estimate,
        layout_optimization=layout_optimization,
        timing=timing_block,
        dashboard=dashboard,
    )


__all__ = ["build_scenario_report", "report_to_markdown"]
