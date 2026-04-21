"""Tests for Monte Carlo forward-model metric extraction."""

from __future__ import annotations

import pytest
from square.mc.forward_model import (
    MC_DASHBOARD_METRIC_FIELDS,
    MC_ECDLP_METRIC_KEY,
    extract_default_mc_metrics,
)


def test_extract_default_mc_metrics_base_keys_match_contract() -> None:
    """Base keys are defined once in MC_DASHBOARD_METRIC_FIELDS to avoid drift from the report dashboard."""
    m = extract_default_mc_metrics({})
    assert set(m.keys()) == {k for k, _ in MC_DASHBOARD_METRIC_FIELDS}
    assert all(v is None for v in m.values())


def test_extract_default_mc_metrics_includes_ecdlp_key_when_present() -> None:
    report = {
        "dashboard": {
            "naive_serial_time_days_from_depth_times_cycle": 1.5,
            "code_distance_d": 7,
            "approximate_data_plane_physical_qubits": 100.0,
            "logical_qubits_at_n": 2000.0,
            "logical_failure_probability_union_depth_proxy": 0.03,
            "magic_limited_runtime_multiplier": 1.25,
        },
        "algorithm_metrics": {"ecdlp": {"toffoli_gates_upper_bound": 1e6}},
    }
    m = extract_default_mc_metrics(report)
    assert m["code_distance_d"] == 7.0
    assert m["logical_failure_probability_union_depth_proxy"] == pytest.approx(0.03)
    assert m["magic_limited_runtime_multiplier"] == pytest.approx(1.25)
    assert MC_ECDLP_METRIC_KEY in m
    assert m[MC_ECDLP_METRIC_KEY] == 1e6
