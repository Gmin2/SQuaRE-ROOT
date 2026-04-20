"""Tests for square-mvp-demo CLI."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

import pytest
from square.cli_demo import main
from square.loader import find_square_root


def test_square_mvp_demo_default_markdown(capsys: pytest.CaptureFixture[str]) -> None:
    code = main([])
    assert code == 0
    out = capsys.readouterr().out
    assert "MVP stakeholder demo" in out
    assert "oratomic_gold_path" in out
    assert "output-contract.md" in out
    assert "## Headlines" in out


def test_square_mvp_demo_json(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--json"])
    assert code == 0
    out = capsys.readouterr().out
    assert '"report_contract_version"' in out
    assert '"oratomic_gold_path"' in out


def test_square_mvp_demo_rsa_scenario(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["Configs/rsa2048_gidney_ekera_2021_parallel.yaml"])
    assert code == 0
    out = capsys.readouterr().out
    assert "rsa2048_gidney_ekera_2021_parallel" in out


def test_square_cli_demo_module_invokes_main() -> None:
    """``python -m square.cli_demo`` must run (regression: missing __main__ produced no output)."""
    root = find_square_root()
    env = {**os.environ, "PYTHONPATH": str(root)}
    r = subprocess.run(
        [sys.executable, "-m", "square.cli_demo", "--json"],
        cwd=str(root),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stderr
    assert "oratomic_gold_path" in r.stdout


def test_square_cli_mc_module_invokes_main() -> None:
    """``python -m square.cli_mc`` runs a tiny study (parity with CI ``square-mc``)."""
    root = find_square_root()
    env = {**os.environ, "PYTHONPATH": str(root)}
    td = tempfile.mkdtemp()
    csv_p = os.path.join(td, "s.csv")
    json_p = os.path.join(td, "s.json")
    try:
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "square.cli_mc",
                "Configs/monte_carlo_study_ecdlp_example.yaml",
                "--samples",
                "2",
                "--seed",
                "1",
                "--output-csv",
                csv_p,
                "--summary-json",
                json_p,
                "--root",
                str(root),
            ],
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode == 0, r.stderr
        assert os.path.isfile(csv_p) and os.path.getsize(csv_p) > 0
        assert os.path.isfile(json_p) and os.path.getsize(json_p) > 0
    finally:
        shutil.rmtree(td, ignore_errors=True)
