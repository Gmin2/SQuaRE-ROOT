"""
Monte Carlo sampling loop: draw θ, evaluate forward model, CSV + rich summary.

Supports independent marginals, Latin hypercube (uniform parameters only), and optional
parallel evaluation via :class:`concurrent.futures.ThreadPoolExecutor` (shared in-memory bundle).
"""

from __future__ import annotations

import csv
import json
import random
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from square.loader import ScenarioBundle
from square.mc.forward_model import evaluate_forward_model
from square.mc.lhs import all_blocks_uniform_for_lhs, generate_lhs_uniform_thetas
from square.mc.parameters import sample_parameter_value
from square.mc.study_spec import MonteCarloStudySpec

# Bump when summary JSON shape or semantics change (quantiles/moments/correlations blocks).
MC_SUMMARY_CONTRACT_VERSION = 1


@dataclass(frozen=True)
class MonteCarloRunResult:
    """Outcome of :func:`run_monte_carlo_study`."""

    study_id: str
    n_samples: int
    seed: int
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _float_column_loose(rows: Sequence[Mapping[str, Any]], col: str) -> list[float]:
    """Coerce ``col`` to floats per row; skip ``None`` and non-numeric values."""
    vals: list[float] = []
    for r in rows:
        v = r.get(col)
        if v is None:
            continue
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            continue
    return vals


def _float_column_strict_all_rows(rows: Sequence[Mapping[str, Any]], col: str) -> list[float] | None:
    """Coerce ``col`` for every row; return ``None`` if any row is missing or non-numeric."""
    vals: list[float] = []
    for r in rows:
        v = r.get(col)
        if v is None:
            return None
        try:
            vals.append(float(v))
        except (TypeError, ValueError):
            return None
    return vals


def _linear_quantile(sorted_vals: list[float], q: float) -> float:
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
    rows: Sequence[Mapping[str, Any]],
    columns: list[str],
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for col in columns:
        vals = _float_column_loose(rows, col)
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


def _moment_summary_for_columns(
    rows: Sequence[Mapping[str, Any]],
    columns: list[str],
) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for col in columns:
        vals = _float_column_loose(rows, col)
        n = len(vals)
        if n == 0:
            out[col] = {}
            continue
        mean = sum(vals) / n
        if n > 1:
            var = sum((v - mean) ** 2 for v in vals) / (n - 1)
            std = var**0.5
        else:
            std = 0.0
        out[col] = {
            "n": float(n),
            "mean": mean,
            "std": std,
            "min": min(vals),
            "max": max(vals),
        }
    return out


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2 or len(ys) != n:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    denx = sum((xs[i] - mx) ** 2 for i in range(n)) ** 0.5
    deny = sum((ys[i] - my) ** 2 for i in range(n)) ** 0.5
    if denx == 0.0 or deny == 0.0:
        return None
    return num / (denx * deny)


def _pairwise_correlations(
    rows: Sequence[Mapping[str, Any]],
    columns: list[str],
) -> dict[str, dict[str, float | None]]:
    """Pearson correlation for columns that have numeric values on every row."""
    series: dict[str, list[float]] = {}
    for col in columns:
        vals = _float_column_strict_all_rows(rows, col)
        if vals is not None and len(vals) >= 2:
            series[col] = vals
    keys = sorted(series)
    out: dict[str, dict[str, float | None]] = {}
    for a in keys:
        out[a] = {}
        for b in keys:
            if a == b:
                out[a][b] = 1.0
            else:
                out[a][b] = _pearson(series[a], series[b])
    return out


def _build_theta_list_independent(
    param_blocks: list[dict[str, Any]],
    n_samples: int,
    rng: random.Random,
) -> list[dict[str, float]]:
    out: list[dict[str, float]] = []
    for _ in range(n_samples):
        theta: dict[str, float] = {}
        for block in param_blocks:
            key = str(block["parameter_key"]).strip()
            theta[key] = sample_parameter_value(block, rng)
        out.append(theta)
    return out


def run_monte_carlo_study(
    spec: MonteCarloStudySpec,
    bundle: ScenarioBundle,
    *,
    n_samples: int,
    seed: int,
    include_full_report: bool = False,
    n_jobs: int = 1,
    sampling_strategy: str | None = None,
) -> MonteCarloRunResult:
    """
    Draw ``n_samples`` θ vectors and evaluate the forward model per draw.

    :param sampling_strategy: ``independent`` | ``latin_hypercube``. If ``None``, use
        ``spec.sampling_strategy``. Latin hypercube requires **all** parameters to use
        ``distribution: uniform``.
    :param n_jobs: If > 1, evaluate forward model with a thread pool (GIL-limited but avoids
        reloading YAML per thread). Use ~CPU count for large ``n_samples``.
    """
    if n_samples < 1:
        raise ValueError("n_samples must be >= 1.")
    if n_jobs < 1:
        raise ValueError("n_jobs must be >= 1.")

    strategy = (sampling_strategy or spec.sampling_strategy).strip().lower()
    if strategy not in ("independent", "latin_hypercube"):
        raise ValueError(f"Unknown sampling_strategy {strategy!r}.")

    rng = random.Random(seed)
    param_blocks = spec.parameters
    param_keys = [str(b["parameter_key"]).strip() for b in param_blocks]

    if strategy == "latin_hypercube":
        if not all_blocks_uniform_for_lhs(param_blocks):
            raise ValueError(
                "latin_hypercube requires every parameter block to use distribution: uniform."
            )
        theta_list = generate_lhs_uniform_thetas(param_blocks, n_samples, rng)
    else:
        theta_list = _build_theta_list_independent(param_blocks, n_samples, rng)

    def _eval_one(theta: dict[str, float]) -> dict[str, float | None]:
        return evaluate_forward_model(
            bundle,
            numeric_overrides=theta,
            include_full_report=include_full_report,
        ).metrics

    if n_jobs == 1:
        metrics_list = [_eval_one(th) for th in theta_list]
    else:
        with ThreadPoolExecutor(max_workers=n_jobs) as ex:
            metrics_list = list(ex.map(_eval_one, theta_list))

    rows: list[dict[str, Any]] = []
    for i, (theta, metrics) in enumerate(zip(theta_list, metrics_list, strict=True)):
        rows.append({"sample_index": i, **theta, **metrics})

    if not rows:
        metric_keys: list[str] = []
        summary_columns = list(param_keys)
    else:
        metric_keys = [k for k in rows[0] if k not in ("sample_index",) and k not in param_keys]
        summary_columns = param_keys + metric_keys
    quantiles = _quantile_summary_for_columns(rows, summary_columns)
    moments = _moment_summary_for_columns(rows, summary_columns)
    correlations = _pairwise_correlations(rows, metric_keys)

    summary: dict[str, Any] = {
        "mc_summary_contract_version": MC_SUMMARY_CONTRACT_VERSION,
        "study_id": spec.study_id,
        "schema_version": spec.schema_version,
        "scope": spec.scope,
        "n_samples": n_samples,
        "seed": seed,
        "sampling_strategy": strategy,
        "n_jobs": n_jobs,
        "parameter_keys": param_keys,
        "metric_keys": metric_keys,
        "quantiles": quantiles,
        "moments": moments,
        "correlations": correlations,
    }

    return MonteCarloRunResult(
        study_id=spec.study_id,
        n_samples=n_samples,
        seed=seed,
        rows=rows,
        summary=summary,
    )


def write_mc_samples_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
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
    """
    Write Monte Carlo summary JSON with strict floats (no ``NaN`` / ``Infinity``).

    :raises ValueError: if the summary is not JSON-serializable under ``allow_nan=False``.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = json.dumps(dict(summary), indent=2, allow_nan=False)
    except ValueError as exc:
        raise ValueError(f"cannot serialize MC summary to JSON: {exc}") from exc
    p.write_text(text + "\n", encoding="utf-8")
