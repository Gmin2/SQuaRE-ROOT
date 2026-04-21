"""Tests for ``square.cli`` (square-report)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from square.cli import main
from square.loader import find_square_root


def test_square_report_cli_rejects_non_positive_distance_override() -> None:
    assert main(["_no_such_file.yaml", "--d", "0"]) == 2
    assert main(["_no_such_file.yaml", "--d", "-3"]) == 2


def test_square_report_cli_rejects_non_positive_modulus_override() -> None:
    assert main(["_no_such_file.yaml", "--n", "0"]) == 2
    assert main(["_no_such_file.yaml", "--n", "-2048"]) == 2


def test_square_report_cli_json_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = find_square_root()
    monkeypatch.chdir(tmp_path)
    scenario = root / "Configs" / "oratomic_gold_path.yaml"
    assert scenario.is_file()
    code = main([str(scenario), "--root", str(root)])
    assert code == 0


def test_square_report_cli_rejects_scenario_outside_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = find_square_root()
    outside = tmp_path / "outside.yaml"
    outside.write_text(
        "schema_version: 1\nscenario: outside\npaths:\n"
        "  modality: Assumptions/Modalities/superconducting_gidney_ekera_2021.yaml\n"
        "  qec_code: Assumptions/QEC_Codes/surface_gidney_ekera_2021.yaml\n"
        "  magic: Assumptions/MagicStateProduction/ccz_factory_gidney_ekera_2021.yaml\n"
        "  algorithm: Algorithms/shor_rsa_gidney_ekera_2021.yaml\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    assert main([str(outside), "--root", str(root)]) == 1


def test_square_report_cli_writes_valid_json_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = find_square_root()
    monkeypatch.chdir(tmp_path)
    scenario = root / "Configs" / "oratomic_gold_path.yaml"
    code = main([str(scenario), "--root", str(root)])
    assert code == 0
    out = capsys.readouterr().out.strip()
    data = json.loads(out)
    assert data["report_contract_version"] == 10
    assert "dashboard" in data
