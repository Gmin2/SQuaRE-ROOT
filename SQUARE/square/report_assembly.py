"""Terminal report dict assembly (contract shell only, no domain orchestration)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any


def engine_version() -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version

        return version("square")
    except PackageNotFoundError:
        return "0.0.0+unknown"


def assemble_report_shell(
    *,
    report_contract_version: int,
    warnings: list[str],
    scenario: Mapping[str, Any],
    target: Mapping[str, Any],
    table2_reference: dict[str, Any] | None,
    sources: Mapping[str, Any],
    layers: dict[str, Any],
    algorithm_metrics: dict[str, Any],
    qec_overhead: dict[str, Any],
    logical_fault_model: dict[str, Any],
    physical_rollup: dict[str, Any],
    physical_layer: dict[str, Any],
    system_metrics: dict[str, Any],
    parameter_sensitivity: dict[str, Any],
    qec_distance_resolution: dict[str, Any],
    layout_estimate: dict[str, Any] | None,
    layout_optimization: dict[str, Any] | None,
    timing: dict[str, Any],
    dashboard: dict[str, Any],
) -> dict[str, Any]:
    """
    Build the top-level scenario report mapping from precomputed sections.

    Keeps the output contract in one place so orchestration code only produces blocks.
    """
    return {
        "report_contract_version": report_contract_version,
        "engine": {"name": "square", "version": engine_version()},
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "warnings": warnings,
        "scenario": dict(scenario),
        "target": dict(target),
        "table2_reference": table2_reference,
        "sources": sources,
        "layers": layers,
        "algorithm_metrics": algorithm_metrics,
        "qec_overhead": qec_overhead,
        "logical_fault_model": logical_fault_model,
        "physical_rollup": physical_rollup,
        "physical_layer": physical_layer,
        "system_metrics": system_metrics,
        "parameter_sensitivity": parameter_sensitivity,
        "qec_distance_resolution": qec_distance_resolution,
        "layout_estimate": layout_estimate,
        "layout_optimization": layout_optimization,
        "timing": timing,
        "dashboard": dashboard,
    }
