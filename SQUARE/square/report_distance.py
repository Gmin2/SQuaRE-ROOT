"""
Surface-code distance resolution: scenario / CLI override vs heuristic union bound.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from square.heuristic_union_inputs import read_heuristic_union_bound_inputs
from square.qec_distance_heuristic import suggest_union_bound_code_distance
from square.yaml_numeric import (
    read_evaluated_metric_float,
    read_modality_characteristic_gate_error,
)


def read_heuristic_phenomenological_logical_error_model_applies(
    scenario: Mapping[str, Any],
    warnings: list[str],
) -> bool:
    """
    When ``scenario.qec.heuristic_phenomenological_logical_error_model_applies`` is explicitly false,
    the engine must not use the phenomenological union-bound / ``p_L`` stack (distance heuristic, fault model).

    Omitted or unknown values default to ``True`` for backward compatibility.
    """
    raw = scenario.get("qec")
    if not isinstance(raw, dict):
        return True
    key = raw.get("heuristic_phenomenological_logical_error_model_applies")
    if key is None:
        return True
    if isinstance(key, bool):
        return key
    s = str(key).strip().lower()
    if s in ("false", "0", "no", "off"):
        return False
    if s in ("true", "1", "yes", "on"):
        return True
    warnings.append(
        "scenario.qec.heuristic_phenomenological_logical_error_model_applies is not a boolean; "
        "treating as true."
    )
    return True


def parse_code_distance_from_scenario(
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


def resolve_code_distance_full(
    scenario: Mapping[str, Any],
    *,
    override: int | None,
    modality: Mapping[str, Any],
    qec: Mapping[str, Any],
    evaluated: Mapping[str, Any],
    warnings: list[str],
    physical_gate_error_rate_effective: float | None = None,
) -> tuple[int | None, dict[str, Any]]:
    """
    CLI override, explicit scenario distance, or heuristic (when ``qec.distance_policy`` requests it).
    """
    meta: dict[str, Any] = {"mode": "unset"}

    if override is not None:
        d, w = parse_code_distance_from_scenario(scenario, override=override)
        warnings.extend(w)
        meta.update({"mode": "cli_override", "distance_d": d, "from_cli_override": True})
        return d, meta

    d_explicit, w = parse_code_distance_from_scenario(scenario, override=None)
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

    if not read_heuristic_phenomenological_logical_error_model_applies(scenario, warnings):
        warnings.append(
            "qec.distance_policy requests a heuristic but scenario.qec.heuristic_phenomenological_logical_error_model_applies "
            "is false; distance d not computed via phenomenological union bound."
        )
        meta.update({"mode": "heuristic_disabled_by_assumption", "distance_d": None})
        return None, meta

    p: float | None = physical_gate_error_rate_effective
    if p is None:
        p = read_modality_characteristic_gate_error(modality, warnings, context="paths.modality")
    if p is None:
        warnings.append(
            "qec.distance_policy requests a heuristic but modality characteristic_physical_gate_error_rate "
            "is missing or non-numeric; distance d not computed."
        )
        meta.update({"mode": "heuristic_failed_missing_p", "distance_d": None})
        return None, meta

    lq_val = read_evaluated_metric_float(
        evaluated,
        "abstract_logical_qubits",
        warnings,
        context="heuristic_distance",
    )
    dp_val = read_evaluated_metric_float(
        evaluated,
        "abstract_measurement_depth_layers",
        warnings,
        context="heuristic_distance",
    )
    if lq_val is None or dp_val is None:
        warnings.append(
            "Heuristic distance skipped: need evaluated abstract_logical_qubits and abstract_measurement_depth_layers."
        )
        meta.update({"mode": "heuristic_failed_missing_formulas", "distance_d": None})
        return None, meta

    hu = read_heuristic_union_bound_inputs(qec, qec_block, warnings, budget_warning_context=None)

    d, hmeta = suggest_union_bound_code_distance(
        physical_gate_error_rate=p,
        logical_qubit_count=lq_val,
        qec_cycle_count_proxy=dp_val,
        logical_error_budget=hu.logical_error_budget,
        phenomenological_p_th=hu.phenomenological_p_th,
        phenomenological_prefactor=hu.phenomenological_prefactor,
        min_d=hu.min_d,
        max_d=hu.max_d,
        use_discrete_scan=hu.use_discrete_scan,
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
            "logical_error_budget": hu.logical_error_budget,
            "distance_optimizer": "discrete_scan" if hu.use_discrete_scan else "closed_form",
            "physical_gate_error_rate_effective": p,
        }
    )
    return d, meta
