#!/usr/bin/env python3
"""Plot ``square-mc`` sample CSV (failure proxy, magic multiplier, θ scatter) without re-running MC."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from square.plotting import load_mc_samples_rows_from_csv, write_mc_semantics_png


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Render MC semantics PNG from an existing mc_samples_*.csv (matplotlib required).",
    )
    p.add_argument("csv", type=Path, help="Path to mc_samples CSV from square-mc.")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output PNG (default: <csv_stem>_semantics.png next to the CSV).",
    )
    args = p.parse_args(argv)
    if not args.csv.is_file():
        print(f"plot_mc_csv: not a file: {args.csv}", file=sys.stderr)
        return 1
    out = args.output
    if out is None:
        out = args.csv.with_name(f"{args.csv.stem}_semantics.png")
    try:
        rows = load_mc_samples_rows_from_csv(args.csv)
        write_mc_semantics_png(out, rows)
    except RuntimeError as exc:
        print(f"plot_mc_csv: {exc}", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"plot_mc_csv: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
