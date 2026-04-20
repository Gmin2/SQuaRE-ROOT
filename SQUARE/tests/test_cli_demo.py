"""Tests for square-mvp-demo CLI."""

from __future__ import annotations

import pytest
from square.cli_demo import main


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
