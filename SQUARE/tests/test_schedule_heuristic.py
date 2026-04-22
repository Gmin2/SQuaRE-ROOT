"""Unit tests for schedule heuristics (isolated from full report)."""

from __future__ import annotations

import pytest
from square.schedule_heuristic import (
    build_parallel_depth_schedule_v1,
    infer_reaction_limited_from_scenario,
)


def test_infer_reaction_limited_explicit_scenario_wins() -> None:
    rlim, src = infer_reaction_limited_from_scenario(
        {"schedule": {"reaction_limited": False}},
        table2_row_value=None,
        factory_parameter_key=None,
    )
    assert rlim is False
    assert "scenario.schedule" in src


def test_infer_reaction_limited_distillation_in_row() -> None:
    rlim, _src = infer_reaction_limited_from_scenario(
        {},
        table2_row_value="distillation_limited_ripple_carry",
        factory_parameter_key=None,
    )
    assert rlim is False


def test_build_parallel_depth_schedule_v1_reaction_limited() -> None:
    out = build_parallel_depth_schedule_v1(
        abstract_measurement_depth_layers=1_000_000.0,
        surface_code_cycle_microseconds=1.0,
        classical_reaction_microseconds=10.0,
        ccz_factory_count=2,
        reaction_limited=True,
    )
    assert out["model"] == "parallel_depth_over_ccz_paths_v1"
    assert out["effective_layer_time_microseconds"] == pytest.approx(10.0)
    assert out["ccz_factory_count"] == 2
    expected_wall_us = 1_000_000.0 * 10.0 / 2.0
    assert out["wall_clock_microseconds"] == pytest.approx(expected_wall_us)
    assert out["wall_clock_days"] == pytest.approx(expected_wall_us / 1e6 / 86400.0)


def test_build_parallel_depth_schedule_v1_not_reaction_limited_uses_cycle_only() -> None:
    out = build_parallel_depth_schedule_v1(
        abstract_measurement_depth_layers=100.0,
        surface_code_cycle_microseconds=2.0,
        classical_reaction_microseconds=99.0,
        ccz_factory_count=1,
        reaction_limited=False,
    )
    assert out["effective_layer_time_microseconds"] == pytest.approx(2.0)
    assert out["wall_clock_microseconds"] == pytest.approx(200.0)
