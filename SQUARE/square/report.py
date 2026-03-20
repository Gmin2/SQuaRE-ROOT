"""
Build structured reports from a :class:`~square.loader.ScenarioBundle`.

Output shape is documented in ``docs/output-contract.md`` (``report_contract_version``).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Mapping

from square.formula_eval import FormulaEvalError, eval_numeric_formula, eval_numeric_formula_with_bindings
from square.loader import ScenarioBundle
from square.qec_distance_heuristic import suggest_surface_code_distance_union_bound
from square.schedule_heuristic import build_parallel_depth_schedule_v1, infer_reaction_limited_from_scenario

_REPORT_CONTRACT_VERSION = 2

_HEADER_KEYS = frozenset(
    {
        "document_id",
        "schema_version",
        "primary_reference",
        "doi",
        "arxiv",
        "date_issued",
        "notes",
    }
)

_FORMULA_METRICS: tuple[tuple[str, str], ...] = (
    ("abstract_logical_qubits_formula", "abstract_logical_qubits"),
    ("abstract_measurement_depth_formula", "abstract_measurement_depth_layers"),
    ("abstract_toffoli_plus_t_halves_count_formula", "abstract_toffoli_plus_t_halves_count"),
)

_PINNED_SUFFIX_RE = re.compile(r"_n_(\d+)$")
_CCZ_ROW_RE = re.compile(r"_(\d+)_ccz\b")


def _is_parameter_entry(obj: Any) -> bool:
    return isinstance(obj, dict) and "value" in obj and "unit" in obj


def _split_document(doc: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    header: dict[str, Any] = {}
    parameters: dict[str, Any] = {}
    for key, val in doc.items():
        sk = str(key)
        if sk in _HEADER_KEYS:
            header[sk] = val
        elif _is_parameter_entry(val):
            parameters[sk] = val
        else:
            header[sk] = val
    return header, parameters


def _source_header(doc: Mapping[str, Any]) -> dict[str, Any]:
    return {k: doc[k] for k in _HEADER_KEYS if k in doc}


def _scenario_public_dict(scenario: Mapping[str, Any]) -> dict[str, Any]:
    return dict(scenario)


def _parse_ccz_count_from_table2(row_value: Any) -> int | None:
    if row_value is None:
        return None
    text = str(row_value)
    m = _CCZ_ROW_RE.search(text)
    return int(m.group(1)) if m else None


def _pinned_algorithm_entries_for_n(algorithm: Mapping[str, Any], n: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in algorithm.items():
        if key in _HEADER_KEYS or not isinstance(val, dict):
            continue
        m = _PINNED_SUFFIX_RE.search(str(key))
        if m and int(m.group(1)) == n:
            out[str(key)] = val
    return out


def _find_ccz_factory_parameter_key(magic: Mapping[str, Any], ccz: int) -> str | None:
    for key, val in magic.items():
        if not str(key).startswith("ccz_factory_count"):
            continue
        if isinstance(val, dict) and val.get("value") == ccz:
            return str(key)
    return None


def _magic_float_by_key(magic: Mapping[str, Any], key: str) -> float | None:
    entry = magic.get(key)
    if not isinstance(entry, dict) or entry.get("value") is None:
        return None
    try:
        return float(entry["value"])
    except (TypeError, ValueError):
        return None


def _engine_version() -> str:
    try:
        from importlib.metadata import version

        return version("square")
    except Exception:
        return "0.0.1"


def _parse_code_distance(
    scenario: Mapping[str, Any],
    *,
    override: int | None,
) -> tuple[int | None, list[str]]:
    """
    Resolve surface-code distance ``d`` from CLI override, then scenario YAML.

    Supported scenario shapes: top-level ``qec_code_distance: <int>``, or ``qec: { code_distance: <int> }``.
    """
    local_warnings: list[str] = []
    if override is not None:
        try:
            d_ov = int(override)
        except (TypeError, ValueError):
            local_warnings.append("code_distance override is not an integer; ignoring.")
            d_ov = None
        if d_ov is not None and d_ov <= 0:
            local_warnings.append("code_distance override must be positive; ignoring.")
            d_ov = None
        if d_ov is not None:
            return d_ov, local_warnings

    raw: Any = scenario.get("qec_code_distance")
    if raw is None and isinstance(scenario.get("qec"), dict):
        raw = scenario["qec"].get("code_distance")

    if raw is None:
        return None, local_warnings

    try:
        d = int(raw)
    except (TypeError, ValueError):
        local_warnings.append("Scenario qec_code_distance / qec.code_distance is not an integer; ignoring.")
        return None, local_warnings
    if d <= 0:
        local_warnings.append("Scenario code distance must be positive; ignoring.")
        return None, local_warnings
    return d, local_warnings


def _param_entry_float(entry: Any, default: float) -> float:
    if isinstance(entry, dict) and entry.get("value") is not None:
        try:
            return float(entry["value"])
        except (TypeError, ValueError):
            return default
    return default


def _resolve_code_distance_full(
    scenario: Mapping[str, Any],
    *,
    override: int | None,
    modality: Mapping[str, Any],
    qec: Mapping[str, Any],
    evaluated: Mapping[str, Any],
    warnings: list[str],
) -> tuple[int | None, dict[str, Any]]:
    """
    CLI override, explicit scenario distance, or heuristic (when ``qec.distance_policy`` requests it).
    """
    meta: dict[str, Any] = {"mode": "unset"}

    if override is not None:
        d, w = _parse_code_distance(scenario, override=override)
        warnings.extend(w)
        meta.update({"mode": "cli_override", "distance_d": d, "from_cli_override": True})
        return d, meta

    d_explicit, w = _parse_code_distance(scenario, override=None)
    warnings.extend(w)
    if d_explicit is not None:
        meta.update({"mode": "explicit_scenario", "distance_d": d_explicit, "explicit_in_scenario": True})
        return d_explicit, meta

    qec_block = scenario.get("qec") if isinstance(scenario.get("qec"), dict) else {}
    policy_raw = qec_block.get("distance_policy") or qec_block.get("distance_mode")
    policy = str(policy_raw).strip().lower() if policy_raw is not None else ""
    heuristic_aliases = frozenset({"heuristic_union_bound", "optimize_heuristic", "heuristic"})
    if policy not in heuristic_aliases:
        meta["distance_d"] = None
        return None, meta

    gate_entry = modality.get("characteristic_physical_gate_error_rate")
    p: float | None = None
    if isinstance(gate_entry, dict) and gate_entry.get("value") is not None:
        try:
            p = float(gate_entry["value"])
        except (TypeError, ValueError):
            p = None
    if p is None:
        warnings.append(
            "qec.distance_policy requests a heuristic but modality characteristic_physical_gate_error_rate "
            "is missing or non-numeric; distance d not computed."
        )
        meta.update({"mode": "heuristic_failed_missing_p", "distance_d": None})
        return None, meta

    abs_lq = evaluated.get("abstract_logical_qubits")
    depth_l = evaluated.get("abstract_measurement_depth_layers")
    lq_val: float | None = None
    dp_val: float | None = None
    if isinstance(abs_lq, dict) and abs_lq.get("value") is not None:
        try:
            lq_val = float(abs_lq["value"])
        except (TypeError, ValueError):
            lq_val = None
    if isinstance(depth_l, dict) and depth_l.get("value") is not None:
        try:
            dp_val = float(depth_l["value"])
        except (TypeError, ValueError):
            dp_val = None
    if lq_val is None or dp_val is None:
        warnings.append(
            "Heuristic distance skipped: need evaluated abstract_logical_qubits and abstract_measurement_depth_layers."
        )
        meta.update({"mode": "heuristic_failed_missing_formulas", "distance_d": None})
        return None, meta

    budget_raw = qec_block.get("logical_error_budget", 0.1)
    try:
        budget_f = float(budget_raw)
    except (TypeError, ValueError):
        budget_f = 0.1
        warnings.append("qec.logical_error_budget invalid; using 0.1.")

    p_th = _param_entry_float(qec.get("heuristic_surface_code_physical_threshold_order_of_magnitude"), 0.01)
    pref = _param_entry_float(qec.get("heuristic_logical_error_prefactor"), 0.05)
    min_d = int(_param_entry_float(qec.get("heuristic_distance_min_d"), 5))
    max_d = int(_param_entry_float(qec.get("heuristic_distance_max_d"), 55))

    d, hmeta = suggest_surface_code_distance_union_bound(
        physical_gate_error_rate=p,
        logical_qubit_count=lq_val,
        qec_cycle_count_proxy=dp_val,
        logical_error_budget=budget_f,
        phenomenological_p_th=p_th,
        phenomenological_prefactor=pref,
        min_d=min_d,
        max_d=max_d,
    )
    warnings.append(
        "code distance d from heuristic_union_bound (phenomenological model), "
        "not the paper-specific optimizer in Gidney & Ekerå 2021."
    )
    meta.update(
        {
            "mode": "heuristic_union_bound",
            "distance_d": d,
            "heuristic": hmeta,
            "logical_error_budget": budget_f,
        }
    )
    return d, meta


def build_scenario_report(
    bundle: ScenarioBundle,
    *,
    modulus_bits_override: int | None = None,
    code_distance_override: int | None = None,
) -> dict[str, Any]:
    """
    Assemble a JSON-serializable report dict for the given bundle.

    :param bundle: Loaded scenario documents.
    :param modulus_bits_override: If set, use this ``n`` instead of ``target.modulus_bit_length``.
    :param code_distance_override: If set, use this QEC distance ``d`` instead of scenario fields.
    """
    warnings: list[str] = []
    scenario = bundle.scenario
    target = scenario.get("target") if isinstance(scenario.get("target"), dict) else {}
    n_raw = modulus_bits_override if modulus_bits_override is not None else target.get("modulus_bit_length")
    n: int | None
    if n_raw is None:
        n = None
        warnings.append("No modulus_bit_length in scenario target (and no override); formula metrics skipped.")
    else:
        try:
            n = int(n_raw)
        except (TypeError, ValueError):
            n = None
            warnings.append("modulus_bit_length is not an integer; formula metrics skipped.")
        if n is not None and n <= 0:
            n = None
            warnings.append("modulus_bit_length must be positive; formula metrics skipped.")

    algo = bundle.algorithm
    evaluated: dict[str, Any] = {}
    evaluated_skipped: list[str] = []

    if n is not None:
        for src_key, out_key in _FORMULA_METRICS:
            entry = algo.get(src_key)
            if not isinstance(entry, dict):
                evaluated_skipped.append(src_key)
                continue
            raw = entry.get("value")
            if not isinstance(raw, str):
                evaluated_skipped.append(src_key)
                continue
            if "O(" in raw or "O(1)" in raw:
                evaluated_skipped.append(src_key)
                continue
            try:
                value = eval_numeric_formula(raw, float(n))
            except (FormulaEvalError, ZeroDivisionError, OverflowError) as exc:
                warnings.append(f"Could not evaluate {src_key!r}: {exc}")
                evaluated_skipped.append(src_key)
                continue
            evaluated[out_key] = {
                "value": value,
                "source_parameter": src_key,
                "provenance": "computed_from_yaml_formula",
            }

    exp = algo.get("exponent_register_qubits_ne_asymptotic")
    if isinstance(exp, dict) and isinstance(exp.get("value"), str) and "O(" in str(exp["value"]):
        evaluated_skipped.append("exponent_register_qubits_ne_asymptotic")

    pinned = _pinned_algorithm_entries_for_n(algo, n) if n is not None else {}

    d_resolved, qec_distance_resolution = _resolve_code_distance_full(
        scenario,
        override=code_distance_override,
        modality=bundle.modality,
        qec=bundle.qec,
        evaluated=evaluated,
        warnings=warnings,
    )

    patch_entry = bundle.qec.get("logical_qubit_patch_physical_qubit_count_formula")
    patch_formula: str | None = None
    if isinstance(patch_entry, dict) and isinstance(patch_entry.get("value"), str):
        patch_formula = str(patch_entry["value"])

    patch_physical_per_logical: float | None = None
    qec_patch_status = "no_formula_in_profile"
    qec_patch_eval_meta: dict[str, Any] | None = None

    if patch_formula:
        if d_resolved is None:
            qec_patch_status = "pending_distance_d"
            warnings.append(
                "Surface-code patch formula is present but code distance d is not set "
                "(use scenario qec_code_distance, qec.distance_policy heuristic, or --d); "
                "physical qubits per logical are not computed."
            )
        else:
            try:
                patch_physical_per_logical = eval_numeric_formula_with_bindings(
                    patch_formula, {"d": float(d_resolved)}
                )
                qec_patch_status = "evaluated"
                qec_patch_eval_meta = {
                    "provenance": "computed_from_yaml_formula",
                    "source_parameter": "logical_qubit_patch_physical_qubit_count_formula",
                }
            except (FormulaEvalError, ZeroDivisionError, OverflowError) as exc:
                qec_patch_status = "eval_failed"
                warnings.append(f"Could not evaluate QEC patch formula: {exc}")

    table2_block = scenario.get("table2_reference_row")
    ccz_count = None
    if isinstance(table2_block, dict):
        ccz_count = _parse_ccz_count_from_table2(table2_block.get("value"))
    if ccz_count is None and isinstance(table2_block, str):
        ccz_count = _parse_ccz_count_from_table2(table2_block)

    rsa2048_phys: float | None = None
    phys_key: str | None = None
    rsa2048_megaqd: float | None = None
    mega_key: str | None = None
    rsa2048_wall_days: float | None = None
    wall_key: str | None = None
    factory_param_key: str | None = None
    if ccz_count is not None:
        phys_key = f"rsa_2048_reported_physical_qubits_millions_{ccz_count}_ccz"
        phys_entry = bundle.magic.get(phys_key)
        if isinstance(phys_entry, dict) and phys_entry.get("value") is not None:
            try:
                rsa2048_phys = float(phys_entry["value"])
            except (TypeError, ValueError):
                rsa2048_phys = None
                warnings.append(f"Magic YAML key {phys_key!r} has a non-numeric value.")
        else:
            warnings.append(
                f"No magic YAML entry {phys_key!r} for inferred CCZ count {ccz_count}; "
                "dashboard physical qubit headline omitted."
            )

        mega_key = f"rsa_2048_reported_megaqubit_days_{ccz_count}_ccz"
        rsa2048_megaqd = _magic_float_by_key(bundle.magic, mega_key)
        if rsa2048_megaqd is None:
            warnings.append(
                f"No magic YAML entry {mega_key!r} for inferred CCZ count {ccz_count}; "
                "Table 2 megaqubit-days pin omitted."
            )

        wall_key = f"rsa_2048_reported_wall_clock_days_{ccz_count}_ccz"
        rsa2048_wall_days = _magic_float_by_key(bundle.magic, wall_key)
        if rsa2048_wall_days is None:
            warnings.append(
                f"No magic YAML entry {wall_key!r} for inferred CCZ count {ccz_count}; "
                "Table 2 wall-clock days pin omitted."
            )

        factory_param_key = _find_ccz_factory_parameter_key(bundle.magic, ccz_count)
        if factory_param_key is None:
            warnings.append(f"No ccz_factory_count* row in magic YAML matches count {ccz_count}.")
    elif table2_block is not None:
        warnings.append("Could not parse CCZ factory count from table2_reference_row.value.")

    toffoli_b = None
    megaqd = None
    if n is not None:
        tb = algo.get(f"toffoli_plus_t_halves_count_billions_n_{n}")
        if isinstance(tb, dict) and tb.get("value") is not None:
            try:
                toffoli_b = float(tb["value"])
            except (TypeError, ValueError):
                pass
        mq = algo.get(f"minimum_spacetime_volume_megaqubitdays_n_{n}")
        if isinstance(mq, dict) and mq.get("value") is not None:
            try:
                megaqd = float(mq["value"])
            except (TypeError, ValueError):
                pass

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

    modality_h, modality_p = _split_document(bundle.modality)
    qec_h, qec_p = _split_document(bundle.qec)
    magic_h, magic_p = _split_document(bundle.magic)
    algo_h, algo_p = _split_document(algo)

    magic_aux_layer = None
    if bundle.magic_aux is not None:
        mx_h, mx_p = _split_document(bundle.magic_aux)
        magic_aux_layer = {"header": mx_h, "parameters": mx_p}

    logical_qubits_val: float | None = None
    abs_lq = evaluated.get("abstract_logical_qubits")
    if isinstance(abs_lq, dict) and abs_lq.get("value") is not None:
        try:
            logical_qubits_val = float(abs_lq["value"])
        except (TypeError, ValueError):
            logical_qubits_val = None

    approx_data_physical: float | None = None
    if logical_qubits_val is not None and patch_physical_per_logical is not None:
        approx_data_physical = logical_qubits_val * patch_physical_per_logical
        warnings.append(
            "approximate_data_plane_physical_qubits = abstract_logical_qubits × physical_qubits_per_logical; "
            "excludes magic-state factories, routing, classical control footprint, and other non-data overhead."
        )

    reported_total_physical_qubits: float | None = None
    if rsa2048_phys is not None:
        reported_total_physical_qubits = float(rsa2048_phys) * 1e6

    derived_non_data_overhead_physical_qubits: float | None = None
    if reported_total_physical_qubits is not None and approx_data_physical is not None:
        derived_non_data_overhead_physical_qubits = max(0.0, reported_total_physical_qubits - approx_data_physical)
        warnings.append(
            "derived_non_data_overhead_physical_qubits = Table-2-pinned total qubits minus naive data-plane product; "
            "attributes remainder to factories, routing, distillation, control, etc. without splitting them."
        )

    per_ccz_factory_qubits = _magic_float_by_key(bundle.magic, "physical_qubits_per_ccz_factory_approximate")
    factory_footprint_from_yaml: float | None = None
    if ccz_count is not None and per_ccz_factory_qubits is not None:
        factory_footprint_from_yaml = float(ccz_count) * float(per_ccz_factory_qubits)

    layout_estimate: dict[str, Any] = {
        "approximate_data_plane_physical_qubits": approx_data_physical,
        "reported_end_to_end_physical_qubits": reported_total_physical_qubits,
        "derived_non_data_overhead_physical_qubits": derived_non_data_overhead_physical_qubits,
        "factory_footprint_physical_qubits_from_yaml": factory_footprint_from_yaml,
        "physical_qubits_per_ccz_factory_approximate_key": "physical_qubits_per_ccz_factory_approximate"
        if per_ccz_factory_qubits is not None
        else None,
        "provenance": "layout_proxy_v1",
    }

    naive_serial_timing: dict[str, Any] | None = None
    depth_layers = evaluated.get("abstract_measurement_depth_layers")
    cycle_entry = bundle.modality.get("surface_code_cycle_time")
    if isinstance(depth_layers, dict) and depth_layers.get("value") is not None:
        try:
            depth_val = float(depth_layers["value"])
        except (TypeError, ValueError):
            depth_val = None
        if depth_val is not None and isinstance(cycle_entry, dict) and cycle_entry.get("value") is not None:
            try:
                cycle_us = float(cycle_entry["value"])
            except (TypeError, ValueError):
                cycle_us = None
            if cycle_us is not None:
                serial_us = depth_val * cycle_us
                serial_days = serial_us / (1e6 * 86400.0)
                naive_serial_timing = {
                    "abstract_measurement_depth_layers": depth_val,
                    "surface_code_cycle_time_microseconds": cycle_us,
                    "serial_time_microseconds": serial_us,
                    "serial_time_days": serial_days,
                    "provenance": "computed_from_measurement_depth_times_surface_cycle",
                    "source_parameters": {
                        "depth": "abstract_measurement_depth_formula",
                        "cycle": "surface_code_cycle_time",
                    },
                }
                warnings.append(
                    "naive_serial_time_days = abstract_measurement_depth_layers × surface_code_cycle_time; "
                    "assumes one code cycle per abstract layer, no parallelism, no reaction/distillation limits — "
                    "not comparable to Table 2 wall-clock without the paper’s full schedule."
                )

    table2_row_text: str | None = None
    if isinstance(table2_block, dict) and table2_block.get("value") is not None:
        table2_row_text = str(table2_block.get("value"))
    schedule_model_v1: dict[str, Any] | None = None
    schedule_calibration: dict[str, Any] | None = None
    reaction_entry = bundle.modality.get("classical_control_reaction_time")
    reaction_us: float | None = None
    if isinstance(reaction_entry, dict) and reaction_entry.get("value") is not None:
        try:
            reaction_us = float(reaction_entry["value"])
        except (TypeError, ValueError):
            reaction_us = None

    if (
        isinstance(depth_layers, dict)
        and depth_layers.get("value") is not None
        and isinstance(cycle_entry, dict)
        and cycle_entry.get("value") is not None
        and reaction_us is not None
        and ccz_count is not None
    ):
        try:
            depth_val_s = float(depth_layers["value"])
            cycle_us_s = float(cycle_entry["value"])
        except (TypeError, ValueError):
            depth_val_s = None
            cycle_us_s = None
        if depth_val_s is not None and cycle_us_s is not None:
            rlim, rsrc = infer_reaction_limited_from_scenario(
                scenario,
                table2_row_value=table2_row_text,
                factory_parameter_key=factory_param_key,
            )
            schedule_model_v1 = build_parallel_depth_schedule_v1(
                abstract_measurement_depth_layers=depth_val_s,
                surface_code_cycle_microseconds=cycle_us_s,
                classical_reaction_microseconds=reaction_us,
                ccz_factory_count=int(ccz_count),
                reaction_limited=rlim,
            )
            schedule_model_v1["reaction_limited_inferred_from"] = rsrc
            warnings.append(
                "schedule_model_v1 uses depth/(CCZ factories) with an effective layer time; "
                "it is a coarse bound, not the paper’s compiled schedule."
            )
            if naive_serial_timing and naive_serial_timing.get("serial_time_days") is not None:
                naive_d = float(naive_serial_timing["serial_time_days"])
                model_d = float(schedule_model_v1["wall_clock_days"])
                schedule_calibration = {
                    "naive_serial_time_days": naive_d,
                    "schedule_model_v1_wall_clock_days": model_d,
                    "ratio_naive_serial_over_model_v1": naive_d / model_d if model_d > 0 else None,
                    "provenance": "ratio_of_estimates",
                }
            if rsa2048_wall_days is not None and schedule_model_v1.get("wall_clock_days") is not None:
                pinned_d = float(rsa2048_wall_days)
                model_d2 = float(schedule_model_v1["wall_clock_days"])
                schedule_calibration = schedule_calibration or {}
                schedule_calibration.update(
                    {
                        "table2_pinned_wall_clock_days": pinned_d,
                        "ratio_table2_pinned_over_model_v1": pinned_d / model_d2 if model_d2 > 0 else None,
                    }
                )

    reported_table2_timing: dict[str, Any] | None = None
    if ccz_count is not None:
        reported_table2_timing = {
            "ccz_factory_count": ccz_count,
            "physical_qubits_millions": rsa2048_phys,
            "physical_qubits_millions_key": phys_key,
            "megaqubit_days": rsa2048_megaqd,
            "megaqubit_days_key": mega_key if rsa2048_megaqd is not None else None,
            "wall_clock_days": rsa2048_wall_days,
            "wall_clock_days_key": wall_key if rsa2048_wall_days is not None else None,
            "provenance": "pinned_in_magic_yaml_table2",
        }

    timing_block: dict[str, Any] = {
        "reported_table2_pinned": reported_table2_timing,
        "naive_serial_from_measurement_depth": naive_serial_timing,
        "schedule_model_v1": schedule_model_v1,
        "schedule_calibration": schedule_calibration,
    }

    physical_rollup: dict[str, Any] = {
        "code_distance_d": d_resolved,
        "physical_qubits_per_logical": patch_physical_per_logical,
        "abstract_logical_qubits_at_n": logical_qubits_val,
        "approximate_data_plane_physical_qubits": approx_data_physical,
        "patch_formula_status": qec_patch_status,
    }

    report: dict[str, Any] = {
        "report_contract_version": _REPORT_CONTRACT_VERSION,
        "engine": {"name": "square", "version": _engine_version()},
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "warnings": warnings,
        "scenario": _scenario_public_dict(scenario),
        "target": dict(target) if isinstance(target, dict) else {},
        "table2_reference": table2_block if isinstance(table2_block, dict) else None,
        "sources": {
            "modality": _source_header(bundle.modality),
            "qec": _source_header(bundle.qec),
            "magic": _source_header(bundle.magic),
            "algorithm": _source_header(algo),
            "magic_aux": _source_header(bundle.magic_aux) if bundle.magic_aux else None,
        },
        "layers": {
            "modality": {"document_id": modality_h.get("document_id"), "header": modality_h, "parameters": modality_p},
            "qec": {"document_id": qec_h.get("document_id"), "header": qec_h, "parameters": qec_p},
            "magic": {"document_id": magic_h.get("document_id"), "header": magic_h, "parameters": magic_p},
            "magic_aux": magic_aux_layer,
            "algorithm": {"document_id": algo_h.get("document_id"), "header": algo_h, "parameters": algo_p},
        },
        "algorithm_metrics": {
            "n": n,
            "evaluated": evaluated,
            "evaluated_skipped": evaluated_skipped,
            "pinned_in_algorithm_yaml": pinned,
        },
        "qec_overhead": {
            "logical_qubit_patch_physical_qubit_count": {
                "formula": patch_formula,
                "distance_d": d_resolved,
                "physical_qubits_per_logical": patch_physical_per_logical,
                "status": qec_patch_status,
                **(qec_patch_eval_meta or {}),
            }
        },
        "physical_rollup": physical_rollup,
        "qec_distance_resolution": qec_distance_resolution,
        "layout_estimate": layout_estimate,
        "timing": timing_block,
        "dashboard": {
            "ccz_factory_count": ccz_count,
            "ccz_factory_parameter_key": factory_param_key,
            "rsa_2048_reported_physical_qubits_millions_key": phys_key,
            "reported_rsa2048_physical_qubits_millions": rsa2048_phys,
            "rsa_2048_reported_megaqubit_days_key": mega_key,
            "reported_rsa2048_megaqubit_days": rsa2048_megaqd,
            "rsa_2048_reported_wall_clock_days_key": wall_key,
            "reported_rsa2048_wall_clock_days": rsa2048_wall_days,
            "naive_serial_time_days_from_depth_times_cycle": naive_serial_timing["serial_time_days"]
            if naive_serial_timing
            else None,
            "logical_qubits_at_n": evaluated.get("abstract_logical_qubits", {}).get("value")
            if isinstance(evaluated.get("abstract_logical_qubits"), dict)
            else None,
            "toffoli_plus_t_halves_billions_at_n": toffoli_b,
            "minimum_spacetime_volume_megaqubitdays_at_n": megaqd,
            "logical_qubit_physical_qubits_if_distance_d": patch_physical_per_logical,
            "approximate_data_plane_physical_qubits": approx_data_physical,
            "t_factory_fallback_recommended": t_fallback_recommended,
            "t_factory_transition_modulus_bits_order_of_magnitude": t_transition,
            "code_distance_d": d_resolved,
            "qec_distance_resolution_mode": qec_distance_resolution.get("mode"),
            "derived_non_data_overhead_physical_qubits": derived_non_data_overhead_physical_qubits,
            "factory_footprint_physical_qubits_from_yaml": factory_footprint_from_yaml,
            "schedule_model_v1_wall_clock_days": schedule_model_v1.get("wall_clock_days")
            if schedule_model_v1
            else None,
            "schedule_calibration_ratio_table2_over_model_v1": schedule_calibration.get(
                "ratio_table2_pinned_over_model_v1"
            )
            if schedule_calibration
            else None,
        },
    }

    return report


def report_to_markdown(report: Mapping[str, Any]) -> str:
    """
    Render a short Markdown summary of a report (JSON remains canonical).

    :param report: Output of :func:`build_scenario_report`.
    """
    lines: list[str] = []
    lines.append("# SQuaRE scenario report\n")
    eng = report.get("engine", {})
    lines.append(
        f"**Contract** v{report.get('report_contract_version')} · **Engine** {eng.get('name')} {eng.get('version')}\n"
    )
    lines.append(f"**Generated** {report.get('generated_at')}\n")
    scen = report.get("scenario", {})
    lines.append(f"**Scenario** `{scen.get('scenario')}` (schema {scen.get('schema_version')})\n")

    tgt = report.get("target", {})
    if tgt:
        lines.append(f"**Target** modulus bits **{tgt.get('modulus_bit_length')}**, problem `{tgt.get('problem')}`\n")

    dash = report.get("dashboard", {})
    lines.append("## Headlines\n")
    lines.append(f"- **n (evaluation):** {report.get('algorithm_metrics', {}).get('n')}\n")
    lines.append(f"- **Abstract logical qubits (evaluated):** {dash.get('logical_qubits_at_n')}\n")
    lines.append(f"- **CCZ factories (from scenario row):** {dash.get('ccz_factory_count')}\n")
    lines.append(f"- **Reported RSA-2048 physical qubits (M):** {dash.get('reported_rsa2048_physical_qubits_millions')}\n")
    lines.append(f"- **Toffoli+T/2 (billions) at n:** {dash.get('toffoli_plus_t_halves_billions_at_n')}\n")
    lines.append(f"- **Min. spacetime volume (megaqubit-days) at n:** {dash.get('minimum_spacetime_volume_megaqubitdays_at_n')}\n")
    lines.append(
        f"- **Table 2 pinned (RSA-2048, inferred CCZ): megaqubit-days:** {dash.get('reported_rsa2048_megaqubit_days')}, "
        f"**wall-clock days:** {dash.get('reported_rsa2048_wall_clock_days')}\n"
    )
    lines.append(
        f"- **Naive serial time (depth × surface cycle, not Table 2 wall-clock):** "
        f"{dash.get('naive_serial_time_days_from_depth_times_cycle')} days\n"
    )
    lines.append(f"- **Code distance d (resolved):** {dash.get('code_distance_d')} (`{dash.get('qec_distance_resolution_mode')}`)\n")
    lines.append(f"- **Physical qubits / logical (at d):** {dash.get('logical_qubit_physical_qubits_if_distance_d')}\n")
    lines.append(f"- **Approx. data-plane physical qubits (logical × patch):** {dash.get('approximate_data_plane_physical_qubits')}\n")
    lines.append(
        f"- **Derived non-data overhead (pinned total − data plane):** {dash.get('derived_non_data_overhead_physical_qubits')}\n"
    )
    lines.append(
        f"- **Factory footprint from YAML (count × per-factory):** {dash.get('factory_footprint_physical_qubits_from_yaml')}\n"
    )
    lines.append(f"- **Schedule model v1 wall-clock (days):** {dash.get('schedule_model_v1_wall_clock_days')}\n")
    lines.append(
        f"- **Table2 / schedule_model_v1 ratio:** {dash.get('schedule_calibration_ratio_table2_over_model_v1')}\n"
    )
    lines.append(f"- **T-factory fallback flagged:** {dash.get('t_factory_fallback_recommended')}\n")

    warns = report.get("warnings") or []
    if warns:
        lines.append("\n## Warnings\n")
        for w in warns:
            lines.append(f"- {w}\n")

    lines.append("\n## Sources (document_id)\n")
    src = report.get("sources", {})
    for layer, block in src.items():
        if isinstance(block, dict) and block.get("document_id"):
            lines.append(f"- **{layer}:** `{block.get('document_id')}`\n")

    lines.append("\n*Full detail: emit JSON (`square-report` without `--markdown`).*\n")
    return "".join(lines)
