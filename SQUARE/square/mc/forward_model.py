"""Deterministic forward model y = f(theta, scenario) for Monte Carlo."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from square.loader import ScenarioBundle
from square.mc.overrides import apply_numeric_overrides
from square.report import build_scenario_report

# Dashboard keys (metric_name, dashboard_field) extracted into MC metric dict keys.
MC_DASHBOARD_METRIC_FIELDS: tuple[tuple[str, str], ...] = (
    ("naive_serial_time_days", "naive_serial_time_days_from_depth_times_cycle"),
    ("code_distance_d", "code_distance_d"),
    ("approximate_data_plane_physical_qubits", "approximate_data_plane_physical_qubits"),
    ("logical_qubits_at_n", "logical_qubits_at_n"),
)

MC_ECDLP_METRIC_KEY = "ecdlp_toffoli_gates_upper_bound"


@dataclass(frozen=True)
class ForwardModelResult:
    numeric_overrides: dict[str, float]
    metrics: dict[str, float | None]
    report: dict[str, Any] | None


def extract_default_mc_metrics(report: Mapping[str, Any]) -> dict[str, float | None]:
    dash = report.get("dashboard")
    if not isinstance(dash, dict):
        return {metric_key: None for metric_key, _ in MC_DASHBOARD_METRIC_FIELDS}

    out: dict[str, float | None] = {
        metric_key: _as_float(dash.get(dash_key)) for metric_key, dash_key in MC_DASHBOARD_METRIC_FIELDS
    }
    am = report.get("algorithm_metrics")
    if isinstance(am, dict) and am.get("ecdlp"):
        e = am["ecdlp"]
        if isinstance(e, dict):
            out[MC_ECDLP_METRIC_KEY] = _as_float(e.get("toffoli_gates_upper_bound"))
    return out


def _as_float(x: Any) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def evaluate_forward_model(
    bundle: ScenarioBundle,
    *,
    numeric_overrides: Mapping[str, float] | None = None,
    include_full_report: bool = True,
    code_distance_override: int | None = None,
) -> ForwardModelResult:
    ov = dict(numeric_overrides) if numeric_overrides else {}
    b = apply_numeric_overrides(bundle, ov) if ov else bundle
    report = build_scenario_report(b, code_distance_override=code_distance_override)
    metrics = extract_default_mc_metrics(report)
    return ForwardModelResult(
        numeric_overrides=ov,
        metrics=metrics,
        report=report if include_full_report else None,
    )
