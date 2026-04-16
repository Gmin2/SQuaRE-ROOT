"""Tests for structured scenario reports."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from square.formula_eval import eval_numeric_formula, eval_numeric_formula_with_bindings
from square.loader import find_square_root, load_scenario_bundle
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

    assert report["report_contract_version"] == 9
    pl = report["physical_layer"]
    assert pl["status"] == "passthrough_from_modality"
    assert pl["document_id"] == "superconducting_gidney_ekera_2021"
    assert len(pl["parameter_keys"]) == 8
    assert pl["parameters"]["coherence_time_t1_microseconds"]["value"] == 80.0
    lf = report["logical_fault_model"]
    assert lf["status"] == "computed"
    assert lf["exponent_half_distance"] == 13
    assert lf["logical_error_rate_per_cycle"] == pytest.approx(0.05 * (0.1**13))
    assert lf["logical_cycle_time"]["logical_cycle_time_microseconds"] == 10.0
    sm = report["system_metrics"]
    assert sm["schema"] == "system_metrics_v2"
    assert sm["status"] == "computed"
    assert isinstance(sm["notes"], list)
    assert sm["logical_qubit_capacity_lqc"] == pytest.approx(14585.0)
    assert sm["logical_qubit_capacity_lqc_method"] is not None
    assert sm["quantum_operations_throughput_qot"] == pytest.approx(28.0 / (10.0 * 1e-6))
    assert sm["validated_error_rate_ver"] is None
    assert sm["mitigated_operations_ceiling"] is None
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
    assert dash["table2_pinned_source_parameter"] == "paper_table2_rsa2048_reference_rows"
    assert dash["table2_pinned_row_layout_descriptor"] == "reaction_limited_carry_runways"
    assert dash["ccz_factory_parameter_key"] == "reaction_limited_carry_runways"
    assert dash["code_distance_d"] == 25
    assert dash["reported_rsa2048_physical_qubits_millions"] == 20.0
    assert dash["reported_rsa2048_megaqubit_days"] == 5.9
    assert dash["reported_rsa2048_wall_clock_days"] == 0.31
    assert dash["toffoli_plus_t_halves_billions_at_n"] == 2.7
    assert dash["minimum_spacetime_volume_megaqubitdays_at_n"] == 5.9
    assert dash["t_factory_fallback_recommended"] is False
    assert dash["factory_footprint_physical_qubits_from_yaml"] == pytest.approx(28 * 10_000.0)

    depth_layers = 500 * 2048**2 + 2048**2 * math.log2(2048)
    p_l_rsa = lf["logical_error_rate_per_cycle"]
    assert sm["logical_operations_budget_lob"] == pytest.approx(0.1 / float(p_l_rsa))
    assert sm["headroom_logical_depth"] == pytest.approx(0.1 / float(p_l_rsa) - depth_layers)
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
    assert report["layers"]["qcvv"] is None
    assert report["layers"]["qem"] is None
    assert report["sources"]["qcvv"] is None
    assert report["sources"]["qem"] is None

    json.dumps(report)
    md = report_to_markdown(report)
    assert "Physical layer (OSRE snapshot)" in md
    assert "Logical fault model" in md
    assert "passthrough_from_modality" in md
    assert "System metrics (OSRE)" in md
    assert "`computed`" in md
    assert "system_metrics_v2" in md


def test_build_report_ecdlp_secp256k1_babbush_low_toffoli() -> None:
    root = find_square_root()
    scenario = root / "Configs" / "ecdlp_secp256k1_babbush_2026_low_toffoli.yaml"
    bundle = load_scenario_bundle(scenario, root=root)
    report = build_scenario_report(bundle)

    assert report["report_contract_version"] == 9
    assert report["physical_layer"]["status"] == "passthrough_from_modality"
    assert report["physical_layer"]["document_id"] == "superconducting_babbush_et_al_2026"
    sm_ec = report["system_metrics"]
    assert sm_ec["schema"] == "system_metrics_v2"
    assert sm_ec["status"] == "partial"
    assert sm_ec["logical_qubit_capacity_lqc"] is None
    lfm = report["logical_fault_model"]
    assert lfm["status"] == "computed"
    assert lfm["exponent_half_distance"] == 11
    assert lfm["logical_cycle_time"]["logical_cycle_time_microseconds"] == 10.0
    assert report["algorithm_metrics"]["n"] is None
    ecdlp = report["algorithm_metrics"]["ecdlp"]
    assert ecdlp["active"] is True
    assert ecdlp["variant"] == "low_toffoli_variant"
    assert ecdlp["logical_qubits_upper_bound"] == 1450
    assert ecdlp["toffoli_gates_upper_bound"] == 70_000_000
    assert ecdlp["ecdlp_measurement_depth_layers_per_toffoli_gate"] == 1.0
    assert ecdlp["paper_headline_physical_qubits_upper_bound_narrative"] == 500_000

    ev = report["algorithm_metrics"]["evaluated"]
    assert ev["abstract_logical_qubits"]["value"] == 1450
    assert ev["abstract_logical_qubits"]["provenance"] == "ecdlp_envelope_fixed_problem"
    assert ev["abstract_measurement_depth_layers"]["value"] == 70_000_000.0

    p_l_ec = lfm["logical_error_rate_per_cycle"]
    assert sm_ec["logical_operations_budget_lob"] == pytest.approx(0.1 / float(p_l_ec))
    assert sm_ec["headroom_logical_depth"] == pytest.approx(0.1 / float(p_l_ec) - 70_000_000.0)
    assert sm_ec["quantum_operations_throughput_qot"] == pytest.approx(1.0 / (10.0 * 1e-6))
    assert sm_ec["validated_error_rate_ver"] is None
    assert sm_ec["mitigated_operations_ceiling"] is None

    dash = report["dashboard"]
    assert dash.get("ecdlp_active") is True
    assert dash["ecdlp_variant"] == "low_toffoli_variant"
    assert dash["ecdlp_toffoli_gates_upper_bound"] == 70_000_000
    assert dash["ecdlp_paper_headline_physical_qubits_upper_bound"] == 500_000

    assert report["qec_distance_resolution"]["mode"] == "heuristic_union_bound"
    assert report["qec_distance_resolution"]["distance_d"] == 21
    timing = report["timing"]["naive_serial_from_measurement_depth"]
    assert timing is not None
    assert timing["source_parameters"]["depth"] == "ecdlp_logical_resource_envelopes_secp256k1_proxy"
    expected_days = 70_000_000.0 * 1.0 / 1e6 / 86400.0
    assert timing["serial_time_days"] == pytest.approx(expected_days)

    json.dumps(report)


def test_build_report_physical_layer_cain_neutral_atom() -> None:
    root = find_square_root()
    scenario = root / "Configs" / "ecdlp_secp256k1_cain_2026_neutral_atom_qldpc.yaml"
    bundle = load_scenario_bundle(scenario, root=root)
    report = build_scenario_report(bundle)
    pl = report["physical_layer"]
    assert report["report_contract_version"] == 9
    assert pl["document_id"] == "neutral_atom_cain_et_al_2026"
    assert pl["status"] == "passthrough_from_modality"
    assert pl["parameters"]["coherence_time_t1_microseconds"]["value"] == 15000.0
    assert report["logical_fault_model"]["logical_cycle_time"]["logical_cycle_time_microseconds"] == 40.0


def test_build_report_surfaces_qcvv_qem_layers_when_loaded() -> None:
    root = find_square_root()
    scen = root / "Configs" / "_test_qcvv_qem_report.yaml"
    scen.write_text(
        "schema_version: 1\nscenario: _test_qcvv_qem_report\ntarget:\n  modulus_bit_length: 2048\n"
        "  problem: rsa_integer_factoring\nqec:\n  distance_policy: heuristic_union_bound\n"
        "  logical_error_budget: 0.1\ntable2_reference_row:\n  value: ours_2019_parallel_28_ccz\n"
        "  unit: descriptor\npaths:\n"
        "  modality: Assumptions/Modalities/superconducting_gidney_ekera_2021.yaml\n"
        "  qec_code: Assumptions/QEC_Codes/surface_gidney_ekera_2021.yaml\n"
        "  magic: Assumptions/MagicStateProduction/ccz_factory_gidney_ekera_2021.yaml\n"
        "  magic_aux: Assumptions/MagicStateProduction/t_factory_fallback_gidney_ekera_2021.yaml\n"
        "  algorithm: Algorithms/shor_rsa_gidney_ekera_2021.yaml\n"
        "  qcvv: Assumptions/QCVV/identity_no_overhead.yaml\n"
        "  qem: Assumptions/QEM/identity_no_overhead.yaml\n",
        encoding="utf-8",
    )
    try:
        report = build_scenario_report(load_scenario_bundle(scen, root=root))
        assert report["layers"]["qcvv"] is not None
        assert report["layers"]["qcvv"]["header"]["document_id"] == "qcvv_identity_no_overhead"
        assert report["layers"]["qem"] is not None
        assert report["layers"]["qem"]["header"]["document_id"] == "qem_identity_no_overhead"
        assert report["sources"]["qcvv"]["document_id"] == "qcvv_identity_no_overhead"
        assert report["sources"]["qem"]["document_id"] == "qem_identity_no_overhead"
        smq = report["system_metrics"]
        assert smq["validated_error_rate_ver"] == pytest.approx(0.001)
        lob_q = smq["logical_operations_budget_lob"]
        assert lob_q is not None
        assert smq["mitigated_operations_ceiling"] == pytest.approx(float(lob_q))
        md = report_to_markdown(report)
        assert "qcvv" in md
        assert "qem" in md
        assert "VER" in md
        assert "Mitigated operations ceiling" in md
    finally:
        scen.unlink(missing_ok=True)


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
        "  modality: ../outside.yaml\n"
        "  qec_code: ../outside.yaml\n"
        "  magic: ../outside.yaml\n"
        "  algorithm: ../outside.yaml\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="escapes"):
        load_scenario_bundle(scenario, root=root)
