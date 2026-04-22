#!/usr/bin/env python3
"""
Minimal Monte Carlo demo: run a short study and print summary stats.

Usage (from ``SQUARE/`` after ``pip install -e .``)::

    python scripts/mc_demo.py

Optional: ``pip install matplotlib`` then set environment ``SQUARE_MC_PLOT=1`` to save a histogram.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Allow running without install: add SQUARE to path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from square.loader import find_square_root, load_scenario_bundle
from square.mc import load_monte_carlo_study_spec, run_monte_carlo_study


def main() -> int:
    root = find_square_root(Path(__file__))
    study_path = root / "tests" / "fixtures" / "monte_carlo_study_ecdlp_example.yaml"
    spec = load_monte_carlo_study_spec(study_path, root=root)
    bundle = load_scenario_bundle(root / spec.base_scenario, root=root)

    result = run_monte_carlo_study(
        spec,
        bundle,
        n_samples=40,
        seed=7,
        include_full_report=False,
        n_jobs=1,
    )

    m = result.summary["moments"].get("naive_serial_time_days", {})
    print(f"Study: {spec.study_id}  strategy={result.summary.get('sampling_strategy')}")
    print(f"naive_serial_time_days: mean={m.get('mean')}  std={m.get('std')}")
    q = result.summary["quantiles"].get("naive_serial_time_days", {})
    print(f"  quantiles p05/p50/p95: {q.get('p05')} / {q.get('p50')} / {q.get('p95')}")

    if os.environ.get("SQUARE_MC_PLOT") == "1":
        try:
            import matplotlib.pyplot as plt

            vals = [
                float(r["naive_serial_time_days"])
                for r in result.rows
                if r.get("naive_serial_time_days") is not None
            ]
            fig, ax = plt.subplots()
            ax.hist(vals, bins=12, color="steelblue", edgecolor="black")
            ax.set_xlabel("naive_serial_time_days")
            ax.set_ylabel("count")
            out = Path("mc_demo_naive_days.png")
            fig.savefig(out, dpi=120)
            print(f"Wrote {out.resolve()}")
            plt.close()
        except ImportError:
            print("matplotlib not installed; skip plot (pip install matplotlib)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
