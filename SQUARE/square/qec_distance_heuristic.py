"""
Heuristic surface-code distance selection (not a replacement for paper-specific optimizers).

Uses a phenomenological per-round logical error model and a union bound over logical
qubits × depth proxy. The **primary** suggestion uses a discrete scan over odd ``d``;
an analytic closed form is retained for diagnostics.
"""

from __future__ import annotations

import math
from typing import Any


def _odd_int_clamped(d: int, *, min_d: int, max_d: int) -> int:
    d = max(min_d, min(max_d, d))
    if d % 2 == 0:
        d += 1
        if d > max_d:
            d = max_d - 1 if (max_d % 2 == 0) else max_d
    return d


def phenomenological_logical_error_per_cycle(
    d: int,
    *,
    physical_gate_error_rate: float,
    phenomenological_p_th: float,
    phenomenological_prefactor: float,
) -> float:
    """
    Per-(logical,cycle) logical error proxy: ``prefactor * (p/p_th)^ceil((d+1)/2)``.

    For odd ``d``, ``ceil((d+1)/2) = (d+1)/2``.
    """
    r = physical_gate_error_rate / phenomenological_p_th
    exp = (d + 1) // 2
    return float(phenomenological_prefactor) * (r**exp)


def union_bound_total_failure_mass(
    d: int,
    *,
    physical_gate_error_rate: float,
    logical_qubit_count: float,
    qec_cycle_count_proxy: float,
    phenomenological_p_th: float,
    phenomenological_prefactor: float,
) -> float:
    """Union bound: ``N_logical * N_cycles * P_L(d)``."""
    pl = phenomenological_logical_error_per_cycle(
        d,
        physical_gate_error_rate=physical_gate_error_rate,
        phenomenological_p_th=phenomenological_p_th,
        phenomenological_prefactor=phenomenological_prefactor,
    )
    lq = max(float(logical_qubit_count), 1.0)
    cy = max(float(qec_cycle_count_proxy), 1.0)
    return lq * cy * pl


def min_odd_distance_discrete_scan(
    *,
    physical_gate_error_rate: float,
    logical_qubit_count: float,
    qec_cycle_count_proxy: float,
    logical_error_budget: float,
    phenomenological_p_th: float,
    phenomenological_prefactor: float,
    min_d: int,
    max_d: int,
) -> tuple[int, dict[str, Any]]:
    """
    Smallest **odd** ``d`` in ``[min_d, max_d]`` with union-bound mass ``<= budget``.

    If none satisfy the budget, returns clamped ``max_d`` (odd) with a note.
    """
    meta: dict[str, Any] = {
        "optimizer": "discrete_odd_d_scan_v1",
        "physical_gate_error_rate": physical_gate_error_rate,
        "logical_qubit_count": logical_qubit_count,
        "qec_cycle_count_proxy": qec_cycle_count_proxy,
        "logical_error_budget": logical_error_budget,
        "phenomenological_p_th": phenomenological_p_th,
        "phenomenological_prefactor": phenomenological_prefactor,
        "min_d": min_d,
        "max_d": max_d,
    }

    if physical_gate_error_rate <= 0 or physical_gate_error_rate >= phenomenological_p_th:
        d = _odd_int_clamped(max_d, min_d=min_d, max_d=max_d)
        meta["note"] = (
            "Heuristic assumes p < p_th; returning clamped distance. "
            "Tune modality gate error or qec profile threshold."
        )
        meta["distance_d"] = d
        meta["scan_rows"] = []
        return d, meta

    budget = float(logical_error_budget)
    lq = max(float(logical_qubit_count), 1.0)
    cy = max(float(qec_cycle_count_proxy), 1.0)
    meta["epsilon_per_logical_per_cycle_proxy"] = budget / (lq * cy)
    meta["p_over_p_th"] = physical_gate_error_rate / phenomenological_p_th

    lo = max(1, int(min_d))
    hi = max(lo, int(max_d))
    d0 = lo if lo % 2 == 1 else lo + 1
    if d0 > hi:
        d0 = _odd_int_clamped(hi, min_d=lo, max_d=hi)

    scan_rows: list[dict[str, Any]] = []
    chosen: int | None = None
    for d in range(d0, hi + 1, 2):
        mass = union_bound_total_failure_mass(
            d,
            physical_gate_error_rate=physical_gate_error_rate,
            logical_qubit_count=logical_qubit_count,
            qec_cycle_count_proxy=qec_cycle_count_proxy,
            phenomenological_p_th=phenomenological_p_th,
            phenomenological_prefactor=phenomenological_prefactor,
        )
        ok = mass <= budget
        scan_rows.append({"distance_d": d, "union_bound_mass": mass, "satisfies_budget": ok})
        if ok and chosen is None:
            chosen = d

    meta["scan_rows"] = scan_rows

    if chosen is not None:
        meta["distance_d"] = chosen
        return chosen, meta

    d_fallback = _odd_int_clamped(hi, min_d=lo, max_d=hi)
    meta["distance_d"] = d_fallback
    meta["note"] = "No odd distance in [min_d, max_d] meets the union-bound budget; using max_d (odd)."
    return d_fallback, meta


def _closed_form_odd_distance(
    *,
    physical_gate_error_rate: float,
    logical_qubit_count: float,
    qec_cycle_count_proxy: float,
    logical_error_budget: float,
    phenomenological_p_th: float,
    phenomenological_prefactor: float,
    min_d: int,
    max_d: int,
) -> tuple[int | None, dict[str, Any]]:
    """Legacy continuous relaxation → odd ``d`` (for comparison to the discrete optimizer)."""
    meta: dict[str, Any] = {}
    if physical_gate_error_rate <= 0 or physical_gate_error_rate >= phenomenological_p_th:
        return None, meta
    lq = max(float(logical_qubit_count), 1.0)
    cy = max(float(qec_cycle_count_proxy), 1.0)
    eps = float(logical_error_budget) / (lq * cy)
    r = physical_gate_error_rate / phenomenological_p_th
    meta["half_distance_float"] = None
    if eps >= phenomenological_prefactor:
        return _odd_int_clamped(min_d, min_d=min_d, max_d=max_d), meta
    half = math.log(eps / phenomenological_prefactor) / math.log(r)
    meta["half_distance_float"] = half
    d_raw = int(2 * max(1, math.ceil(half)) - 1)
    return _odd_int_clamped(d_raw, min_d=min_d, max_d=max_d), meta


def suggest_union_bound_code_distance(
    *,
    physical_gate_error_rate: float,
    logical_qubit_count: float,
    qec_cycle_count_proxy: float,
    logical_error_budget: float = 0.1,
    phenomenological_p_th: float = 0.01,
    phenomenological_prefactor: float = 0.05,
    min_d: int = 5,
    max_d: int = 55,
    use_discrete_scan: bool = True,
) -> tuple[int, dict[str, Any]]:
    """
    Suggest an odd code distance using a conservative phenomenological union bound.

    Code-family agnostic (surface, LDPC placeholder profiles, etc.); not a paper-specific optimizer.
    When ``use_discrete_scan`` is True (default), uses :func:`min_odd_distance_discrete_scan`.
    Otherwise uses the closed-form inversion + clamping (legacy).

    Metadata always includes ``closed_form_distance_d`` when defined for A/B checks.
    """
    base_meta: dict[str, Any] = {
        "model": "phenomenological_union_bound_v1",
        "physical_gate_error_rate": physical_gate_error_rate,
        "logical_qubit_count": logical_qubit_count,
        "qec_cycle_count_proxy": qec_cycle_count_proxy,
        "logical_error_budget": logical_error_budget,
        "phenomenological_p_th": phenomenological_p_th,
        "phenomenological_prefactor": phenomenological_prefactor,
        "min_d": min_d,
        "max_d": max_d,
    }

    cf_d, cf_extra = _closed_form_odd_distance(
        physical_gate_error_rate=physical_gate_error_rate,
        logical_qubit_count=logical_qubit_count,
        qec_cycle_count_proxy=qec_cycle_count_proxy,
        logical_error_budget=logical_error_budget,
        phenomenological_p_th=phenomenological_p_th,
        phenomenological_prefactor=phenomenological_prefactor,
        min_d=min_d,
        max_d=max_d,
    )
    base_meta["closed_form_distance_d"] = cf_d
    base_meta.update(cf_extra)

    if not use_discrete_scan:
        if cf_d is None:
            d = _odd_int_clamped(max_d, min_d=min_d, max_d=max_d)
            base_meta["distance_d"] = d
            base_meta["optimizer"] = "closed_form_fallback"
            return d, base_meta
        base_meta["distance_d"] = cf_d
        base_meta["optimizer"] = "closed_form_only"
        return cf_d, base_meta

    d, scan_meta = min_odd_distance_discrete_scan(
        physical_gate_error_rate=physical_gate_error_rate,
        logical_qubit_count=logical_qubit_count,
        qec_cycle_count_proxy=qec_cycle_count_proxy,
        logical_error_budget=logical_error_budget,
        phenomenological_p_th=phenomenological_p_th,
        phenomenological_prefactor=phenomenological_prefactor,
        min_d=min_d,
        max_d=max_d,
    )
    # Merge scan output into base_meta (scan_rows, optimizer, note, etc.)
    base_meta.update(scan_meta)
    base_meta["distance_d"] = d
    return d, base_meta


# Backward-compatible alias (older name implied surface-only).
suggest_surface_code_distance_union_bound = suggest_union_bound_code_distance
