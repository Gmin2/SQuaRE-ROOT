"""Magic-state throughput proxy: demand vs optional per-factory supply rate (OSRE memo alignment)."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from square.yaml_numeric import read_parameter_entry_float

# Optional magic YAML: per-CCZ-factory supply of abstract measurement-depth equivalents per second.
# When absent, ``magic_supply_adequate`` / ``magic_limited_runtime_multiplier`` stay ``null`` (not modeled).
MAGIC_SUPPLY_DEPTH_LAYERS_PER_S_PER_FACTORY_KEY = (
    "ccz_factory_supply_abstract_measurement_depth_layers_per_second_per_factory"
)

_MAX_RUNTIME_MULTIPLIER = 1_000_000.0


def compute_magic_throughput_dashboard_fields(
    *,
    magic: Mapping[str, Any],
    ccz_factory_count: int | None,
    evaluated: Mapping[str, Any],
    schedule_model_v1: Mapping[str, Any] | None,
    naive_serial_timing: Mapping[str, Any] | None,
    warnings: list[str],
) -> dict[str, Any]:
    """
    Compare abstract logical-depth demand rate to an optional magic supply rate.

    **Demand (proxy):** ``D / T`` where ``D`` = ``evaluated.abstract_measurement_depth_layers.value`` and
    ``T`` is wall-clock seconds from ``timing.schedule_model_v1.wall_clock_days`` when present, else
    ``timing.naive_serial_from_measurement_depth.serial_time_days`` (serial depth×cycle proxy).

    **Supply (proxy):** ``N_ccz × R`` with ``R`` from optional magic ``parameter_entry``
    :data:`MAGIC_SUPPLY_DEPTH_LAYERS_PER_S_PER_FACTORY_KEY` (per-factory), and ``N_ccz`` from the scenario
    Table-2 CCZ count when set, else ``schedule_model_v1.ccz_factory_count`` when the schedule block exists.

    **Outputs:** ``magic_supply_adequate`` (``true`` / ``false`` / ``null``) and ``magic_limited_runtime_multiplier``
    (``max(1, demand/supply)`` capped, or ``null`` when not computed). These do **not** rewrite schedule or
    naive timing blocks; they are feasibility flags for external timelines.
    """
    out: dict[str, Any] = {"magic_supply_adequate": None, "magic_limited_runtime_multiplier": None}

    depth_entry = evaluated.get("abstract_measurement_depth_layers")
    depth_val: float | None = None
    if isinstance(depth_entry, dict) and depth_entry.get("value") is not None:
        try:
            depth_val = float(depth_entry["value"])
        except (TypeError, ValueError):
            depth_val = None
    if depth_val is None or depth_val < 0.0 or not math.isfinite(depth_val):
        warnings.append(
            "dashboard.magic_throughput: skipped; need finite evaluated.abstract_measurement_depth_layers.value."
        )
        return out

    wall_days: float | None = None
    if isinstance(schedule_model_v1, dict) and schedule_model_v1.get("wall_clock_days") is not None:
        try:
            wall_days = float(schedule_model_v1["wall_clock_days"])
        except (TypeError, ValueError):
            wall_days = None
    if wall_days is None and isinstance(naive_serial_timing, dict):
        raw = naive_serial_timing.get("serial_time_days")
        if raw is not None:
            try:
                wall_days = float(raw)
            except (TypeError, ValueError):
                wall_days = None
    if wall_days is None or wall_days <= 0.0 or not math.isfinite(wall_days):
        warnings.append(
            "dashboard.magic_throughput: skipped; need positive wall-clock days from schedule_model_v1 "
            "or naive_serial_from_measurement_depth."
        )
        return out

    time_s = wall_days * 86400.0
    demand_lps = float(depth_val) / time_s
    if demand_lps <= 0.0 or not math.isfinite(demand_lps):
        warnings.append("dashboard.magic_throughput: skipped; non-positive demand rate.")
        return out

    n_ccz: int | None = None
    if ccz_factory_count is not None:
        try:
            n_ccz = int(ccz_factory_count)
        except (TypeError, ValueError):
            n_ccz = None
    if n_ccz is None and isinstance(schedule_model_v1, dict):
        raw_c = schedule_model_v1.get("ccz_factory_count")
        if raw_c is not None:
            try:
                n_ccz = int(raw_c)
            except (TypeError, ValueError):
                n_ccz = None
    if n_ccz is None or n_ccz < 1:
        warnings.append(
            "dashboard.magic_throughput: skipped; need positive ccz_factory_count (Table 2 scenario row) "
            "or schedule_model_v1.ccz_factory_count."
        )
        return out

    rate = read_parameter_entry_float(
        magic,
        MAGIC_SUPPLY_DEPTH_LAYERS_PER_S_PER_FACTORY_KEY,
        warnings,
        context="paths.magic",
    )
    if rate is None or rate <= 0.0 or not math.isfinite(float(rate)):
        warnings.append(
            f"dashboard.magic_throughput: skipped; magic YAML missing or invalid "
            f"{MAGIC_SUPPLY_DEPTH_LAYERS_PER_S_PER_FACTORY_KEY!r} (per-factory supply proxy)."
        )
        return out

    supply_lps = float(n_ccz) * float(rate)
    if supply_lps <= 0.0:
        return out

    eps = 1e-12
    adequate = demand_lps <= supply_lps * (1.0 + eps)
    mult = 1.0 if adequate else min(_MAX_RUNTIME_MULTIPLIER, demand_lps / max(supply_lps, eps))
    out["magic_supply_adequate"] = bool(adequate)
    out["magic_limited_runtime_multiplier"] = float(mult)
    if not adequate:
        warnings.append(
            "dashboard.magic_throughput: supply proxy (N_ccz × per-factory rate) is below demand proxy "
            f"(D/T); magic_limited_runtime_multiplier={mult:.4g} scales notional wall-clock vs this OSRE check "
            "(see docs/output-contract.md, dashboard section)."
        )
    return out
