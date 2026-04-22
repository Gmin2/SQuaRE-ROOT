"""Physical rollup and layout estimate proxies (Table 2 vs data plane, factory footprint)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


def _magic_float_by_key(magic: Mapping[str, Any], key: str) -> float | None:
    entry = magic.get(key)
    if not isinstance(entry, dict) or entry.get("value") is None:
        return None
    try:
        return float(entry["value"])
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class PhysicalRollupLayoutResult:
    """Outputs of :func:`build_physical_rollup_and_layout_estimate`."""

    logical_qubits_val: float | None
    approx_data_physical: float | None
    reported_total_physical_qubits: float | None
    derived_non_data_overhead_physical_qubits: float | None
    per_ccz_factory_qubits: float | None
    factory_footprint_from_yaml: float | None
    layout_estimate: dict[str, Any]
    physical_rollup: dict[str, Any]


def build_physical_rollup_and_layout_estimate(
    *,
    magic: Mapping[str, Any],
    evaluated: Mapping[str, Any],
    early_pins: Mapping[str, Any],
    d_resolved: int | None,
    patch_physical_per_logical: float | None,
    qec_patch_status: str,
    warnings: list[str],
) -> PhysicalRollupLayoutResult:
    """
    Derive logical qubit count, data-plane proxy, Table-2 rollup, factory footprint, layout estimate dict, physical_rollup.
    """
    rsa2048_phys = early_pins.get("rsa2048_phys")
    ccz_count = early_pins.get("ccz_count")

    logical_qubits_val: float | None = None
    abs_lq = evaluated.get("abstract_logical_qubits")
    if isinstance(abs_lq, dict) and abs_lq.get("value") is not None:
        try:
            logical_qubits_val = float(abs_lq["value"])
        except (TypeError, ValueError):
            logical_qubits_val = None

    approx_data_physical: float | None = None
    if logical_qubits_val is not None and patch_physical_per_logical is not None:
        approx_data_physical = logical_qubits_val * patch_physical_per_logical
        warnings.append(
            "approximate_data_plane_physical_qubits = abstract_logical_qubits × physical_qubits_per_logical; "
            "excludes magic-state factories, routing, classical control footprint, and other non-data overhead."
        )

    reported_total_physical_qubits: float | None = None
    if rsa2048_phys is not None:
        reported_total_physical_qubits = float(rsa2048_phys) * 1e6

    derived_non_data_overhead_physical_qubits: float | None = None
    if reported_total_physical_qubits is not None and approx_data_physical is not None:
        derived_non_data_overhead_physical_qubits = max(0.0, reported_total_physical_qubits - approx_data_physical)
        warnings.append(
            "derived_non_data_overhead_physical_qubits = Table-2-pinned total qubits minus naive data-plane product; "
            "attributes remainder to factories, routing, distillation, control, etc. without splitting them."
        )

    per_ccz_factory_qubits = _magic_float_by_key(magic, "physical_qubits_per_ccz_factory_approximate")
    factory_footprint_from_yaml: float | None = None
    if ccz_count is not None and per_ccz_factory_qubits is not None:
        factory_footprint_from_yaml = float(ccz_count) * float(per_ccz_factory_qubits)

    layout_estimate: dict[str, Any] = {
        "approximate_data_plane_physical_qubits": approx_data_physical,
        "reported_end_to_end_physical_qubits": reported_total_physical_qubits,
        "derived_non_data_overhead_physical_qubits": derived_non_data_overhead_physical_qubits,
        "factory_footprint_physical_qubits_from_yaml": factory_footprint_from_yaml,
        "physical_qubits_per_ccz_factory_approximate_key": "physical_qubits_per_ccz_factory_approximate"
        if per_ccz_factory_qubits is not None
        else None,
        "provenance": "layout_proxy_v1",
    }

    physical_rollup: dict[str, Any] = {
        "code_distance_d": d_resolved,
        "physical_qubits_per_logical": patch_physical_per_logical,
        "abstract_logical_qubits_at_n": logical_qubits_val,
        "approximate_data_plane_physical_qubits": approx_data_physical,
        "patch_formula_status": qec_patch_status,
    }

    return PhysicalRollupLayoutResult(
        logical_qubits_val=logical_qubits_val,
        approx_data_physical=approx_data_physical,
        reported_total_physical_qubits=reported_total_physical_qubits,
        derived_non_data_overhead_physical_qubits=derived_non_data_overhead_physical_qubits,
        per_ccz_factory_qubits=per_ccz_factory_qubits,
        factory_footprint_from_yaml=factory_footprint_from_yaml,
        layout_estimate=layout_estimate,
        physical_rollup=physical_rollup,
    )
