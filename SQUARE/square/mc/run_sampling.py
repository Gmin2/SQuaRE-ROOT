"""
Monte Carlo sampling loop: draw θ, evaluate forward model, CSV + quantile summary.

Uses independent marginals per study YAML parameter block (joint correlation is a future extension).
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from square.loader import ScenarioBundle
from square.mc.forward_model import evaluate_forward_model
from square.mc.parameters import sample_parameter_value
from square.mc.study_spec import MonteCarloStudySpec


@dataclass(frozen=True)
class MonteCarloRunResult:
    """Outcome of :func:`run_monte_carlo_study`."""

    study_id: str
    n_samples: int
    seed: int
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _linear_quantile(sorted_vals: list[float], q: float) -> float:
    """Linear interpolation quantile; ``q`` in [0, 1]."""
    if not sorted_vals:
        return float("nan")
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = q * (n - 1)
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    w = pos - lo
    return sorted_vals[lo] * (1.0 - w) + sorted_vals[hi] * w


def _quantile_summary_for_columns(
    rows: list[Mapping[str, Any]],
    columns: list[str],
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for col in columns:
        vals: list[float] = []
        for r in rows:
            v = r.get(col)
            if v is None:
                continue
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                continue
        if not vals:
            out[col] = {}
            continue
        vals.sort()
        out[col] = {
            "p05": _linear_quantile(vals, 0.05),
            "p50": _linear_quantile(vals, 0.5),
            "p95": _linear_quantile(vals, 0.95),
        }
    return out


def run_monte_carlo_study(
    spec: MonteCarloStudySpec,
    bundle: ScenarioBundle,
    *,
    n_samples: int,
    seed: int,
    include_full_report: bool = False,
) -> MonteCarloRunResult:
    """
    Draw ``n_samples`` independent θ vectors (one draw per parameter per sample), evaluate ``f(θ)``.

    :param spec: Loaded study (priors).
    :param bundle: Base scenario bundle (from ``spec.base_scenario``).
    :param n_samples: Number of Monte Carlo draws (>= 1).
    :param seed: RNG seed for reproducibility.
    :param include_full_report: If True, keeps full JSON report per sample (memory-heavy).
    """
    if n_samples < 1:
        raise ValueError("n_samples must be >= 1.")

    rng = random.Random(seed)
    param_blocks = spec.parameters
    param_keys = [str(b["parameter_key"]).strip() for b in param_blocks]

    rows: list[dict[str, Any]] = []
    for i in range(n_samples):
        theta: dict[str, float] = {}
        for block in param_blocks:
            key = str(block["parameter_key"]).strip()
            theta[key] = sample_parameter_value(block, rng)
        result = evaluate_forward_model(
            bundle,
            numeric_overrides=theta,
            include_full_report=include_full_report,
        )
        row: dict[str, Any] = {"sample_index": i, **theta, **result.metrics}
        rows.append(row)

    metric_keys = [k for k in rows[0] if k not in ("sample_index",) and k not in param_keys]
    summary_columns = param_keys + metric_keys
    quantiles = _quantile_summary_for_columns(rows, summary_columns)

    summary: dict[str, Any] = {
        "study_id": spec.study_id,
        "schema_version": spec.schema_version,
        "scope": spec.scope,
        "n_samples": n_samples,
        "seed": seed,
        "parameter_keys": param_keys,
        "metric_keys": metric_keys,
        "quantiles": quantiles,
    }

    return MonteCarloRunResult(
        study_id=spec.study_id,
        n_samples=n_samples,
        seed=seed,
        rows=rows,
        summary=summary,
    )


def write_mc_samples_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    """Write sample rows to CSV (all keys unioned as columns)."""
    if not rows:
        Path(path).write_text("sample_index\n", encoding="utf-8")
        return
    fieldnames: list[str] = []
    seen: set[str] = set()
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                fieldnames.append(k)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: _csv_cell(r.get(k)) for k in fieldnames})


def _csv_cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return repr(v)
    return str(v)


def write_mc_summary_json(path: str | Path, summary: Mapping[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as fh:
        json.dump(dict(summary), fh, indent=2)
        fh.write("\n")
