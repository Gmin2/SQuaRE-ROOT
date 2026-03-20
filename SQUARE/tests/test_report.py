"""Tests for structured scenario reports."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from square.loader import find_square_root, load_scenario_bundle
from square.formula_eval import eval_numeric_formula, eval_numeric_formula_with_bindings
from square.report import build_scenario_report, report_to_markdown


def test_eval_numeric_formula_golden() -> None:
    assert eval_numeric_formula("3 * n + 0.002 * n * log2(n)", 2048) == pytest.approx(
        3 * 2048 + 0.002 * 2048 * math.log2(2048)
    )


def test_eval_numeric_formula_with_bindings_patch_in_d() -> None:
    assert eval_numeric_formula_with_bindings("2 * (d + 1)**2", {"d": 17.0}) == pytest.approx(648.0)


def test_build_report_rsa2048_parallel() -> None:
    root = find_square_root()
    scenario = root / "Configs" / "rsa2048_gidney_ekera_2021_parallel.yaml"
    bundle = load_scenario_bundle(scenario, root=root)
    report = build_scenario_report(bundle)

    assert report["report_contract_version"] == 1
    assert report["scenario"]["scenario"] == "rsa2048_gidney_ekera_2021_parallel"
    assert report["algorithm_metrics"]["n"] == 2048

    ev = report["algorithm_metrics"]["evaluated"]
    assert "abstract_logical_qubits" in ev
    assert ev["abstract_logical_qubits"]["provenance"] == "computed_from_yaml_formula"
    assert ev["abstract_logical_qubits"]["value"] == pytest.approx(
        3 * 2048 + 0.002 * 2048 * math.log2(2048)
    )

    dash = report["dashboard"]
    assert dash["ccz_factory_count"] == 28
    assert dash["reported_rsa2048_physical_qubits_millions"] == 20.0
    assert dash["toffoli_plus_t_halves_billions_at_n"] == 2.7
    assert dash["minimum_spacetime_volume_megaqubitdays_at_n"] == 5.9
    assert dash["t_factory_fallback_recommended"] is False

    assert report["layers"]["magic_aux"] is not None
    assert report["layers"]["magic_aux"]["header"]["document_id"] == "t_factory_fallback_gidney_ekera_2021"

    json.dumps(report)


def test_build_report_with_code_distance_evaluates_patch_and_rollup() -> None:
    root = find_square_root()
    scenario = root / "Configs" / "rsa2048_gidney_ekera_2021_parallel.yaml"
    bundle = load_scenario_bundle(scenario, root=root)
    report = build_scenario_report(bundle, code_distance_override=17)

    patch = report["qec_overhead"]["logical_qubit_patch_physical_qubit_count"]
    assert patch["distance_d"] == 17
    assert patch["physical_qubits_per_logical"] == pytest.approx(648.0)
    assert patch["status"] == "evaluated"
    assert patch.get("provenance") == "computed_from_yaml_formula"

    logical = 3 * 2048 + 0.002 * 2048 * math.log2(2048)
    assert report["dashboard"]["logical_qubit_physical_qubits_if_distance_d"] == pytest.approx(648.0)
    assert report["dashboard"]["approximate_data_plane_physical_qubits"] == pytest.approx(logical * 648.0)

    pr = report["physical_rollup"]
    assert pr["code_distance_d"] == 17
    assert pr["physical_qubits_per_logical"] == pytest.approx(648.0)
    assert pr["abstract_logical_qubits_at_n"] == pytest.approx(logical)
    assert pr["approximate_data_plane_physical_qubits"] == pytest.approx(logical * 648.0)
    assert pr["patch_formula_status"] == "evaluated"

    json.dumps(report)


def test_report_markdown_contains_scenario_name() -> None:
    root = find_square_root()
    scenario = root / "Configs" / "rsa2048_gidney_ekera_2021_parallel.yaml"
    report = build_scenario_report(load_scenario_bundle(scenario, root=root))
    md = report_to_markdown(report)
    assert "rsa2048_gidney_ekera_2021_parallel" in md
    assert "## Headlines" in md


def test_load_scenario_rejects_path_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "square_root"
    (root / "Assumptions").mkdir(parents=True)
    (root / "Assumptions" / "Schemas.yaml").write_text("schema_version: 1\n", encoding="utf-8")
    (root / "Configs").mkdir()
    outside = tmp_path / "outside.yaml"
    outside.write_text("document_id: x\nschema_version: 1\nprimary_reference: x\n", encoding="utf-8")
    scenario = root / "Configs" / "bad.yaml"
    scenario.write_text(
        "schema_version: 1\nscenario: bad\npaths:\n"
        f"  modality: ../outside.yaml\n"
        f"  qec_code: ../outside.yaml\n"
        f"  magic: ../outside.yaml\n"
        f"  algorithm: ../outside.yaml\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="escapes"):
        load_scenario_bundle(scenario, root=root)
