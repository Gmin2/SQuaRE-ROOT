"""
Build structured reports from a :class:`~square.loader.ScenarioBundle`.

Output shape is documented in ``docs/output-contract.md`` (``report_contract_version``).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from square.formula_eval import (
    FormulaEvalError,
    eval_numeric_formula,
    eval_numeric_formula_with_bindings,
)
from square.layout_optimization import (
    build_layout_distance_candidates,
    summarize_layout_optimization,
)
from square.loader import ScenarioBundle
from square.qec_distance_heuristic import suggest_surface_code_distance_union_bound
from square.schedule_heuristic import (
    build_parallel_depth_schedule_v1,
    infer_reaction_limited_from_scenario,
)

_REPORT_CONTRACT_VERSION = 5


def _build_system_metrics_placeholder() -> dict[str, Any]:
    """
    OSRE-style system metrics (LQC, LOB, QOT, headroom, VER, mitigation ceiling).

    Contract v5 reserves these keys; numeric composition is deferred to later phases.
    See ``docs/output-contract.md`` § ``system_metrics``.
    """
    return {
        "schema": "system_metrics_v1",
        "status": "not_computed",
        "notes": (
            "Placeholder for OSRE Product Requirements Memorandum metrics. "
            "Future releases will populate LQC/LOB/QOT from composed physical, QEC, magic, and algorithm layers."
        ),
        "logical_qubit_capacity_lqc": None,
        "logical_operations_budget_lob": None,
        "quantum_operations_throughput_qot": None,
        "headroom_logical_depth": None,
        "validated_error_rate_ver": None,
        "mitigated_operations_ceiling": None,
    }

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

_TABLE1_PINS_KEY = "paper_table1_pins_by_modulus_bit_length"
_TABLE2_RSA2048_ROWS_KEY = "paper_table2_rsa2048_reference_rows"

_ECDLP_DOCUMENT_IDS = frozenset({"ecdlp_secp256k1_babbush_et_al_2026"})
_ECDLP_ENVELOPE_KEY = "ecdlp_logical_resource_envelopes_secp256k1"


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


def _table1_pin_row(algo: Mapping[str, Any], n: int) -> dict[str, Any] | None:
    """Return the Table 1 pin sub-map for modulus bit length ``n`` when present."""
    entry = algo.get(_TABLE1_PINS_KEY)
    if not isinstance(entry, dict):
        return None
    raw_val = entry.get("value")
    if not isinstance(raw_val, dict):
        return None
    sub = raw_val.get(str(int(n)))
    return sub if isinstance(sub, dict) else None


def _table2_rsa2048_row_for_ccz(magic: Mapping[str, Any], ccz: int) -> dict[str, Any] | None:
    """Match a Table 2 reference row by ``ccz_factories`` (RSA-2048 consolidated block)."""
    entry = magic.get(_TABLE2_RSA2048_ROWS_KEY)
    if not isinstance(entry, dict):
        return None
    rows = entry.get("value")
    if not isinstance(rows, list):
        return None
    target = int(ccz)
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = row.get("ccz_factories")
        try:
            if raw is not None and int(raw) == target:
                return row
        except (TypeError, ValueError):
            continue
    return None


def _synthetic_pinned_from_table1(algo: Mapping[str, Any], n: int) -> dict[str, Any]:
    """
    Rebuild legacy-style pinned parameter keys from :pyattr:`_TABLE1_PINS_KEY` for ``algorithm_metrics``.
    """
    parent = algo.get(_TABLE1_PINS_KEY)
    sub = _table1_pin_row(algo, n)
    if not isinstance(parent, dict) or sub is None:
        return {}
    base = {
        "confidence": parent.get("confidence"),
        "source": parent.get("source"),
        "date": parent.get("date"),
        "section": parent.get("section"),
        "layer": "algorithm",
        "notes": f"Resolved from {_TABLE1_PINS_KEY} for n={n}.",
    }
    out: dict[str, Any] = {}
    if "toffoli_plus_t_halves_billions" in sub:
        out[f"toffoli_plus_t_halves_count_billions_n_{n}"] = {
            **base,
            "value": sub["toffoli_plus_t_halves_billions"],
            "unit": "billions_of_toffoli_plus_t_halves",
        }
    if "minimum_spacetime_volume_megaqubit_days" in sub:
        out[f"minimum_spacetime_volume_megaqubitdays_n_{n}"] = {
            **base,
            "value": sub["minimum_spacetime_volume_megaqubit_days"],
            "unit": "megaqubit_days",
        }
    return out


def _table2_dashboard_row_ref(ccz: int) -> str:
    """Stable logical pointer into the consolidated Table 2 YAML block."""
    return f"{_TABLE2_RSA2048_ROWS_KEY}#ccz_factories={int(ccz)}"


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


def _resolve_ecdlp_variant(scenario: Mapping[str, Any], warnings: list[str]) -> str:
    """Return scenario ``ecdlp_variant`` (default: low_toffoli_variant)."""
    _raw_target = scenario.get("target")
    tgt: dict[str, Any] = _raw_target if isinstance(_raw_target, dict) else {}
    raw = tgt.get("ecdlp_variant")
    if raw is None:
        raw = scenario.get("ecdlp_variant")
    if raw is None:
        return "low_toffoli_variant"
    s = str(raw).strip()
    allowed = frozenset({"low_logical_qubit_variant", "low_toffoli_variant"})
    if s in allowed:
        return s
    warnings.append(f"Unknown ecdlp_variant {raw!r}; using low_toffoli_variant.")
    return "low_toffoli_variant"


def _ecdlp_depth_multiplier(algo: Mapping[str, Any]) -> float:
    """Layers per Toffoli for ``abstract_measurement_depth_layers`` (II.1)."""
    e = algo.get("ecdlp_measurement_depth_layers_per_toffoli_gate")
    if isinstance(e, dict) and e.get("value") is not None:
        try:
            return float(e["value"])
        except (TypeError, ValueError):
            pass
    return 1.0


def _ecdlp_headline_physical_upper_bound_narrative(algo: Mapping[str, Any]) -> float | None:
    e = algo.get("headline_superconducting_physical_qubits_upper_bound")
    if isinstance(e, dict) and e.get("value") is not None:
        try:
            return float(e["value"])
        except (TypeError, ValueError):
            return None
    return None


def _build_ecdlp_report_context(
    algo: Mapping[str, Any],
    scenario: Mapping[str, Any],
    warnings: list[str],
) -> dict[str, Any] | None:
    """
    Fixed-problem ECDLP profiles: fill ``evaluated`` logical qubits + depth proxy from cited envelopes.

    Depth proxy (II.1): ``abstract_measurement_depth_layers`` =
    ``toffoli_gates_upper_bound`` × ``ecdlp_measurement_depth_layers_per_toffoli_gate``.
    """
    if algo.get("document_id") not in _ECDLP_DOCUMENT_IDS:
        return None

    variant = _resolve_ecdlp_variant(scenario, warnings)
    env_parent = algo.get(_ECDLP_ENVELOPE_KEY)
    if not isinstance(env_parent, dict):
        warnings.append(f"ECDLP algorithm missing {_ECDLP_ENVELOPE_KEY!r}; skipping ECDLP evaluation.")
        return None
    env_val = env_parent.get("value")
    if not isinstance(env_val, dict) or variant not in env_val:
        warnings.append(f"ECDLP envelope missing variant {variant!r}.")
        return None
    row = env_val.get(variant)
    if not isinstance(row, dict):
        warnings.append("ECDLP envelope variant row is not a mapping.")
        return None
    try:
        lq = float(row["logical_qubits_upper_bound"])
        tof = float(row["toffoli_gates_upper_bound"])
    except (KeyError, TypeError, ValueError) as exc:
        warnings.append(f"ECDLP envelope numeric fields invalid: {exc}")
        return None

    mult = _ecdlp_depth_multiplier(algo)
    depth_layers = tof * mult
    prov = "ecdlp_envelope_fixed_problem"

    evaluated: dict[str, Any] = {
        "abstract_logical_qubits": {
            "value": lq,
            "source_parameter": _ECDLP_ENVELOPE_KEY,
            "provenance": prov,
        },
        "abstract_measurement_depth_layers": {
            "value": depth_layers,
            "source_parameter": _ECDLP_ENVELOPE_KEY,
            "provenance": prov,
            "depth_proxy": (
                "toffoli_gates_upper_bound × ecdlp_measurement_depth_layers_per_toffoli_gate "
                f"({tof} × {mult})"
            ),
        },
    }

    skipped = [src_key for src_key, _ in _FORMULA_METRICS]
    skipped.append("exponent_register_qubits_ne_asymptotic")

    ecdlp_block: dict[str, Any] = {
        "active": True,
        "variant": variant,
        "logical_qubits_upper_bound": lq,
        "toffoli_gates_upper_bound": tof,
        "ecdlp_measurement_depth_layers_per_toffoli_gate": mult,
        "abstract_measurement_depth_layers_proxy": depth_layers,
        "depth_proxy_rule": "toffoli_upper_bound_times_layers_per_toffoli_parameter",
    }
    headline_pb = _ecdlp_headline_physical_upper_bound_narrative(algo)
    if headline_pb is not None:
        ecdlp_block["paper_headline_physical_qubits_upper_bound_narrative"] = headline_pb

    warnings.append(
        "ECDLP mode: abstract_measurement_depth_layers is a Toffoli-derived proxy for heuristics, "
        "not a compiled layer schedule from the undisclosed circuits."
    )

    return {
        "evaluated": evaluated,
        "evaluated_skipped": skipped,
        "ecdlp_block": ecdlp_block,
    }


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


def _ecdlp_dashboard_extras(ecdlp_block: dict[str, Any] | None) -> dict[str, Any]:
    if ecdlp_block is None:
        return {}
    return {
        "ecdlp_active": True,
        "ecdlp_variant": ecdlp_block.get("variant"),
        "ecdlp_toffoli_gates_upper_bound": ecdlp_block.get("toffoli_gates_upper_bound"),
        "ecdlp_paper_headline_physical_qubits_upper_bound": ecdlp_block.get(
            "paper_headline_physical_qubits_upper_bound_narrative"
        ),
    }


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

    _raw_qec = scenario.get("qec")
    qec_block: dict[str, Any] = _raw_qec if isinstance(_raw_qec, dict) else {}
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

    dist_opt_raw = qec_block.get("distance_optimizer", "discrete_scan")
    dist_opt = str(dist_opt_raw).strip().lower() if dist_opt_raw is not None else "discrete_scan"
    use_discrete_scan = dist_opt != "closed_form"

    d, hmeta = suggest_surface_code_distance_union_bound(
        physical_gate_error_rate=p,
        logical_qubit_count=lq_val,
        qec_cycle_count_proxy=dp_val,
        logical_error_budget=budget_f,
        phenomenological_p_th=p_th,
        phenomenological_prefactor=pref,
        min_d=min_d,
        max_d=max_d,
        use_discrete_scan=use_discrete_scan,
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
            "distance_optimizer": "discrete_scan" if use_discrete_scan else "closed_form",
        }
    )
    return d, meta


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

    gate_entry = modality.get("characteristic_physical_gate_error_rate")
    p: float | None = None
    if isinstance(gate_entry, dict) and gate_entry.get("value") is not None:
        try:
            p = float(gate_entry["value"])
        except (TypeError, ValueError):
            p = None

    depth_l = evaluated.get("abstract_measurement_depth_layers")
    dp_val: float | None = None
    if isinstance(depth_l, dict) and depth_l.get("value") is not None:
        try:
            dp_val = float(depth_l["value"])
        except (TypeError, ValueError):
            dp_val = None

    if p is None or dp_val is None:
        return None

    budget_raw = qec_block.get("logical_error_budget", 0.1)
    try:
        budget_f = float(budget_raw)
    except (TypeError, ValueError):
        budget_f = 0.1

    p_th = _param_entry_float(qec.get("heuristic_surface_code_physical_threshold_order_of_magnitude"), 0.01)
    pref = _param_entry_float(qec.get("heuristic_logical_error_prefactor"), 0.05)
    min_d = int(_param_entry_float(qec.get("heuristic_distance_min_d"), 5))
    max_d = int(_param_entry_float(qec.get("heuristic_distance_max_d"), 55))

    candidates = build_layout_distance_candidates(
        patch_formula=patch_formula,
        logical_qubits=float(logical_qubits),
        physical_gate_error_rate=p,
        qec_cycle_count_proxy=dp_val,
        logical_error_budget=budget_f,
        phenomenological_p_th=p_th,
        phenomenological_prefactor=pref,
        min_d=min_d,
        max_d=max_d,
        reported_total_physical_qubits=reported_total_physical_qubits,
        factory_footprint_physical_qubits=factory_footprint_physical_qubits,
    )
    summary = summarize_layout_optimization(
        selected_d=int(selected_d),
        candidates=candidates,
        logical_error_budget=budget_f,
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
    _raw_target = scenario.get("target")
    target: dict[str, Any] = _raw_target if isinstance(_raw_target, dict) else {}
    algo = bundle.algorithm

    ecdlp_ctx = _build_ecdlp_report_context(algo, scenario, warnings)
    ecdlp_block_for_metrics: dict[str, Any] | None = None

    evaluated: dict[str, Any] = {}
    evaluated_skipped: list[str] = []
    n: int | None = None

    if ecdlp_ctx is not None:
        evaluated = ecdlp_ctx["evaluated"]
        evaluated_skipped = ecdlp_ctx["evaluated_skipped"]
        ecdlp_block_for_metrics = ecdlp_ctx["ecdlp_block"]
    else:
        n_raw = modulus_bits_override if modulus_bits_override is not None else target.get("modulus_bit_length")
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
    if n is not None:
        for k, v in _synthetic_pinned_from_table1(algo, n).items():
            pinned.setdefault(k, v)

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
    table2_row_layout_descriptor: str | None = None
    if ccz_count is not None:
        row_ref = _table2_dashboard_row_ref(ccz_count)
        phys_key = mega_key = wall_key = row_ref
        t2_row = _table2_rsa2048_row_for_ccz(bundle.magic, ccz_count)
        if t2_row is None:
            warnings.append(
                f"No row with ccz_factories={ccz_count} in magic YAML {_TABLE2_RSA2048_ROWS_KEY!r}; "
                "Table 2 pins omitted."
            )
        else:
            ld = t2_row.get("layout_descriptor")
            table2_row_layout_descriptor = str(ld) if ld is not None else None
            factory_param_key = table2_row_layout_descriptor
            try:
                rsa2048_phys = float(t2_row["physical_qubits_millions"])
            except (KeyError, TypeError, ValueError):
                rsa2048_phys = None
                warnings.append(
                    f"Table 2 row {row_ref!r} missing or non-numeric physical_qubits_millions."
                )
            rsa2048_megaqd = None
            try:
                rsa2048_megaqd = float(t2_row["megaqubit_days"])
            except (KeyError, TypeError, ValueError):
                warnings.append(f"Table 2 row {row_ref!r} missing or non-numeric megaqubit_days.")
            rsa2048_wall_days = None
            try:
                rsa2048_wall_days = float(t2_row["wall_clock_days"])
            except (KeyError, TypeError, ValueError):
                warnings.append(f"Table 2 row {row_ref!r} missing or non-numeric wall_clock_days.")
    elif table2_block is not None:
        warnings.append("Could not parse CCZ factory count from table2_reference_row.value.")

    toffoli_b = None
    megaqd = None
    if n is not None:
        t1 = _table1_pin_row(algo, n)
        if t1 is not None:
            raw_tb = t1.get("toffoli_plus_t_halves_billions")
            if raw_tb is not None:
                try:
                    toffoli_b = float(raw_tb)
                except (TypeError, ValueError):
                    pass
            raw_mq = t1.get("minimum_spacetime_volume_megaqubit_days")
            if raw_mq is not None:
                try:
                    megaqd = float(raw_mq)
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

    qcvv_layer = None
    if bundle.qcvv is not None:
        qv_h, qv_p = _split_document(bundle.qcvv)
        qcvv_layer = {"document_id": qv_h.get("document_id"), "header": qv_h, "parameters": qv_p}

    qem_layer = None
    if bundle.qem is not None:
        qm_h, qm_p = _split_document(bundle.qem)
        qem_layer = {"document_id": qm_h.get("document_id"), "header": qm_h, "parameters": qm_p}

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
    )

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
                depth_src = (
                    "ecdlp_logical_resource_envelopes_secp256k1_proxy"
                    if ecdlp_block_for_metrics is not None
                    else "abstract_measurement_depth_formula"
                )
                naive_serial_timing = {
                    "abstract_measurement_depth_layers": depth_val,
                    "surface_code_cycle_time_microseconds": cycle_us,
                    "serial_time_microseconds": serial_us,
                    "serial_time_days": serial_days,
                    "provenance": "computed_from_measurement_depth_times_surface_cycle",
                    "source_parameters": {
                        "depth": depth_src,
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
            "source_parameter": _TABLE2_RSA2048_ROWS_KEY,
            "layout_descriptor": table2_row_layout_descriptor,
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

    algo_metrics = _algorithm_metrics_block(
        n=n,
        evaluated=evaluated,
        evaluated_skipped=evaluated_skipped,
        pinned=pinned,
        ecdlp_block=ecdlp_block_for_metrics,
    )

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
            "qcvv": _source_header(bundle.qcvv) if bundle.qcvv else None,
            "qem": _source_header(bundle.qem) if bundle.qem else None,
        },
        "layers": {
            "modality": {"document_id": modality_h.get("document_id"), "header": modality_h, "parameters": modality_p},
            "qec": {"document_id": qec_h.get("document_id"), "header": qec_h, "parameters": qec_p},
            "magic": {"document_id": magic_h.get("document_id"), "header": magic_h, "parameters": magic_p},
            "magic_aux": magic_aux_layer,
            "qcvv": qcvv_layer,
            "qem": qem_layer,
            "algorithm": {"document_id": algo_h.get("document_id"), "header": algo_h, "parameters": algo_p},
        },
        "algorithm_metrics": algo_metrics,
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
        "system_metrics": _build_system_metrics_placeholder(),
        "qec_distance_resolution": qec_distance_resolution,
        "layout_estimate": layout_estimate,
        "layout_optimization": layout_optimization,
        "timing": timing_block,
        "dashboard": {
            "ccz_factory_count": ccz_count,
            "ccz_factory_parameter_key": factory_param_key,
            "table2_pinned_source_parameter": _TABLE2_RSA2048_ROWS_KEY if ccz_count is not None else None,
            "table2_pinned_row_layout_descriptor": table2_row_layout_descriptor,
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
            **_ecdlp_dashboard_extras(ecdlp_block_for_metrics),
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
        if report.get("algorithm_metrics", {}).get("ecdlp"):
            lines.append(
                f"**Target** ECDLP `{tgt.get('problem')}` · variant `{tgt.get('ecdlp_variant')}` "
                f"(curve bits {tgt.get('curve_bit_length')})\n"
            )
        else:
            lines.append(
                f"**Target** modulus bits **{tgt.get('modulus_bit_length')}**, problem `{tgt.get('problem')}`\n"
            )

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

    sm = report.get("system_metrics") or {}
    lines.append("\n## System metrics (OSRE)\n")
    lines.append(
        f"- **Status:** `{sm.get('status')}` — LQC/LOB/QOT/headroom/VER reserved for future computation "
        f"(contract v{report.get('report_contract_version')}).\n"
    )

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
