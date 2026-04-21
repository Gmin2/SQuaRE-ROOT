"""Unit tests for ``square.report_magic_throughput``."""

from __future__ import annotations

import math

import pytest
from square.report_magic_throughput import (
    MAGIC_SUPPLY_DEPTH_LAYERS_PER_S_PER_FACTORY_KEY,
    compute_magic_throughput_dashboard_fields,
)


def test_magic_throughput_adequate_when_supply_exceeds_demand() -> None:
    w: list[str] = []
    depth = 1e6
    wall_days = 1.0
    time_s = wall_days * 86400.0
    demand = depth / time_s
    n_ccz = 4
    rate = demand / float(n_ccz) * 2.0
    out = compute_magic_throughput_dashboard_fields(
        magic={MAGIC_SUPPLY_DEPTH_LAYERS_PER_S_PER_FACTORY_KEY: {"value": rate, "unit": "x"}},
        ccz_factory_count=n_ccz,
        evaluated={"abstract_measurement_depth_layers": {"value": depth}},
        schedule_model_v1={"wall_clock_days": wall_days},
        naive_serial_timing=None,
        warnings=w,
    )
    assert out["magic_supply_adequate"] is True
    assert out["magic_limited_runtime_multiplier"] == pytest.approx(1.0)
    assert not any("supply proxy" in x for x in w)


def test_magic_throughput_inadequate_sets_multiplier_and_warning() -> None:
    w: list[str] = []
    depth = 1e9
    wall_days = 1.0
    time_s = wall_days * 86400.0
    demand = depth / time_s
    n_ccz = 2
    rate = demand / float(n_ccz) * 0.5
    out = compute_magic_throughput_dashboard_fields(
        magic={MAGIC_SUPPLY_DEPTH_LAYERS_PER_S_PER_FACTORY_KEY: {"value": rate, "unit": "x"}},
        ccz_factory_count=n_ccz,
        evaluated={"abstract_measurement_depth_layers": {"value": depth}},
        schedule_model_v1={"wall_clock_days": wall_days},
        naive_serial_timing=None,
        warnings=w,
    )
    assert out["magic_supply_adequate"] is False
    supply = float(n_ccz) * float(rate)
    assert out["magic_limited_runtime_multiplier"] == pytest.approx(min(1_000_000.0, demand / supply))
    assert any("supply proxy" in x for x in w)


def test_magic_throughput_skipped_without_rate() -> None:
    w: list[str] = []
    out = compute_magic_throughput_dashboard_fields(
        magic={},
        ccz_factory_count=1,
        evaluated={"abstract_measurement_depth_layers": {"value": 1e6}},
        schedule_model_v1={"wall_clock_days": 1.0},
        naive_serial_timing=None,
        warnings=w,
    )
    assert out["magic_supply_adequate"] is None
    assert out["magic_limited_runtime_multiplier"] is None
    assert any(MAGIC_SUPPLY_DEPTH_LAYERS_PER_S_PER_FACTORY_KEY in x for x in w)


def test_magic_throughput_uses_naive_serial_when_no_schedule_wall() -> None:
    w: list[str] = []
    depth = 8.64e11
    serial_days = 10.0
    out = compute_magic_throughput_dashboard_fields(
        magic={MAGIC_SUPPLY_DEPTH_LAYERS_PER_S_PER_FACTORY_KEY: {"value": 1000.0, "unit": "x"}},
        ccz_factory_count=10,
        evaluated={"abstract_measurement_depth_layers": {"value": depth}},
        schedule_model_v1={"wall_clock_days": None},
        naive_serial_timing={"serial_time_days": serial_days},
        warnings=w,
    )
    demand = depth / (serial_days * 86400.0)
    supply = 10.0 * 1000.0
    assert out["magic_supply_adequate"] == (demand <= supply * (1.0 + 1e-12))
    assert out["magic_limited_runtime_multiplier"] == pytest.approx(
        1.0 if demand <= supply else min(1_000_000.0, demand / max(supply, 1e-12))
    )
    assert math.isfinite(float(out["magic_limited_runtime_multiplier"] or 0.0))
