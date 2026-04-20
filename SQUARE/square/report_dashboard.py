"""Top-level ``dashboard`` fields for scenario JSON report."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _ecdlp_dashboard_extras(ecdlp_block: dict[str, Any] | None) -> dict[str, Any]:
    if ecdlp_block is None:
        return {}
    return {
        "ecdlp_active": True,
        "ecdlp_variant": ecdlp_block.get("variant"),
        "ecdlp_toffoli_gates_upper_bound": ecdlp_block.get("toffoli_gates_upper_bound"),
        "ecdlp_paper_headline_physical_qubits_upper_bound": ecdlp_block.get(
            "paper_headline_physical_qubits_upper_bound_narrative"
        ),
    }


def build_dashboard_fields(
    *,
    ccz_count: int | None,
    factory_param_key: str | None,
    table2_pinned_source_parameter: str | None,
    table2_row_layout_descriptor: str | None,
    phys_key: str | None,
    rsa2048_phys: float | None,
    mega_key: str | None,
    rsa2048_megaqd: float | None,
    wall_key: str | None,
    rsa2048_wall_days: float | None,
    naive_serial_timing: Mapping[str, Any] | None,
    evaluated: Mapping[str, Any],
    toffoli_b: float | None,
    megaqd: float | None,
    patch_physical_per_logical: float | None,
    approx_data_physical: float | None,
    t_fallback_recommended: bool,
    t_transition: int | None,
    d_resolved: int | None,
    qec_distance_resolution_mode: Any,
    derived_non_data_overhead_physical_qubits: float | None,
    factory_footprint_from_yaml: float | None,
    schedule_model_v1: Mapping[str, Any] | None,
    schedule_calibration: Mapping[str, Any] | None,
    ecdlp_block_for_metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Assemble the ``dashboard`` object from already-derived report scalars.

    ECDLP-specific keys are merged from ``ecdlp_block_for_metrics`` when present.
    """
    base: dict[str, Any] = {
        "ccz_factory_count": ccz_count,
        "ccz_factory_parameter_key": factory_param_key,
        "table2_pinned_source_parameter": table2_pinned_source_parameter,
        "table2_pinned_row_layout_descriptor": table2_row_layout_descriptor,
        "rsa_2048_reported_physical_qubits_millions_key": phys_key,
        "reported_rsa2048_physical_qubits_millions": rsa2048_phys,
        "rsa_2048_reported_megaqubit_days_key": mega_key,
        "reported_rsa2048_megaqubit_days": rsa2048_megaqd,
        "rsa_2048_reported_wall_clock_days_key": wall_key,
        "reported_rsa2048_wall_clock_days": rsa2048_wall_days,
        "naive_serial_time_days_from_depth_times_cycle": naive_serial_timing["serial_time_days"]
        if naive_serial_timing
        else None,
        "logical_qubits_at_n": evaluated.get("abstract_logical_qubits", {}).get("value")
        if isinstance(evaluated.get("abstract_logical_qubits"), dict)
        else None,
        "toffoli_plus_t_halves_billions_at_n": toffoli_b,
        "minimum_spacetime_volume_megaqubitdays_at_n": megaqd,
        "logical_qubit_physical_qubits_if_distance_d": patch_physical_per_logical,
        "approximate_data_plane_physical_qubits": approx_data_physical,
        "t_factory_fallback_recommended": t_fallback_recommended,
        "t_factory_transition_modulus_bits_order_of_magnitude": t_transition,
        "code_distance_d": d_resolved,
        "qec_distance_resolution_mode": qec_distance_resolution_mode,
        "derived_non_data_overhead_physical_qubits": derived_non_data_overhead_physical_qubits,
        "factory_footprint_physical_qubits_from_yaml": factory_footprint_from_yaml,
        "schedule_model_v1_wall_clock_days": schedule_model_v1.get("wall_clock_days")
        if schedule_model_v1
        else None,
        "schedule_calibration_ratio_table2_over_model_v1": schedule_calibration.get("ratio_table2_pinned_over_model_v1")
        if schedule_calibration
        else None,
    }
    base.update(_ecdlp_dashboard_extras(ecdlp_block_for_metrics))
    return base
