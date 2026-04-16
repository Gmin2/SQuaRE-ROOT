"""Tests for phenomenological surface-code distance heuristic."""

from __future__ import annotations

import math

import pytest
from square.qec_distance_heuristic import (
    min_odd_distance_discrete_scan,
    suggest_surface_code_distance_union_bound,
)


def test_suggest_d_rsa2048_baseline_matches_report_golden() -> None:
    n = 2048
    lq = 3 * n + 0.002 * n * math.log2(n)
    dp = 500 * n**2 + n**2 * math.log2(n)
    d, meta = suggest_surface_code_distance_union_bound(
        physical_gate_error_rate=0.001,
        logical_qubit_count=lq,
        qec_cycle_count_proxy=dp,
        logical_error_budget=0.1,
    )
    assert d == 25
    assert meta["distance_d"] == 25
    assert meta["p_over_p_th"] == pytest.approx(0.1)
    assert meta["optimizer"] == "discrete_odd_d_scan_v1"
    assert meta["closed_form_distance_d"] == 25


def test_discrete_scan_first_feasible_is_min_odd_d() -> None:
    n = 2048
    lq = 3 * n + 0.002 * n * math.log2(n)
    dp = 500 * n**2 + n**2 * math.log2(n)
    d, meta = min_odd_distance_discrete_scan(
        physical_gate_error_rate=0.001,
        logical_qubit_count=lq,
        qec_cycle_count_proxy=dp,
        logical_error_budget=0.1,
        phenomenological_p_th=0.01,
        phenomenological_prefactor=0.05,
        min_d=5,
        max_d=55,
    )
    assert d == 25
    rows = meta["scan_rows"]
    assert rows[0]["distance_d"] == 5
    first_ok = next(r for r in rows if r["satisfies_budget"])
    assert first_ok["distance_d"] == 25


def test_p_above_threshold_clamps() -> None:
    d, meta = suggest_surface_code_distance_union_bound(
        physical_gate_error_rate=0.02,
        logical_qubit_count=100.0,
        qec_cycle_count_proxy=1e6,
        logical_error_budget=0.1,
        max_d=31,
    )
    assert d % 2 == 1
    assert d <= 31
    assert "note" in meta
