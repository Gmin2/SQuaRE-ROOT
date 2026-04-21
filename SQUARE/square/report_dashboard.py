"""Top-level ``dashboard`` fields for scenario JSON report."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from square.report_magic_throughput import compute_magic_throughput_dashboard_fields
from square.yaml_numeric import read_evaluated_abstract_measurement_depth_layers

# ``depth_layers=...`` uses this default so ``None`` means "caller already evaluated depth" (no re-read).
_UNSET_DEPTH: object = object()


def compute_logical_failure_probability_union_depth_proxy(
    *,
    logical_fault_model: Mapping[str, Any],
    evaluated: Mapping[str, Any],
    warnings: list[str],
    depth_layers: float | None | object = _UNSET_DEPTH,
) -> float | None:
    """
    Conservative union-style logical failure proxy ``min(1, D × p_L)``.

    Optional ``depth_layers`` avoids a second parse when the caller already read ``D`` via
    :func:`square.yaml_numeric.read_evaluated_abstract_measurement_depth_layers`.

    ``D`` is ``algorithm_metrics.evaluated.abstract_measurement_depth_layers.value`` (logical depth proxy).
    ``p_L`` is ``logical_fault_model.logical_error_rate_per_cycle`` (phenomenological per-cycle rate).

    This is **not** a calibrated fault path or decoder simulation; omit when inputs are missing or ``p_L``
    is absent (e.g. ``p_phys ≥ p_th``).
    """
    p_l_raw = logical_fault_model.get("logical_error_rate_per_cycle")
    if p_l_raw is None or not isinstance(p_l_raw, (int, float)):
        warnings.append(
            "dashboard.logical_failure_probability_union_depth_proxy omitted: need numeric "
            "logical_fault_model.logical_error_rate_per_cycle (phenomenological p_L)."
        )
        return None
    p_l = float(p_l_raw)
    if p_l <= 0.0:
        warnings.append(
            "dashboard.logical_failure_probability_union_depth_proxy omitted: "
            "logical_fault_model.logical_error_rate_per_cycle must be > 0."
        )
        return None

    if depth_layers is _UNSET_DEPTH:
        d_layers = read_evaluated_abstract_measurement_depth_layers(
            evaluated,
            warnings,
            context="dashboard.logical_failure_probability_union_depth_proxy",
        )
    else:
        d_layers = depth_layers  # type: ignore[assignment]
    if d_layers is None:
        return None

    return min(1.0, d_layers * p_l)


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
    logical_fault_model: Mapping[str, Any],
    warnings: list[str],
    magic: Mapping[str, Any],
) -> dict[str, Any]:
    """
    Assemble the ``dashboard`` object from already-derived report scalars.

    ECDLP-specific keys are merged from ``ecdlp_block_for_metrics`` when present.

    ``logical_failure_probability_union_depth_proxy`` uses the same ``p_L`` and depth proxy as OSRE-style
    notes; see :func:`compute_logical_failure_probability_union_depth_proxy`.

    ``magic_supply_adequate`` / ``magic_limited_runtime_multiplier`` come from
    :func:`square.report_magic_throughput.compute_magic_throughput_dashboard_fields`.
    """
    depth_layers = read_evaluated_abstract_measurement_depth_layers(
        evaluated,
        warnings,
        context="dashboard.abstract_measurement_depth_layers",
    )
    fail_p = compute_logical_failure_probability_union_depth_proxy(
        logical_fault_model=logical_fault_model,
        evaluated=evaluated,
        warnings=warnings,
        depth_layers=depth_layers,
    )
    magic_tp = compute_magic_throughput_dashboard_fields(
        magic=magic,
        ccz_factory_count=ccz_count,
        evaluated=evaluated,
        schedule_model_v1=schedule_model_v1,
        naive_serial_timing=naive_serial_timing,
        warnings=warnings,
        depth_layers=depth_layers,
    )
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
        "logical_failure_probability_union_depth_proxy": fail_p,
    }
    base.update(magic_tp)
    base.update(_ecdlp_dashboard_extras(ecdlp_block_for_metrics))
    return base
