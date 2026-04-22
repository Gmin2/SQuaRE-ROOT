"""CLI: Monte Carlo study — sample θ, run forward model, write CSV + quantile JSON."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from square.loader import (
    find_square_root,
    load_scenario_bundle,
    resolve_path_under_square_root,
)
from square.mc import (
    load_monte_carlo_study_spec,
    run_monte_carlo_study,
    write_mc_samples_csv,
    write_mc_summary_json,
)
from square.mc.overrides import PARAMETER_LAYERS
from square.plotting import write_mc_semantics_png


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="square-mc",
        description="Run a Monte Carlo study (prior predictive): sample θ from study YAML, evaluate reports.",
    )
    parser.add_argument(
        "study",
        type=Path,
        help="Path to Monte Carlo study YAML (e.g. tests/fixtures/monte_carlo_study_ecdlp_example.yaml).",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=100,
        metavar="N",
        help="Number of Monte Carlo draws (default: 100).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for reproducibility (default: 42).",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=None,
        help="Write per-sample rows to this CSV path (default: mc_samples_<study_id>.csv in cwd).",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=None,
        help="Write quantile summary JSON (default: mc_summary_<study_id>.json in cwd).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="SQuaRE project root (directory with Assumptions/Schemas.yaml); auto-detected if omitted.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        metavar="J",
        help="Thread-pool workers for forward evaluations (default: 1).",
    )
    parser.add_argument(
        "--strict-metrics",
        action="store_true",
        help="Abort if any draw omits required MC metrics (overrides study YAML when set).",
    )
    parser.add_argument(
        "--sampling",
        choices=("independent", "latin_hypercube"),
        default=None,
        help="Override study YAML sampling.strategy (latin_hypercube requires all uniform parameters).",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="After the run, write a PNG of MC distributions (failure proxy, magic multiplier, θ scatter).",
    )
    parser.add_argument(
        "--plot-output",
        type=Path,
        default=None,
        metavar="PATH",
        help="PNG path for --plot (default: mc_samples_<study_id>_semantics.png in cwd).",
    )
    parser.add_argument(
        "--plot-theta",
        type=str,
        default=None,
        metavar="KEY",
        help="MC scatter x-axis: a PARAMETER_LAYERS key present in the CSV (default: first varying key).",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.samples < 1:
        print("square-mc: --samples must be a positive integer (>= 1).", file=sys.stderr)
        return 2

    if args.jobs < 1:
        print("square-mc: --jobs must be a positive integer (>= 1).", file=sys.stderr)
        return 2

    root = args.root.resolve() if args.root is not None else find_square_root(Path(__file__))

    try:
        spec = load_monte_carlo_study_spec(args.study, root=root)
        scenario_path = resolve_path_under_square_root(root, str(spec.base_scenario))
    except (FileNotFoundError, TypeError, ValueError) as exc:
        print(f"square-mc: {exc}", file=sys.stderr)
        return 1
    if not scenario_path.is_file():
        print(
            f"square-mc: base scenario not found under project root: {spec.base_scenario} -> {scenario_path}",
            file=sys.stderr,
        )
        return 1

    try:
        bundle = load_scenario_bundle(scenario_path, root=root, require_scenario_under_root=True)
        result = run_monte_carlo_study(
            spec,
            bundle,
            n_samples=args.samples,
            seed=args.seed,
            include_full_report=False,
            n_jobs=args.jobs,
            sampling_strategy=args.sampling,
            strict_metrics=True if args.strict_metrics else None,
        )
    except (FileNotFoundError, TypeError, ValueError) as exc:
        print(f"square-mc: {exc}", file=sys.stderr)
        return 1

    out_csv = args.output_csv
    if out_csv is None:
        out_csv = Path(f"mc_samples_{spec.study_id}.csv")
    out_json = args.summary_json
    if out_json is None:
        out_json = Path(f"mc_summary_{spec.study_id}.json")

    try:
        write_mc_samples_csv(out_csv, result.rows)
        write_mc_summary_json(out_json, result.summary)
    except ValueError as exc:
        print(f"square-mc: {exc}", file=sys.stderr)
        return 1

    try:
        print(f"Wrote {len(result.rows)} rows -> {out_csv.resolve()}")
        print(f"Wrote summary (quantiles, moments, correlations) -> {out_json.resolve()}")
        print(
            f"sampling_strategy={result.summary.get('sampling_strategy')} "
            f"n_jobs={result.summary.get('n_jobs')}"
        )
    except OSError as exc:
        print(f"square-mc: cannot write status to stdout: {exc}", file=sys.stderr)
        return 1

    if args.plot:
        if args.plot_theta is not None:
            _tk = args.plot_theta.strip()
            if not _tk:
                print("square-mc: --plot-theta must be non-empty.", file=sys.stderr)
                return 2
            if _tk not in PARAMETER_LAYERS:
                print(
                    f"square-mc: --plot-theta must be one of: {', '.join(sorted(PARAMETER_LAYERS))}.",
                    file=sys.stderr,
                )
                return 2
        plot_path = args.plot_output
        if plot_path is None:
            plot_path = Path(f"mc_samples_{spec.study_id}_semantics.png")
        try:
            theta_key = args.plot_theta.strip() if args.plot_theta else None
            if theta_key and result.rows and theta_key not in result.rows[0]:
                print(
                    f"square-mc: --plot-theta {theta_key!r} not in sample rows; using default θ selection.",
                    file=sys.stderr,
                )
                theta_key = None
            write_mc_semantics_png(
                plot_path,
                result.rows,
                theta_parameter_key=theta_key,
                study_parameter_key_order=result.summary.get("parameter_keys"),
            )
            print(f"Wrote MC semantics plot -> {plot_path.resolve()}")
        except RuntimeError as exc:
            print(f"square-mc: --plot failed: {exc}", file=sys.stderr)
            return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
