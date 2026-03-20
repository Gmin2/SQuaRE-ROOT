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

    assert report["report_contract_version"] == 2
    assert report["scenario"]["scenario"] == "rsa2048_gidney_ekera_2021_parallel"
    assert report["algorithm_metrics"]["n"] == 2048

    qdr = report["qec_distance_resolution"]
    assert qdr["mode"] == "heuristic_union_bound"
    assert qdr["distance_d"] == 25

    ev = report["algorithm_metrics"]["evaluated"]
    assert "abstract_logical_qubits" in ev
    assert ev["abstract_logical_qubits"]["provenance"] == "computed_from_yaml_formula"
    assert ev["abstract_logical_qubits"]["value"] == pytest.approx(
        3 * 2048 + 0.002 * 2048 * math.log2(2048)
    )

    dash = report["dashboard"]
    assert dash["ccz_factory_count"] == 28
    assert dash["code_distance_d"] == 25
    assert dash["reported_rsa2048_physical_qubits_millions"] == 20.0
    assert dash["reported_rsa2048_megaqubit_days"] == 5.9
    assert dash["reported_rsa2048_wall_clock_days"] == 0.31
    assert dash["toffoli_plus_t_halves_billions_at_n"] == 2.7
    assert dash["minimum_spacetime_volume_megaqubitdays_at_n"] == 5.9
    assert dash["t_factory_fallback_recommended"] is False
    assert dash["factory_footprint_physical_qubits_from_yaml"] == pytest.approx(28 * 10_000.0)

    depth_layers = 500 * 2048**2 + 2048**2 * math.log2(2048)
    expected_naive_days = depth_layers * 1.0 / 1e6 / 86400.0
    assert dash["naive_serial_time_days_from_depth_times_cycle"] == pytest.approx(expected_naive_days)

    timing = report["timing"]
    assert timing["reported_table2_pinned"]["ccz_factory_count"] == 28
    assert timing["reported_table2_pinned"]["megaqubit_days"] == 5.9
    assert timing["reported_table2_pinned"]["wall_clock_days"] == 0.31
    assert timing["naive_serial_from_measurement_depth"]["serial_time_days"] == pytest.approx(expected_naive_days)
    assert timing["schedule_model_v1"] is not None
    assert timing["schedule_model_v1"]["model"] == "parallel_depth_over_ccz_paths_v1"
    assert timing["schedule_calibration"] is not None
    assert timing["schedule_calibration"]["ratio_table2_pinned_over_model_v1"] == pytest.approx(
        0.31 / (depth_layers * 10.0 / 28.0 / 1e6 / 86400.0)
    )

    patch = report["qec_overhead"]["logical_qubit_patch_physical_qubit_count"]
    assert patch["distance_d"] == 25
    assert patch["status"] == "evaluated"
    logical = 3 * 2048 + 0.002 * 2048 * math.log2(2048)
    per_log = 2 * (25 + 1) ** 2
    assert patch["physical_qubits_per_logical"] == pytest.approx(float(per_log))
    assert dash["approximate_data_plane_physical_qubits"] == pytest.approx(logical * per_log)

    le = report["layout_estimate"]
    assert le["reported_end_to_end_physical_qubits"] == pytest.approx(20e6)
    assert le["derived_non_data_overhead_physical_qubits"] == pytest.approx(20e6 - logical * per_log)

    lo = report["layout_optimization"]
    assert lo is not None
    assert lo["summary"]["selected_code_distance_d"] == 25
    assert lo["summary"]["objective"] == "minimize_odd_code_distance_subject_to_union_bound"
    assert lo["candidates"] is None

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


def test_emit_optimization_trace_includes_layout_candidates(tmp_path: Path) -> None:
    root = find_square_root()
    scenario_src = root / "Configs" / "rsa2048_gidney_ekera_2021_parallel.yaml"
    text = scenario_src.read_text(encoding="utf-8")
    assert "emit_optimization_trace" not in text
    text = text.replace(
        "logical_error_budget: 0.1\n",
        "logical_error_budget: 0.1\n  emit_optimization_trace: true\n",
    )
    scenario_copy = tmp_path / "scenario_trace.yaml"
    scenario_copy.write_text(text, encoding="utf-8")
    report = build_scenario_report(load_scenario_bundle(scenario_copy, root=root))
    cand = report["layout_optimization"]["candidates"]
    assert cand is not None
    assert len(cand) >= 10
    assert any(r["distance_d"] == 25 for r in cand)


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
