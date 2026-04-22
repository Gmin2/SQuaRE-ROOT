"""Unit tests for layout distance scan (isolated from full report)."""

from __future__ import annotations

import pytest
from square.layout_optimization import (
    build_layout_distance_candidates,
    summarize_layout_optimization,
)


def test_build_layout_distance_candidates_odd_scan_and_patch() -> None:
    rows = build_layout_distance_candidates(
        patch_formula="2 * (d + 1)**2",
        logical_qubits=10.0,
        physical_gate_error_rate=0.001,
        qec_cycle_count_proxy=1e4,
        logical_error_budget=0.5,
        phenomenological_p_th=0.01,
        phenomenological_prefactor=0.05,
        min_d=5,
        max_d=9,
        reported_total_physical_qubits=None,
        factory_footprint_physical_qubits=None,
    )
    assert len(rows) == 3
    assert [r["distance_d"] for r in rows] == [5, 7, 9]
    r5 = rows[0]
    assert r5["physical_qubits_per_logical"] == pytest.approx(72.0)
    assert r5["approximate_data_plane_physical_qubits"] == pytest.approx(720.0)


def test_summarize_layout_optimization_shape() -> None:
    rows = build_layout_distance_candidates(
        patch_formula=None,
        logical_qubits=100.0,
        physical_gate_error_rate=0.001,
        qec_cycle_count_proxy=1e3,
        logical_error_budget=0.2,
        phenomenological_p_th=0.01,
        phenomenological_prefactor=0.05,
        min_d=5,
        max_d=9,
        reported_total_physical_qubits=None,
        factory_footprint_physical_qubits=None,
    )
    summary = summarize_layout_optimization(
        selected_d=7,
        candidates=rows,
        logical_error_budget=0.2,
        patch_formula=None,
    )
    assert summary["selected_code_distance_d"] == 7
    assert summary["count_candidates"] == 3
    assert summary["objective"] == "minimize_odd_code_distance_subject_to_union_bound"
