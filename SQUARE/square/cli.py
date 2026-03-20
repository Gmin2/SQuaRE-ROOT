"""Command-line interface for SQuaRE reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from square.loader import load_scenario_bundle
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
        "--markdown",
        action="store_true",
        help="Emit Markdown summary instead of JSON.",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    bundle = load_scenario_bundle(args.scenario)
    report = build_scenario_report(bundle, modulus_bits_override=args.n)

    if args.markdown:
        sys.stdout.write(report_to_markdown(report))
    else:
        json.dump(report, sys.stdout, indent=2)
        sys.stdout.write("\n")
    return 0
