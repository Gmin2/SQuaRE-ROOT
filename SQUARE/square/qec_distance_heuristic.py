"""
Heuristic surface-code distance selection (not a replacement for paper-specific optimizers).

Uses a phenomenological per-round logical error model and a union bound over logical
qubits × depth proxy. See :func:`suggest_surface_code_distance_union_bound`.
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


def suggest_surface_code_distance_union_bound(
    *,
    physical_gate_error_rate: float,
    logical_qubit_count: float,
    qec_cycle_count_proxy: float,
    logical_error_budget: float = 0.1,
    phenomenological_p_th: float = 0.01,
    phenomenological_prefactor: float = 0.05,
    min_d: int = 5,
    max_d: int = 55,
) -> tuple[int, dict[str, Any]]:
    """
    Suggest an odd code distance using a conservative union bound.

    Assumes per-round logical error per logical qubit scales as
    ``prefactor * (p / p_th) ** ((d+1)/2)`` (phenomenological; constants are tunable in YAML).

    Union bound: ``logical_qubits * cycles * P_L <= budget``.

    :param physical_gate_error_rate: Physical error probability per gate (e.g. 0.001).
    :param logical_qubit_count: Proxy for number of logical qubits at risk (e.g. abstract logical qubits).
    :param qec_cycle_count_proxy: Proxy for QEC rounds or layers (e.g. abstract measurement depth).
    :param logical_error_budget: Allowed total logical failure mass (not rigorous success probability).
    :param phenomenological_p_th: Reference threshold scale in the same units as ``p``.
    :param phenomenological_prefactor: Leading coefficient inside the exponential model.
    :param min_d: Clamp minimum odd distance.
    :param max_d: Clamp maximum odd distance.
    :returns: ``(d, metadata)`` with inputs echoed for the report.
    """
    meta: dict[str, Any] = {
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

    if physical_gate_error_rate <= 0 or physical_gate_error_rate >= phenomenological_p_th:
        d = _odd_int_clamped(max_d, min_d=min_d, max_d=max_d)
        meta["note"] = (
            "Heuristic assumes p < p_th; returning clamped distance. "
            "Tune modality gate error or qec profile threshold."
        )
        meta["distance_d"] = d
        return d, meta

    lq = max(float(logical_qubit_count), 1.0)
    cy = max(float(qec_cycle_count_proxy), 1.0)
    eps = float(logical_error_budget) / (lq * cy)
    meta["epsilon_per_logical_per_cycle_proxy"] = eps

    r = physical_gate_error_rate / phenomenological_p_th
    meta["p_over_p_th"] = r

    if eps >= phenomenological_prefactor:
        d = _odd_int_clamped(min_d, min_d=min_d, max_d=max_d)
        meta["note"] = "Budget loose vs prefactor; using min_d."
        meta["distance_d"] = d
        return d, meta

    # prefactor * r ** ((d+1)/2) <= eps  =>  ((d+1)/2) * log(r) <= log(eps / prefactor)
    # r < 1 so log(r) < 0.
    half = math.log(eps / phenomenological_prefactor) / math.log(r)
    meta["half_distance_float"] = half
    d_raw = int(2 * max(1, math.ceil(half)) - 1)
    d = _odd_int_clamped(d_raw, min_d=min_d, max_d=max_d)
    meta["distance_d"] = d
    return d, meta
