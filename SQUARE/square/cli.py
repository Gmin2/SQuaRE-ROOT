"""Command-line interface for SQuaRE reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from square.loader import find_square_root, load_scenario_bundle
from square.report import build_scenario_report, report_to_markdown


def main(argv: list[str] | None = None) -> int:
    """
    Entry point for ``square-report`` / ``python -m square``.

    :param argv: Arguments (excluding program name); defaults to ``sys.argv[1:]``.
    :returns: Process exit code (0 on success).
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
    except (FileNotFoundError, KeyError, TypeError, ValueError) as exc:
        print(f"square-report: cannot load scenario: {exc}", file=sys.stderr)
        return 1
    try:
        report = build_scenario_report(
            bundle,
            modulus_bits_override=args.n,
            code_distance_override=args.d,
        )
    except (KeyError, TypeError, ValueError) as exc:
        print(f"square-report: cannot build report: {exc}", file=sys.stderr)
        return 1

    if args.markdown:
        sys.stdout.write(report_to_markdown(report))
    else:
        try:
            json.dump(report, sys.stdout, indent=2, allow_nan=False)
        except ValueError as exc:
            print(f"square-report: cannot serialize report to JSON: {exc}", file=sys.stderr)
            return 1
        sys.stdout.write("\n")
    return 0
