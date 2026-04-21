"""
Charts for SQuaRE reports and Monte Carlo samples.

Dashboard columns mirror :data:`square.mc.forward_model.MC_DASHBOARD_METRIC_FIELDS` plus
``magic_supply_adequate`` and ``schedule_calibration_ratio_table2_over_model_v1``.
θ columns for MC scatter follow :data:`square.mc.overrides.PARAMETER_LAYERS`.

Matplotlib is **optional** at import time; callers that render figures must install
``square[plots]`` (or ``pip install matplotlib``).
"""

from __future__ import annotations

import csv
import sys
from collections.abc import Mapping, Sequence
from io import BufferedIOBase
from pathlib import Path
from typing import Any

from square.mc.forward_model import MC_DASHBOARD_METRIC_FIELDS
from square.mc.overrides import PARAMETER_LAYERS

_extra_plot_dash_keys: tuple[str, ...] = (
    "magic_supply_adequate",
    "schedule_calibration_ratio_table2_over_model_v1",
)
REPORT_PLOT_DASHBOARD_KEYS: tuple[str, ...] = tuple(
    dict.fromkeys([dash for _, dash in MC_DASHBOARD_METRIC_FIELDS] + list(_extra_plot_dash_keys))
)


def extract_report_plot_frame(report: Mapping[str, Any]) -> dict[str, Any]:
    """
    Return a small dict of scalar plot inputs from a full scenario report.

    Intended for notebooks / web UIs that bind to the same keys as JSON exports.
    """
    dash = report.get("dashboard")
    if not isinstance(dash, dict):
        dash = {}
    lfm = report.get("logical_fault_model")
    p_l = None
    if isinstance(lfm, dict):
        p_l = lfm.get("logical_error_rate_per_cycle")
    scen = report.get("scenario")
    name = None
    if isinstance(scen, dict):
        name = scen.get("scenario")
    out: dict[str, Any] = {
        "scenario": name,
        "report_contract_version": report.get("report_contract_version"),
        "logical_error_rate_per_cycle": p_l,
        "warnings_count": len(report["warnings"]) if isinstance(report.get("warnings"), list) else None,
    }
    for k in REPORT_PLOT_DASHBOARD_KEYS:
        out[k] = dash.get(k)
    return out


def _require_pyplot() -> Any:
    try:
        import matplotlib

        if "matplotlib.pyplot" not in sys.modules:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - exercised when matplotlib missing
        raise RuntimeError(
            "Plotting requires matplotlib. Install with: pip install 'square[plots]' "
            "or pip install matplotlib>=3.7"
        ) from exc
    return plt


def _pick_mc_theta_column(
    rows: Sequence[Mapping[str, Any]],
    *,
    theta_parameter_key: str | None,
    study_parameter_key_order: Sequence[str] | None,
) -> str | None:
    """Resolve which CSV column labels the x-axis for θ vs failure proxy."""
    if not rows:
        return None
    row_keys = set(rows[0].keys())
    if theta_parameter_key:
        if theta_parameter_key in row_keys:
            return theta_parameter_key
        return None
    order = list(study_parameter_key_order) if study_parameter_key_order else list(PARAMETER_LAYERS.keys())
    for k in order:
        if k not in PARAMETER_LAYERS or k not in row_keys:
            continue
        xs = [r.get(k) for r in rows]
        vals = [float(x) for x in xs if isinstance(x, (int, float))]
        if len(vals) >= 2 and max(vals) != min(vals):
            return k
    return None


def write_report_semantics_png(
    path: str | Path | BufferedIOBase,
    report: Mapping[str, Any],
    *,
    dpi: int = 120,
) -> Path | BufferedIOBase:
    """
    Write a single PNG summarizing **failure proxy**, **magic throughput multiplier**, and schedule text.

    The failure-proxy bar **clips display** to ``[0, 1]`` (raw value still labeled). The multiplier bar
    **clips display** at 50× with an annotation when the true value exceeds that cap.
    """
    plt = _require_pyplot()
    frame = extract_report_plot_frame(report)
    p_fail = frame.get("logical_failure_probability_union_depth_proxy")
    mult = frame.get("magic_limited_runtime_multiplier")
    adequate = frame.get("magic_supply_adequate")
    ratio = frame.get("schedule_calibration_ratio_table2_over_model_v1")
    d_val = frame.get("code_distance_d")
    naive_days = frame.get("naive_serial_time_days_from_depth_times_cycle")
    p_l = frame.get("logical_error_rate_per_cycle")

    fig, axes = plt.subplots(1, 3, figsize=(11, 3.2), constrained_layout=True)
    fig.suptitle(
        f"SQuaRE semantics — {frame.get('scenario') or 'scenario'} "
        f"(contract v{frame.get('report_contract_version')})",
        fontsize=11,
    )

    # Panel A: failure proxy (interpretable y)
    ax = axes[0]
    ax.set_title("Logical failure proxy\nmin(1, D × p_L)")
    if p_fail is not None and isinstance(p_fail, (int, float)):
        v = max(0.0, min(1.0, float(p_fail)))
        ax.barh([0], [v], color="#2c5282", height=0.35)
        ax.set_xlim(0, 1.0)
        ax.set_yticks([])
        ax.set_xlabel("probability mass (proxy)")
        ax.text(v + 0.02, 0, f"{float(p_fail):.3g}", va="center", fontsize=9)
    else:
        ax.text(0.5, 0.5, "N/A", ha="center", va="center", transform=ax.transAxes)
        ax.set_xticks([])
        ax.set_yticks([])

    # Panel B: magic bottleneck (multiplier ≥ 1)
    ax = axes[1]
    ax.set_title("Magic throughput\n(runtime multiplier if limited)")
    if mult is not None and isinstance(mult, (int, float)) and float(mult) > 0:
        m = float(mult)
        ax.barh([0], [min(m, 50.0)], color="#9b2c2c" if m > 1.0001 else "#276749", height=0.35)
        ax.set_xlim(0, max(2.0, min(m, 50.0) * 1.1))
        ax.set_yticks([])
        ax.set_xlabel("× notional wall-clock (proxy; capped in display at 50)")
        ax.text(min(m, 50.0) * 0.05, 0, f"{m:.4g}", va="center", fontsize=9)
        if m > 50:
            ax.annotate(f"true {m:.3g}", xy=(1, 0), xycoords="axes fraction", ha="right", fontsize=8)
    else:
        ax.text(0.5, 0.5, "N/A\n(check warnings)", ha="center", va="center", transform=ax.transAxes, fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])

    # Panel C: schedule + magic flag text
    ax = axes[2]
    ax.axis("off")
    lines = [
        f"magic_supply_adequate: {adequate!r}",
        f"Table2 / schedule_model_v1: {ratio!r}",
        f"code_distance_d: {d_val!r}",
        f"naive_serial_days (depth×cycle): {naive_days!r}",
        f"p_L (phenomenological / cycle): {p_l!r}",
        f"warnings: {frame.get('warnings_count')!r}",
    ]
    ax.text(0.02, 0.98, "\n".join(lines), transform=ax.transAxes, va="top", fontsize=9, family="monospace")

    if isinstance(path, (str, Path)):
        outp = Path(path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(outp, dpi=dpi)
        plt.close(fig)
        return outp
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


def load_mc_samples_rows_from_csv(path: str | Path) -> list[dict[str, Any]]:
    """Load ``square-mc`` CSV into row dicts (empty strings → missing)."""
    p = Path(path)
    with p.open(encoding="utf-8", newline="") as fh:
        r = csv.DictReader(fh)
        rows: list[dict[str, Any]] = []
        for row in r:
            clean: dict[str, Any] = {}
            for k, v in row.items():
                if v is None or str(v).strip() == "":
                    continue
                try:
                    clean[k] = float(v)
                except ValueError:
                    clean[k] = v
            rows.append(clean)
    return rows


def write_mc_semantics_png(
    path: str | Path | BufferedIOBase,
    rows: Sequence[Mapping[str, Any]],
    *,
    dpi: int = 120,
    theta_parameter_key: str | None = None,
    study_parameter_key_order: Sequence[str] | None = None,
) -> Path | BufferedIOBase:
    """
    Write a multi-panel figure from MC sample rows: failure proxy distribution, magic multiplier,
    and scatter of ``theta_parameter_key`` vs failure proxy when set; otherwise the first **varying**
    key in ``study_parameter_key_order`` (Monte Carlo study ``parameter_keys``), else dict order of
    ``PARAMETER_LAYERS``.
    """
    plt = _require_pyplot()
    fail_key = "logical_failure_probability_union_depth_proxy"
    mult_key = "magic_limited_runtime_multiplier"
    fails = [
        float(r[fail_key])
        for r in rows
        if r.get(fail_key) is not None and isinstance(r.get(fail_key), (int, float))
    ]
    mults = [
        float(r[mult_key])
        for r in rows
        if r.get(mult_key) is not None and isinstance(r.get(mult_key), (int, float))
    ]

    param_key = _pick_mc_theta_column(
        rows,
        theta_parameter_key=theta_parameter_key,
        study_parameter_key_order=study_parameter_key_order,
    )

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.2), constrained_layout=True)
    fig.suptitle("Monte Carlo — failure proxy, magic multiplier, θ correlation", fontsize=11)

    ax = axes[0]
    ax.set_title("Union failure proxy")
    if fails:
        ax.hist(fails, bins=min(30, max(5, len(fails) // 3)), color="#2c5282", edgecolor="white")
        ax.set_xlabel("min(1, D×p_L)")
        ax.set_ylabel("count")
    else:
        ax.text(0.5, 0.5, "no numeric\nsamples", ha="center", va="center", transform=ax.transAxes)

    ax = axes[1]
    ax.set_title("Magic-limited multiplier")
    if mults:
        ax.hist(mults, bins=min(30, max(5, len(mults) // 3)), color="#744210", edgecolor="white")
        ax.set_xlabel("× wall-clock (proxy)")
        ax.set_ylabel("count")
    else:
        ax.text(0.5, 0.5, "no numeric\nsamples", ha="center", va="center", transform=ax.transAxes)

    ax = axes[2]
    ax.set_title("θ vs failure proxy" + (f"\n({param_key})" if param_key else ""))
    xs_sc: list[float] = []
    ys_sc: list[float] = []
    if param_key:
        for r in rows:
            fx = r.get(fail_key)
            px = r.get(param_key)
            if isinstance(fx, (int, float)) and isinstance(px, (int, float)):
                xs_sc.append(float(px))
                ys_sc.append(float(fx))
    if param_key and len(xs_sc) >= 2:
        ax.scatter(xs_sc, ys_sc, s=12, alpha=0.5, c="#553c9a")
        ax.set_xlabel(param_key)
        ax.set_ylabel(fail_key)
    else:
        ax.text(0.5, 0.5, "no θ column\nor failure proxy", ha="center", va="center", transform=ax.transAxes)

    if isinstance(path, (str, Path)):
        outp = Path(path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(outp, dpi=dpi)
        plt.close(fig)
        return outp
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    return path


__all__ = [
    "REPORT_PLOT_DASHBOARD_KEYS",
    "extract_report_plot_frame",
    "load_mc_samples_rows_from_csv",
    "write_mc_semantics_png",
    "write_report_semantics_png",
]
