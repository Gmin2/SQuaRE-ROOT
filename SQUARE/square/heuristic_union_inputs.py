"""Shared QEC heuristic inputs for union-bound distance, layout scan, and parameter sensitivity."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from square.yaml_numeric import read_parameter_entry_float_default


@dataclass(frozen=True)
class HeuristicUnionBoundInputs:
    """Phenomenological union-bound knobs from QEC YAML (single source of defaults and warnings)."""

    logical_error_budget: float
    phenomenological_p_th: float
    phenomenological_prefactor: float
    min_d: int
    max_d: int
    use_discrete_scan: bool


def read_heuristic_union_bound_inputs(
    qec: Mapping[str, Any],
    qec_block: Mapping[str, Any],
    warnings: list[str],
    *,
    budget_warning_context: str | None = None,
) -> HeuristicUnionBoundInputs:
    """
    Parse ``logical_error_budget``, phenomenological thresholds, distance bounds, and distance optimizer mode.

    :param budget_warning_context: If set, invalid-budget warnings are prefixed; if ``None``, use the legacy
        single-line message ``qec.logical_error_budget invalid; using 0.1.`` (report distance heuristic).
    """
    budget_raw = qec_block.get("logical_error_budget", 0.1)
    try:
        budget_f = float(budget_raw)
    except (TypeError, ValueError):
        budget_f = 0.1
        if budget_warning_context:
            warnings.append(f"{budget_warning_context}: qec.logical_error_budget invalid; using 0.1.")
        else:
            warnings.append("qec.logical_error_budget invalid; using 0.1.")

    p_th = read_parameter_entry_float_default(
        qec.get("heuristic_surface_code_physical_threshold_order_of_magnitude"),
        0.01,
        warnings,
        context="paths.qec",
        param_name="heuristic_surface_code_physical_threshold_order_of_magnitude",
    )
    pref = read_parameter_entry_float_default(
        qec.get("heuristic_logical_error_prefactor"),
        0.05,
        warnings,
        context="paths.qec",
        param_name="heuristic_logical_error_prefactor",
    )
    min_d = int(
        read_parameter_entry_float_default(
            qec.get("heuristic_distance_min_d"),
            5.0,
            warnings,
            context="paths.qec",
            param_name="heuristic_distance_min_d",
        )
    )
    max_d = int(
        read_parameter_entry_float_default(
            qec.get("heuristic_distance_max_d"),
            55.0,
            warnings,
            context="paths.qec",
            param_name="heuristic_distance_max_d",
        )
    )

    dist_opt_raw = qec_block.get("distance_optimizer", "discrete_scan")
    dist_opt = str(dist_opt_raw).strip().lower() if dist_opt_raw is not None else "discrete_scan"
    use_discrete_scan = dist_opt != "closed_form"

    return HeuristicUnionBoundInputs(
        logical_error_budget=budget_f,
        phenomenological_p_th=p_th,
        phenomenological_prefactor=pref,
        min_d=min_d,
        max_d=max_d,
        use_discrete_scan=use_discrete_scan,
    )
