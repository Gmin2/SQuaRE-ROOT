"""Command-line interface for SQuaRE reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from square.loader import find_square_root, load_scenario_bundle
from square.plotting import write_report_semantics_png
from square.report import build_scenario_report, report_to_markdown


def main(argv: list[str] | None = None) -> int:
    """
    Entry point for ``square-report`` / ``python -m square``.

    :param argv: Arguments (excluding program name); defaults to ``sys.argv[1:]``.
    :returns: Process exit code: ``0`` success; ``1`` load/build/serialize errors; ``2`` invalid flags;
        ``3`` optional ``--plot`` failed after JSON/Markdown was written (stdout already emitted).
    """
    parser = argparse.ArgumentParser(
        prog="square-report",
        description="Load a SQuaRE scenario YAML and print a structured report (JSON or Markdown).",
    )
    parser.add_argument(
        "scenario",
        type=Path,
        help="Path to a scenario file under Configs/ (or any scenario YAML with paths.*).",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=None,
        metavar="BITS",
        help="Override modulus bit length for formula evaluation.",
    )
    parser.add_argument(
        "--d",
        type=int,
        default=None,
        metavar="DISTANCE",
        help="Override surface-code distance d (evaluates QEC patch qubit formula).",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Emit Markdown summary instead of JSON.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="SQuaRE project root (directory with Assumptions/Schemas.yaml); inferred from scenario path if omitted.",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Also write a PNG of failure proxy, magic throughput, and schedule text (needs matplotlib).",
    )
    parser.add_argument(
        "--plot-output",
        type=Path,
        default=None,
        metavar="PATH",
        help="PNG path for --plot (default: <scenario_stem>_report_semantics.png in cwd).",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.d is not None and args.d < 1:
        print("square-report: --d must be a positive integer (>= 1).", file=sys.stderr)
        return 2

    if args.n is not None and args.n < 1:
        print("square-report: --n must be a positive integer (>= 1).", file=sys.stderr)
        return 2

    root = args.root.resolve() if args.root is not None else find_square_root(args.scenario)
    try:
        bundle = load_scenario_bundle(
            args.scenario,
            root=root,
            require_scenario_under_root=True,
        )
    except (FileNotFoundError, TypeError, ValueError) as exc:
        print(f"square-report: cannot load scenario: {exc}", file=sys.stderr)
        return 1
    try:
        report = build_scenario_report(
            bundle,
            modulus_bits_override=args.n,
            code_distance_override=args.d,
        )
    except (TypeError, ValueError) as exc:
        print(f"square-report: cannot build report: {exc}", file=sys.stderr)
        return 1

    if args.markdown:
        try:
            sys.stdout.write(report_to_markdown(report))
        except (AttributeError, BrokenPipeError, OSError, TypeError, ValueError) as exc:
            print(f"square-report: cannot render Markdown: {exc}", file=sys.stderr)
            return 1
    else:
        try:
            json.dump(report, sys.stdout, indent=2, allow_nan=False)
            sys.stdout.write("\n")
        except (BrokenPipeError, OSError, ValueError) as exc:
            print(f"square-report: cannot serialize or write JSON: {exc}", file=sys.stderr)
            return 1

    if args.plot:
        plot_path = args.plot_output
        if plot_path is None:
            plot_path = Path(f"{args.scenario.stem}_report_semantics.png")
        try:
            write_report_semantics_png(plot_path, report)
            print(f"square-report: wrote plot -> {plot_path.resolve()}", file=sys.stderr)
        except RuntimeError as exc:
            print(f"square-report: --plot failed: {exc}", file=sys.stderr)
            return 3
    return 0
