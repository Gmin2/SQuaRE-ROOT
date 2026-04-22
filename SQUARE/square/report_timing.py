"""Timing subsection of scenario report: naive serial, schedule v1, Table 2 pins."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from square.schedule_heuristic import (
    build_parallel_depth_schedule_v1,
    infer_reaction_limited_from_scenario,
)


@dataclass(frozen=True)
class TimingBuildResult:
    """Return value of :func:`build_timing_section`."""

    timing_block: dict[str, Any]
    naive_serial_timing: dict[str, Any] | None
    schedule_model_v1: dict[str, Any] | None
    schedule_calibration: dict[str, Any] | None


def build_timing_section(
    *,
    evaluated: Mapping[str, Any],
    modality: Mapping[str, Any],
    scenario: Mapping[str, Any],
    table2_block: Any,
    table2_rsa2048_rows_key: str,
    ecdlp_block_for_metrics: dict[str, Any] | None,
    early_pins: Mapping[str, Any],
    warnings: list[str],
) -> TimingBuildResult:
    """
    Build ``timing`` block: naive serial from depth×cycle, optional schedule v1 + calibration, Table 2 timing pin.
    """
    ccz_count = early_pins.get("ccz_count")
    rsa2048_phys = early_pins.get("rsa2048_phys")
    phys_key = early_pins.get("phys_key")
    rsa2048_megaqd = early_pins.get("rsa2048_megaqd")
    mega_key = early_pins.get("mega_key")
    rsa2048_wall_days = early_pins.get("rsa2048_wall_days")
    wall_key = early_pins.get("wall_key")
    factory_param_key = early_pins.get("factory_param_key")
    table2_row_layout_descriptor = early_pins.get("table2_row_layout_descriptor")

    naive_serial_timing: dict[str, Any] | None = None
    depth_layers = evaluated.get("abstract_measurement_depth_layers")
    cycle_entry = modality.get("surface_code_cycle_time")
    if isinstance(depth_layers, dict) and depth_layers.get("value") is not None:
        try:
            depth_val = float(depth_layers["value"])
        except (TypeError, ValueError):
            depth_val = None
        if depth_val is not None and isinstance(cycle_entry, dict) and cycle_entry.get("value") is not None:
            try:
                cycle_us = float(cycle_entry["value"])
            except (TypeError, ValueError):
                cycle_us = None
            if cycle_us is not None:
                serial_us = depth_val * cycle_us
                serial_days = serial_us / (1e6 * 86400.0)
                depth_src = (
                    "ecdlp_logical_resource_envelopes_secp256k1_proxy"
                    if ecdlp_block_for_metrics is not None
                    else "abstract_measurement_depth_formula"
                )
                naive_serial_timing = {
                    "abstract_measurement_depth_layers": depth_val,
                    "surface_code_cycle_time_microseconds": cycle_us,
                    "serial_time_microseconds": serial_us,
                    "serial_time_days": serial_days,
                    "provenance": "computed_from_measurement_depth_times_surface_cycle",
                    "source_parameters": {
                        "depth": depth_src,
                        "cycle": "surface_code_cycle_time",
                    },
                }
                warnings.append(
                    "naive_serial_time_days = abstract_measurement_depth_layers × surface_code_cycle_time; "
                    "assumes one code cycle per abstract layer, no parallelism, no reaction/distillation limits — "
                    "not comparable to Table 2 wall-clock without the paper’s full schedule."
                )

    table2_row_text: str | None = None
    if isinstance(table2_block, dict) and table2_block.get("value") is not None:
        table2_row_text = str(table2_block.get("value"))
    schedule_model_v1: dict[str, Any] | None = None
    schedule_calibration: dict[str, Any] | None = None
    reaction_entry = modality.get("classical_control_reaction_time")
    reaction_us: float | None = None
    if isinstance(reaction_entry, dict) and reaction_entry.get("value") is not None:
        try:
            reaction_us = float(reaction_entry["value"])
        except (TypeError, ValueError):
            reaction_us = None

    if (
        isinstance(depth_layers, dict)
        and depth_layers.get("value") is not None
        and isinstance(cycle_entry, dict)
        and cycle_entry.get("value") is not None
        and reaction_us is not None
        and ccz_count is not None
    ):
        try:
            depth_val_s = float(depth_layers["value"])
            cycle_us_s = float(cycle_entry["value"])
        except (TypeError, ValueError):
            depth_val_s = None
            cycle_us_s = None
        if depth_val_s is not None and cycle_us_s is not None:
            rlim, rsrc = infer_reaction_limited_from_scenario(
                scenario,
                table2_row_value=table2_row_text,
                factory_parameter_key=factory_param_key,
            )
            schedule_model_v1 = build_parallel_depth_schedule_v1(
                abstract_measurement_depth_layers=depth_val_s,
                surface_code_cycle_microseconds=cycle_us_s,
                classical_reaction_microseconds=reaction_us,
                ccz_factory_count=int(ccz_count),
                reaction_limited=rlim,
            )
            schedule_model_v1["reaction_limited_inferred_from"] = rsrc
            warnings.append(
                "schedule_model_v1 uses depth/(CCZ factories) with an effective layer time; "
                "it is a coarse bound, not the paper’s compiled schedule."
            )
            if naive_serial_timing and naive_serial_timing.get("serial_time_days") is not None:
                naive_d = float(naive_serial_timing["serial_time_days"])
                model_d = float(schedule_model_v1["wall_clock_days"])
                schedule_calibration = {
                    "naive_serial_time_days": naive_d,
                    "schedule_model_v1_wall_clock_days": model_d,
                    "ratio_naive_serial_over_model_v1": naive_d / model_d if model_d > 0 else None,
                    "provenance": "ratio_of_estimates",
                }
            if rsa2048_wall_days is not None and schedule_model_v1.get("wall_clock_days") is not None:
                pinned_d = float(rsa2048_wall_days)
                model_d2 = float(schedule_model_v1["wall_clock_days"])
                schedule_calibration = schedule_calibration or {}
                schedule_calibration.update(
                    {
                        "table2_pinned_wall_clock_days": pinned_d,
                        "ratio_table2_pinned_over_model_v1": pinned_d / model_d2 if model_d2 > 0 else None,
                    }
                )

    reported_table2_timing: dict[str, Any] | None = None
    if ccz_count is not None:
        reported_table2_timing = {
            "ccz_factory_count": ccz_count,
            "physical_qubits_millions": rsa2048_phys,
            "physical_qubits_millions_key": phys_key,
            "megaqubit_days": rsa2048_megaqd,
            "megaqubit_days_key": mega_key if rsa2048_megaqd is not None else None,
            "wall_clock_days": rsa2048_wall_days,
            "wall_clock_days_key": wall_key if rsa2048_wall_days is not None else None,
            "source_parameter": table2_rsa2048_rows_key,
            "layout_descriptor": table2_row_layout_descriptor,
            "provenance": "pinned_in_magic_yaml_table2",
        }

    timing_block: dict[str, Any] = {
        "reported_table2_pinned": reported_table2_timing,
        "naive_serial_from_measurement_depth": naive_serial_timing,
        "schedule_model_v1": schedule_model_v1,
        "schedule_calibration": schedule_calibration,
    }
    return TimingBuildResult(
        timing_block=timing_block,
        naive_serial_timing=naive_serial_timing,
        schedule_model_v1=schedule_model_v1,
        schedule_calibration=schedule_calibration,
    )
