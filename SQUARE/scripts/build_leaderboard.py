#!/usr/bin/env python3
"""Build the Q-Day Leaderboard data files by running ``square-report`` on every scenario.

Shells out to ``square-report <config>`` for each YAML under ``Configs/``, extracts a
small set of headline metrics (with documented fallback chains, because RSA and ECDLP
scenarios populate different report fields), computes a CRQC feasibility score, and
writes ``site/data/leaderboard.json``. Optionally merges a rolling history snapshot for
the sparkline view.

The script fails loudly: any scenario whose report exits non-zero or emits unparseable
JSON aborts the whole build with a non-zero exit code, so a CI job goes red rather than
silently publishing a partial board. See ``docs/leaderboard.md`` for the score formula
and column provenance.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Maximum history snapshots retained for the sparkline (oldest dropped first).
MAX_HISTORY_POINTS = 60

# Physical-qubit estimate, in order of preference. The first present (non-null) wins.
# Each entry is (dashboard_key, multiplier) so we can normalise "millions" to a count.
PHYSICAL_QUBIT_SOURCES: list[tuple[str, float]] = [
    ("reported_rsa2048_physical_qubits_millions", 1_000_000.0),
    ("ecdlp_paper_headline_physical_qubits_upper_bound", 1.0),
    ("approximate_data_plane_physical_qubits", 1.0),
]

# Wall-clock estimate in days, in order of preference. First present (non-null) wins.
WALL_CLOCK_DAY_SOURCES: list[str] = [
    "reported_rsa2048_wall_clock_days",
    "schedule_model_v1_wall_clock_days",
    "naive_serial_time_days_from_depth_times_cycle",
]


def run_report(config_path: Path, root: Path) -> dict[str, Any]:
    """Run ``square-report`` on one scenario and return the parsed JSON report.

    :param config_path: Path to the scenario YAML.
    :param root: SQuaRE project root passed through as ``--root``.
    :returns: The decoded report object.
    :raises RuntimeError: If the CLI exits non-zero or its stdout is not valid JSON.
    """
    proc = subprocess.run(
        ["square-report", str(config_path), "--root", str(root)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"square-report exited {proc.returncode} for {config_path.name}: "
            f"{proc.stderr.strip() or '(no stderr)'}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"square-report produced invalid JSON for {config_path.name}: {exc}"
        ) from exc


def _pick_qubits(dashboard: dict[str, Any]) -> tuple[float | None, str | None]:
    """Select a physical-qubit count from the dashboard via the documented fallback chain.

    :returns: ``(qubits, source_key)`` or ``(None, None)`` if no source is populated.
    """
    for key, mult in PHYSICAL_QUBIT_SOURCES:
        value = dashboard.get(key)
        if isinstance(value, (int, float)):
            return float(value) * mult, key
    return None, None


def _pick_wall_clock_days(dashboard: dict[str, Any]) -> tuple[float | None, str | None]:
    """Select a wall-clock estimate (days) via the documented fallback chain.

    :returns: ``(days, source_key)`` or ``(None, None)`` if no source is populated.
    """
    for key in WALL_CLOCK_DAY_SOURCES:
        value = dashboard.get(key)
        if isinstance(value, (int, float)):
            return float(value), key
    return None, None


def feasibility_score(qubits: float | None, wall_clock_days: float | None) -> float | None:
    """CRQC feasibility proxy on a 0-100 scale (higher = fewer resources = nearer-term).

    Uses spacetime volume ``V = (qubits / 1e6) * wall_clock_days`` in megaqubit-days and
    maps it on a log scale anchored absolutely: score 100 at ``V = 1e-4`` MQ-days,
    score 0 at ``V = 1e4`` MQ-days. This is a transparent proxy, not an endorsement of
    feasibility; see ``docs/leaderboard.md``.

    :returns: Clamped score in ``[0, 100]``, or ``None`` if inputs are missing/non-positive.
    """
    if qubits is None or wall_clock_days is None:
        return None
    volume_mqd = (qubits / 1_000_000.0) * wall_clock_days
    if volume_mqd <= 0:
        return None
    score = 20.0 * (1.0 - math.log10(volume_mqd))
    return max(0.0, min(100.0, round(score, 1)))


def extract_row(report: dict[str, Any]) -> dict[str, Any]:
    """Reduce a full report to one leaderboard row.

    :param report: A parsed ``square-report`` JSON object.
    :returns: Flat row with headline metrics, score, and provenance of picked sources.
    """
    dashboard = report.get("dashboard", {})
    scenario = report.get("scenario", {})
    target = report.get("target", {})
    modality = report.get("layers", {}).get("modality", {})

    qubits, qubits_source = _pick_qubits(dashboard)
    wall_clock_days, wall_clock_source = _pick_wall_clock_days(dashboard)

    return {
        "scenario": scenario.get("scenario"),
        "description": scenario.get("description"),
        "problem": target.get("problem"),
        "modality": modality.get("document_id"),
        "code_distance_d": dashboard.get("code_distance_d"),
        "logical_qubits": dashboard.get("logical_qubits_at_n"),
        "physical_qubits": qubits,
        "physical_qubits_source": qubits_source,
        "wall_clock_days": wall_clock_days,
        "wall_clock_source": wall_clock_source,
        "feasibility_score": feasibility_score(qubits, wall_clock_days),
        "report_contract_version": report.get("report_contract_version"),
        "generated_at": report.get("generated_at"),
        "warnings_count": len(report.get("warnings", []) or []),
    }


def load_prior_history(url: str | None) -> list[dict[str, Any]]:
    """Fetch the previously published ``history.json`` from the live site, if reachable.

    Network/parse failures (including a first-run 404) are non-fatal and yield an empty
    history so the build still succeeds.

    :param url: Absolute URL to the published ``data/history.json``, or ``None`` to skip.
    :returns: The prior history list, or ``[]``.
    """
    if not url:
        return []
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:  # noqa: S310 (trusted CI URL)
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, OSError) as exc:
        print(f"build_leaderboard: no prior history ({exc}); starting fresh.", file=sys.stderr)
        return []
    runs = payload.get("runs") if isinstance(payload, dict) else payload
    return runs if isinstance(runs, list) else []


def build_history(
    prior: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    commit: str,
    timestamp: str,
) -> list[dict[str, Any]]:
    """Append the current run's scores to history, replacing any same-commit entry.

    :param prior: Previously published run snapshots.
    :param rows: Current leaderboard rows.
    :param commit: Short git SHA of the current run.
    :param timestamp: ISO-8601 build timestamp.
    :returns: History list trimmed to ``MAX_HISTORY_POINTS`` most recent runs.
    """
    snapshot = {
        "commit": commit,
        "timestamp": timestamp,
        "scores": {
            row["scenario"]: row["feasibility_score"]
            for row in rows
            if row.get("scenario") is not None
        },
    }
    kept = [run for run in prior if run.get("commit") != commit]
    kept.append(snapshot)
    return kept[-MAX_HISTORY_POINTS:]


def main(argv: list[str] | None = None) -> int:
    """Entry point. See module docstring.

    :returns: ``0`` on success; ``1`` if any scenario report fails.
    """
    parser = argparse.ArgumentParser(description="Build Q-Day Leaderboard data files.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="SQuaRE project root (directory containing Configs/). Default: repo SQUARE/.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output data directory. Default: <root>/site/data.",
    )
    parser.add_argument(
        "--history-url",
        type=str,
        default=None,
        help="URL of the previously published history.json (for sparkline continuity).",
    )
    parser.add_argument(
        "--commit",
        type=str,
        default="local",
        help="Short git SHA stamped into the history snapshot.",
    )
    parser.add_argument(
        "--timestamp",
        type=str,
        default="",
        help="ISO-8601 build timestamp stamped into outputs.",
    )
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    configs_dir = root / "Configs"
    out_dir: Path = (args.out or (root / "site" / "data")).resolve()

    config_files = sorted(p for p in configs_dir.glob("*.yaml"))
    if not config_files:
        print(f"build_leaderboard: no scenarios found under {configs_dir}", file=sys.stderr)
        return 1

    rows: list[dict[str, Any]] = []
    for config_path in config_files:
        print(f"build_leaderboard: running {config_path.name} ...", file=sys.stderr)
        try:
            report = run_report(config_path, root)
        except RuntimeError as exc:
            print(f"build_leaderboard: FAILED on {config_path.name}: {exc}", file=sys.stderr)
            return 1
        rows.append(extract_row(report))

    rows.sort(
        key=lambda r: (r["feasibility_score"] is None, -(r["feasibility_score"] or 0.0))
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    leaderboard = {
        "generated_at": args.timestamp,
        "commit": args.commit,
        "score_formula": "clamp(20 * (1 - log10(V)), 0, 100); V = (physical_qubits/1e6) * wall_clock_days [megaqubit-days]",
        "rows": rows,
    }
    (out_dir / "leaderboard.json").write_text(json.dumps(leaderboard, indent=2) + "\n")

    prior = load_prior_history(args.history_url)
    history = build_history(prior, rows, args.commit, args.timestamp)
    (out_dir / "history.json").write_text(
        json.dumps({"runs": history}, indent=2) + "\n"
    )

    print(
        f"build_leaderboard: wrote {len(rows)} scenarios -> {out_dir}/leaderboard.json "
        f"({len(history)} history points).",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
