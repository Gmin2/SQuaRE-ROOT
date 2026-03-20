"""
Layout proxy optimization: evaluate patch scaling across candidate code distances.

Pairs with :mod:`square.qec_distance_heuristic` — same objective: minimal odd ``d`` meeting
the union bound, with optional per-``d`` data-plane qubit estimates.
"""

from __future__ import annotations

from typing import Any

from square.formula_eval import FormulaEvalError, eval_numeric_formula_with_bindings
from square.qec_distance_heuristic import union_bound_total_failure_mass


def build_layout_distance_candidates(
    *,
    patch_formula: str | None,
    logical_qubits: float,
    physical_gate_error_rate: float,
    qec_cycle_count_proxy: float,
    logical_error_budget: float,
    phenomenological_p_th: float,
    phenomenological_prefactor: float,
    min_d: int,
    max_d: int,
    reported_total_physical_qubits: float | None,
    factory_footprint_physical_qubits: float | None,
) -> list[dict[str, Any]]:
    """
    For each odd ``d`` in range, compute union-bound mass, optional patch size, and layout proxies.

    :param patch_formula: QEC profile formula in ``d`` (e.g. ``2 * (d + 1)**2``).
    :param logical_qubits: Evaluated abstract logical qubit count at scenario ``n``.
    :param factory_footprint_physical_qubits: ``ccz_count * per_factory`` when available.
    :returns: Rows sorted by increasing ``d``.
    """
    rows: list[dict[str, Any]] = []
    lo = max(1, int(min_d))
    hi = max(lo, int(max_d))
    d0 = lo if lo % 2 == 1 else lo + 1

    for d in range(d0, hi + 1, 2):
        mass = union_bound_total_failure_mass(
            d,
            physical_gate_error_rate=physical_gate_error_rate,
            logical_qubit_count=logical_qubits,
            qec_cycle_count_proxy=qec_cycle_count_proxy,
            phenomenological_p_th=phenomenological_p_th,
            phenomenological_prefactor=phenomenological_prefactor,
        )
        patch_per_logical: float | None = None
        data_plane: float | None = None
        total_with_factories: float | None = None
        abs_residual_vs_reported: float | None = None
        if patch_formula:
            try:
                patch_per_logical = eval_numeric_formula_with_bindings(patch_formula, {"d": float(d)})
                data_plane = float(logical_qubits) * float(patch_per_logical)
                if factory_footprint_physical_qubits is not None:
                    total_with_factories = data_plane + float(factory_footprint_physical_qubits)
                if reported_total_physical_qubits is not None and total_with_factories is not None:
                    abs_residual_vs_reported = abs(float(reported_total_physical_qubits) - total_with_factories)
            except (FormulaEvalError, ZeroDivisionError, OverflowError, TypeError, ValueError):
                patch_per_logical = None
                data_plane = None

        rows.append(
            {
                "distance_d": d,
                "union_bound_mass": mass,
                "satisfies_budget": mass <= float(logical_error_budget),
                "physical_qubits_per_logical": patch_per_logical,
                "approximate_data_plane_physical_qubits": data_plane,
                "total_physical_qubits_proxy_data_plus_factories": total_with_factories,
                "absolute_residual_vs_reported_total": abs_residual_vs_reported,
            }
        )
    return rows


def summarize_layout_optimization(
    *,
    selected_d: int,
    candidates: list[dict[str, Any]],
    logical_error_budget: float,
    patch_formula: str | None,
) -> dict[str, Any]:
    """Pick summary stats and best fit-to-reported row among budget-satisfying distances."""
    selected_row = next((r for r in candidates if r["distance_d"] == selected_d), None)
    satisfying = [r for r in candidates if r["satisfies_budget"]]
    best_fit: dict[str, Any] | None = None
    if satisfying:
        with_residual = [r for r in satisfying if r.get("absolute_residual_vs_reported") is not None]
        if with_residual:
            best_fit = min(with_residual, key=lambda r: float(r["absolute_residual_vs_reported"]))

    return {
        "objective": "minimize_odd_code_distance_subject_to_union_bound",
        "logical_error_budget": float(logical_error_budget),
        "selected_code_distance_d": selected_d,
        "selected_row": selected_row,
        "count_candidates": len(candidates),
        "count_satisfying_budget": len(satisfying),
        "best_fit_distance_d_by_reported_total_residual": best_fit["distance_d"] if best_fit else None,
        "patch_formula": patch_formula,
        "provenance": "layout_proxy_scan_v1",
    }
