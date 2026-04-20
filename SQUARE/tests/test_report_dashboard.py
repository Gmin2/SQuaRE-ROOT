"""Tests for ``square.report_dashboard``."""

from __future__ import annotations

from square.report_dashboard import build_dashboard_fields


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
        t_fallback_recommended=False,
        t_transition=None,
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
    )
    assert dash["ecdlp_active"] is True
    assert dash["ecdlp_variant"] == "low_toffoli_variant"
    assert dash["ecdlp_toffoli_gates_upper_bound"] == 1e6
