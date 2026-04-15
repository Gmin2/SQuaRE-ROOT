"""Deterministic forward model y = f(theta, scenario) for Monte Carlo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from square.loader import ScenarioBundle
from square.mc.overrides import apply_numeric_overrides
from square.report import build_scenario_report


@dataclass(frozen=True)
class ForwardModelResult:
    numeric_overrides: dict[str, float]
    metrics: dict[str, float | None]
    report: dict[str, Any] | None


def extract_default_mc_metrics(report: Mapping[str, Any]) -> dict[str, float | None]:
    dash = report.get("dashboard")
    if not isinstance(dash, dict):
        return {
            "naive_serial_time_days": None,
            "code_distance_d": None,
            "approximate_data_plane_physical_qubits": None,
            "logical_qubits_at_n": None,
        }

    out: dict[str, float | None] = {
        "naive_serial_time_days": _as_float(dash.get("naive_serial_time_days_from_depth_times_cycle")),
        "code_distance_d": _as_float(dash.get("code_distance_d")),
        "approximate_data_plane_physical_qubits": _as_float(dash.get("approximate_data_plane_physical_qubits")),
        "logical_qubits_at_n": _as_float(dash.get("logical_qubits_at_n")),
    }
    am = report.get("algorithm_metrics")
    if isinstance(am, dict) and am.get("ecdlp"):
        e = am["ecdlp"]
        if isinstance(e, dict):
            out["ecdlp_toffoli_gates_upper_bound"] = _as_float(e.get("toffoli_gates_upper_bound"))
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
