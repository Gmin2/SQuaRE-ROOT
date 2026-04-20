"""
Stakeholder-facing MVP demo: print a short banner and a Markdown report for a flagship scenario.

Default scenario is the Oratomic gold path (neutral atom + QLDPC + ECDLP envelope).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from square.loader import find_square_root, load_scenario_bundle
from square.report import build_scenario_report, report_to_markdown

_DEFAULT_SCENARIO = Path("Configs") / "oratomic_gold_path.yaml"


def _resolve_scenario_path(user_arg: Path | None, root: Path) -> Path | None:
    """
    Resolve a scenario YAML path against the SQuaRE root and the current working directory.

    :param user_arg: CLI path, or ``None`` for the default Oratomic gold path.
    :param root: Directory containing ``Assumptions/Schemas.yaml``.
    :returns: Absolute path to an existing scenario file, or ``None`` if none found.
    """
    if user_arg is None:
        candidate = (root / _DEFAULT_SCENARIO).resolve()
    else:
        if user_arg.is_absolute():
            candidate = user_arg.resolve()
        elif (root / user_arg).is_file():
            candidate = (root / user_arg).resolve()
        elif user_arg.is_file():
            candidate = user_arg.resolve()
        else:
            candidate = (root / user_arg).resolve()
    if not candidate.is_file():
        print(f"square-mvp-demo: scenario file not found: {candidate}", file=sys.stderr)
        return None
    return candidate


def main(argv: list[str] | None = None) -> int:
    """
    CLI entry for ``square-mvp-demo``: build a report and print Markdown (or JSON with ``--json``).

    :param argv: Arguments excluding the program name; defaults to ``sys.argv[1:]``.
    :returns: Process exit code (0 on success, 2 if the scenario file is missing).
    """
    parser = argparse.ArgumentParser(
        prog="square-mvp-demo",
        description="Print a stakeholder-friendly Markdown report (default: Oratomic gold path).",
    )
    parser.add_argument(
        "scenario",
        type=Path,
        nargs="?",
        default=None,
        help=f"Scenario YAML (default: {_DEFAULT_SCENARIO.as_posix()} under the SQuaRE root).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the full machine-readable JSON report instead of Markdown.",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    root = find_square_root()
    scenario_path = _resolve_scenario_path(args.scenario, root)
    if scenario_path is None:
        return 2
    bundle = load_scenario_bundle(scenario_path, root=root)
    report = build_scenario_report(bundle)
    contract = report.get("report_contract_version")

    if args.json:
        try:
            json.dump(report, sys.stdout, indent=2, allow_nan=False)
        except ValueError as exc:
            print(f"square-mvp-demo: cannot serialize report to JSON: {exc}", file=sys.stderr)
            return 1
        sys.stdout.write("\n")
        return 0

    banner_lines = [
        "=" * 72,
        "SQuaRE — MVP stakeholder demo",
        f"Scenario: {scenario_path.name}  (id: {report.get('scenario', {}).get('scenario', '')})",
        f"Machine-readable contract: report_contract_version={contract} — see docs/output-contract.md",
        "Key JSON blocks for tooling: dashboard, system_metrics, logical_fault_model, layers, timing.",
        f"MVP scope and claims: { (root / 'docs' / 'mvp.md').as_posix() }",
        "=" * 72,
        "",
    ]
    sys.stdout.write("\n".join(banner_lines))
    sys.stdout.write(report_to_markdown(report))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
