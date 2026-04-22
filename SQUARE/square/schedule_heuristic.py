"""
Simple schedule heuristics and calibration against pinned wall-clock values.

These models are intentionally crude; see report warnings and output contract non-goals.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def infer_reaction_limited_from_scenario(
    scenario: Mapping[str, Any],
    *,
    table2_row_value: str | None,
    factory_parameter_key: str | None,
) -> tuple[bool, str]:
    """
    Infer whether reaction-time (vs raw cycle time) should dominate layer latency.

    Explicit ``schedule.reaction_limited`` wins; else distillation-limited rows in the
    Gidney & Ekerå naming convention disable reaction limiting for the simple model.
    """
    sched = scenario.get("schedule")
    if isinstance(sched, dict) and "reaction_limited" in sched:
        raw = sched.get("reaction_limited")
        return bool(raw), "scenario.schedule.reaction_limited"

    blob = " ".join(
        filter(
            None,
            [
                table2_row_value or "",
                factory_parameter_key or "",
            ],
        )
    ).lower()
    if "distillation" in blob:
        return False, "inferred_from_table2_or_factory_key(distillation_limited)"
    return True, "default_reaction_limited_unless_distillation_in_row_or_factory_key"


def build_parallel_depth_schedule_v1(
    *,
    abstract_measurement_depth_layers: float,
    surface_code_cycle_microseconds: float,
    classical_reaction_microseconds: float,
    ccz_factory_count: int,
    reaction_limited: bool,
) -> dict[str, Any]:
    """
    Wall-clock proxy: ``depth * effective_layer_time / max(1, ccz_count)``.

    ``effective_layer_time = max(cycle, reaction)`` when reaction_limited else cycle.
    """
    ccz = max(1, int(ccz_factory_count))
    eff = (
        max(float(surface_code_cycle_microseconds), float(classical_reaction_microseconds))
        if reaction_limited
        else float(surface_code_cycle_microseconds)
    )
    serial_us = float(abstract_measurement_depth_layers) * eff
    wall_us = serial_us / ccz
    wall_days = wall_us / 1e6 / 86400.0
    return {
        "model": "parallel_depth_over_ccz_paths_v1",
        "reaction_limited": reaction_limited,
        "surface_code_cycle_time_microseconds": float(surface_code_cycle_microseconds),
        "classical_control_reaction_time_microseconds": float(classical_reaction_microseconds),
        "effective_layer_time_microseconds": eff,
        "abstract_measurement_depth_layers": float(abstract_measurement_depth_layers),
        "ccz_factory_count": ccz,
        "wall_clock_microseconds": wall_us,
        "wall_clock_days": wall_days,
        "provenance": "heuristic_schedule_v1",
    }
