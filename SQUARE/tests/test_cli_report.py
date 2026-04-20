"""Tests for ``square.cli`` (square-report)."""

from __future__ import annotations

from square.cli import main


def test_square_report_cli_rejects_non_positive_distance_override() -> None:
    assert main(["_no_such_file.yaml", "--d", "0"]) == 2
    assert main(["_no_such_file.yaml", "--d", "-3"]) == 2
