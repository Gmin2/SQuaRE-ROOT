"""Tests for ``square.report_dashboard``."""

from __future__ import annotations

import pytest
from square.report_dashboard import (
    build_dashboard_fields,
    compute_logical_failure_proxy_union_depth_phenomenological,
)
from square.report_magic_aux import DEFAULT_MAGIC_AUX_T_FACTORY_DASHBOARD


def test_build_dashboard_fields_includes_ecdlp_keys_when_block_present() -> None:
    dash = build_dashboard_fields(
        ccz_count=None,
        factory_param_key=None,
        table2_pinned_source_parameter=None,
        table2_row_layout_descriptor=None,
        phys_key=None,
        rsa2048_phys=None,
        mega_key=None,
        rsa2048_megaqd=None,
        wall_key=None,
        rsa2048_wall_days=None,
        naive_serial_timing=None,
        evaluated={},
        toffoli_b=None,
        megaqd=None,
        patch_physical_per_logical=None,
        approx_data_physical=None,
        magic_aux_t_factory_dashboard=dict(DEFAULT_MAGIC_AUX_T_FACTORY_DASHBOARD),
        d_resolved=None,
        qec_distance_resolution_mode="heuristic_union_bound",
        derived_non_data_overhead_physical_qubits=None,
        factory_footprint_from_yaml=None,
        schedule_model_v1=None,
        schedule_calibration=None,
        ecdlp_block_for_metrics={
            "variant": "low_toffoli_variant",
            "toffoli_gates_upper_bound": 1e6,
        },
        logical_fault_model={"logical_error_rate_per_cycle": None},
        warnings=[],
        magic={},
    )
    assert dash["ecdlp_active"] is True
    assert dash["ecdlp_variant"] == "low_toffoli_variant"
    assert dash["ecdlp_toffoli_gates_upper_bound"] == 1e6
    assert dash.get("magic_supply_adequate") is None
    assert dash.get("magic_limited_runtime_multiplier") is None


def test_compute_logical_failure_proxy_union_depth_phenomenological() -> None:
    w: list[str] = []
    v = compute_logical_failure_proxy_union_depth_phenomenological(
        logical_fault_model={"logical_error_rate_per_cycle": 1e-6},
        evaluated={"abstract_measurement_depth_layers": {"value": 2e6}},
        warnings=w,
    )
    assert v == pytest.approx(min(1.0, 2.0))
    assert not w

    w2: list[str] = []
    v2 = compute_logical_failure_proxy_union_depth_phenomenological(
        logical_fault_model={"logical_error_rate_per_cycle": 1e-6},
        evaluated={"abstract_measurement_depth_layers": {"value": 2e9}},
        warnings=w2,
    )
    assert v2 == 1.0


def test_compute_logical_failure_proxy_omitted_without_p_l() -> None:
    w: list[str] = []
    assert (
        compute_logical_failure_proxy_union_depth_phenomenological(
            logical_fault_model={"logical_error_rate_per_cycle": None},
            evaluated={"abstract_measurement_depth_layers": {"value": 100.0}},
            warnings=w,
        )
        is None
    )
    assert w
