"""Tests for structured scenario reports."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from square.formula_eval import eval_numeric_formula, eval_numeric_formula_with_bindings
from square.loader import find_square_root, load_scenario_bundle
from square.mc.forward_model import extract_default_mc_metrics
from square.report import (
    REPORT_CONTRACT_VERSION,
    build_scenario_report,
    report_to_markdown,
)
from square.report_dashboard import DASHBOARD_LOGICAL_FAILURE_PROXY_KEY
from square.report_system_metrics import VER_USES_HEADLINE_CHARACTERISTIC_FOR_VER
from square.yaml_numeric import read_qcvv_characterization_error_multiplier


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

    assert report["report_contract_version"] == REPORT_CONTRACT_VERSION
    pl = report["physical_layer"]
    assert pl["status"] == "passthrough_from_modality"
    assert pl["document_id"] == "superconducting_gidney_ekera_2021"
    assert len(pl["parameter_keys"]) == 11
    assert "fabrication_variability_proxy" in pl["parameters"]
    assert isinstance(pl.get("notes"), list) and pl["notes"]
    assert pl["parameters"]["coherence_time_t1_microseconds"]["value"] == 80.0
    lf = report["logical_fault_model"]
    assert lf["inputs"]["p_nominal_gate_proxy_method"] == "max_1q_2q"
    assert lf["inputs"]["ver_grounded_on_characteristic_only"] is VER_USES_HEADLINE_CHARACTERISTIC_FOR_VER
    assert lf["inputs"]["p_nominal"] == pytest.approx(0.001)
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
    assert sm["validated_error_rate_ver"] == pytest.approx(0.001)
    lob_rsa = float(sm["logical_operations_budget_lob"])
    assert sm["mitigated_operations_ceiling"] == pytest.approx(lob_rsa)
    ps = report["parameter_sensitivity"]
    assert ps["schema"] == "parameter_sensitivity_v1"
    assert ps["status"] == "computed"
    assert ps["ranking_by_abs_derivative_code_distance_d"]
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
    assert dash["reported_rsa2048_megaqubit_days"] == pytest.approx(5.9, rel=0.08)
    assert dash["reported_rsa2048_wall_clock_days"] == pytest.approx(0.31, rel=0.08)
    assert dash["toffoli_plus_t_halves_billions_at_n"] == pytest.approx(2.7, rel=0.08)
    assert dash["minimum_spacetime_volume_megaqubitdays_at_n"] == pytest.approx(5.9, rel=0.08)
    assert dash["t_factory_fallback_recommended"] is False
    assert dash["t_factory_magic_aux_applicable_to_target"] is True
    assert dash["t_factory_transition_modulus_bits_order_of_magnitude"] == 32786
    assert dash["t_factory_transition_scale_confidence"] == "estimated"
    assert dash["t_factory_branch_yaml_enabled"] is True
    assert dash["t_factory_fallback_non_clifford_mechanism"] == "t_distillation_fowler_et_al_style"
    assert any("CCZ→T transition scale is confidence" in str(w) for w in report["warnings"])
    assert dash["factory_footprint_physical_qubits_from_yaml"] == pytest.approx(28 * 10_000.0)

    depth_layers = 500 * 2048**2 + 2048**2 * math.log2(2048)
    p_l_rsa = lf["logical_error_rate_per_cycle"]
    assert dash[DASHBOARD_LOGICAL_FAILURE_PROXY_KEY] == pytest.approx(
        min(1.0, float(depth_layers) * float(p_l_rsa))
    )
    assert sm["logical_operations_budget_lob"] == pytest.approx(0.1 / float(p_l_rsa))
    assert sm["headroom_logical_depth"] == pytest.approx(0.1 / float(p_l_rsa) - depth_layers)
    expected_naive_days = depth_layers * 1.0 / 1e6 / 86400.0
    assert dash["naive_serial_time_days_from_depth_times_cycle"] == pytest.approx(expected_naive_days)
    assert dash["magic_supply_adequate"] is True
    assert dash["magic_limited_runtime_multiplier"] == pytest.approx(1.0)

    timing = report["timing"]
    assert timing["reported_table2_pinned"]["ccz_factory_count"] == 28
    assert timing["reported_table2_pinned"]["megaqubit_days"] == pytest.approx(5.9, rel=0.08)
    assert timing["reported_table2_pinned"]["wall_clock_days"] == pytest.approx(0.31, rel=0.08)
    assert timing["naive_serial_from_measurement_depth"]["serial_time_days"] == pytest.approx(expected_naive_days)
    assert timing["schedule_model_v1"] is not None
    assert timing["schedule_model_v1"]["model"] == "parallel_depth_over_ccz_paths_v1"
    assert timing["schedule_calibration"] is not None
    assert timing["schedule_calibration"]["ratio_table2_pinned_over_model_v1"] == pytest.approx(
        0.31 / (depth_layers * 10.0 / 28.0 / 1e6 / 86400.0), rel=0.08
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
    assert report["layers"]["qcvv"] is not None
    assert report["layers"]["qcvv"]["header"]["document_id"] == "qcvv_identity_no_overhead"
    assert report["layers"]["qem"] is not None
    assert report["layers"]["qem"]["header"]["document_id"] == "qem_identity_no_overhead"
    assert report["sources"]["qcvv"]["document_id"] == "qcvv_identity_no_overhead"
    assert report["sources"]["qem"]["document_id"] == "qem_identity_no_overhead"

    json.dumps(report, allow_nan=False)
    md = report_to_markdown(report)
    assert "Physical layer (OSRE snapshot)" in md
    assert "Notes:" in md
    assert "Logical fault model" in md
    assert "passthrough_from_modality" in md
    assert "System metrics (OSRE)" in md
    assert "`computed`" in md
    assert "system_metrics_v2" in md
    assert "Parameter sensitivity" in md
    assert "Logical failure proxy" in md
    assert "Magic supply adequate" in md


def test_build_report_ecdlp_secp256k1_babbush_low_toffoli() -> None:
    root = find_square_root()
    scenario = root / "Configs" / "ecdlp_secp256k1_babbush_2026_low_toffoli.yaml"
    bundle = load_scenario_bundle(scenario, root=root)
    report = build_scenario_report(bundle)

    assert report["report_contract_version"] == REPORT_CONTRACT_VERSION
    assert report["physical_layer"]["status"] == "passthrough_from_modality"
    assert report["physical_layer"]["document_id"] == "superconducting_babbush_et_al_2026"
    sm_ec = report["system_metrics"]
    assert sm_ec["schema"] == "system_metrics_v2"
    assert sm_ec["status"] == "partial"
    assert sm_ec["logical_qubit_capacity_lqc"] is None
    lfm = report["logical_fault_model"]
    assert lfm["status"] == "computed"
    assert lfm["inputs"]["ver_grounded_on_characteristic_only"] is VER_USES_HEADLINE_CHARACTERISTIC_FOR_VER
    assert lfm["inputs"]["p_nominal_gate_proxy_method"] == "max_1q_2q"
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
    assert sm_ec["validated_error_rate_ver"] == pytest.approx(0.001)
    lob_ec = sm_ec["logical_operations_budget_lob"]
    assert lob_ec is not None
    assert sm_ec["mitigated_operations_ceiling"] == pytest.approx(float(lob_ec))
    assert report["parameter_sensitivity"]["status"] == "computed"

    dash = report["dashboard"]
    assert dash.get("ecdlp_active") is True
    assert dash["ecdlp_variant"] == "low_toffoli_variant"
    assert dash["ecdlp_toffoli_gates_upper_bound"] == 70_000_000
    assert dash["ecdlp_paper_headline_physical_qubits_upper_bound"] == 500_000
    assert dash[DASHBOARD_LOGICAL_FAILURE_PROXY_KEY] == pytest.approx(
        min(1.0, 70_000_000.0 * float(p_l_ec))
    )
    assert dash.get("magic_supply_adequate") is None
    assert dash.get("magic_limited_runtime_multiplier") is None
    assert dash["t_factory_magic_aux_applicable_to_target"] is False
    assert dash["t_factory_transition_modulus_bits_order_of_magnitude"] is None
    assert dash["t_factory_fallback_recommended"] is False
    assert any("magic_aux T-factory transition metadata applies only" in str(x) for x in report["warnings"])
    assert any("dashboard.magic_throughput" in str(x) for x in report["warnings"])

    assert report["qec_distance_resolution"]["mode"] == "heuristic_union_bound"
    assert report["qec_distance_resolution"]["distance_d"] == 21
    timing = report["timing"]["naive_serial_from_measurement_depth"]
    assert timing is not None
    assert timing["source_parameters"]["depth"] == "ecdlp_logical_resource_envelopes_secp256k1_proxy"
    expected_days = 70_000_000.0 * 1.0 / 1e6 / 86400.0
    assert timing["serial_time_days"] == pytest.approx(expected_days)

    json.dumps(report, allow_nan=False)


def test_build_report_physical_layer_cain_neutral_atom() -> None:
    root = find_square_root()
    scenario = root / "Configs" / "oratomic_gold_path.yaml"
    bundle = load_scenario_bundle(scenario, root=root)
    report = build_scenario_report(bundle)
    pl = report["physical_layer"]
    assert report["report_contract_version"] == REPORT_CONTRACT_VERSION
    assert pl["document_id"] == "neutral_atom_cain_et_al_2026"
    assert pl["status"] == "passthrough_from_modality"
    assert pl["parameters"]["coherence_time_t1_microseconds"]["value"] == 15000.0
    assert report["logical_fault_model"]["logical_cycle_time"]["logical_cycle_time_microseconds"] == 40.0


def test_oratomic_gold_path_report() -> None:
    """Stable Oratomic gold path: same stack as Cain neutral-atom ECDLP; pinned for demos and CI."""
    root = find_square_root()
    scenario = root / "Configs" / "oratomic_gold_path.yaml"
    bundle = load_scenario_bundle(scenario, root=root)
    report = build_scenario_report(bundle)

    assert report["scenario"]["scenario"] == "oratomic_gold_path"
    assert report["report_contract_version"] == REPORT_CONTRACT_VERSION

    pl = report["physical_layer"]
    assert pl["document_id"] == "neutral_atom_cain_et_al_2026"
    assert pl["status"] == "passthrough_from_modality"
    assert pl["parameters"]["coherence_time_t1_microseconds"]["value"] == 15000.0

    assert report["layers"]["qec"]["header"]["document_id"] == "qldpc_cain_et_al_2026"
    assert report["layers"]["modality"]["header"]["document_id"] == "neutral_atom_cain_et_al_2026"
    assert report["layers"]["qcvv"] is not None
    assert report["layers"]["qem"] is not None

    lfm = report["logical_fault_model"]
    assert lfm["status"] == "computed"
    assert lfm["exponent_half_distance"] == 8
    assert lfm["logical_error_rate_per_cycle"] == pytest.approx(4.5423445187769087e-13, rel=1e-12)
    assert lfm["logical_cycle_time"]["logical_cycle_time_microseconds"] == 40.0

    qdr = report["qec_distance_resolution"]
    assert qdr["mode"] == "heuristic_union_bound"
    assert qdr["distance_d"] == 15

    ecdlp = report["algorithm_metrics"]["ecdlp"]
    assert ecdlp["active"] is True
    assert ecdlp["variant"] == "low_toffoli_variant"
    assert ecdlp["logical_qubits_upper_bound"] == 1450
    assert ecdlp["toffoli_gates_upper_bound"] == 70_000_000

    sm = report["system_metrics"]
    assert sm["schema"] == "system_metrics_v2"
    assert sm["status"] == "partial"
    assert sm["logical_qubit_capacity_lqc"] is None
    p_l = float(lfm["logical_error_rate_per_cycle"])
    assert sm["logical_operations_budget_lob"] == pytest.approx(0.1 / p_l)
    assert sm["headroom_logical_depth"] == pytest.approx(0.1 / p_l - 70_000_000.0)
    assert sm["quantum_operations_throughput_qot"] == pytest.approx(25_000.0)

    assert report["parameter_sensitivity"]["status"] == "computed"

    dash = report["dashboard"]
    assert dash["t_factory_magic_aux_applicable_to_target"] is False
    assert dash["t_factory_transition_modulus_bits_order_of_magnitude"] is None
    assert dash["t_factory_fallback_recommended"] is False
    assert dash["t_factory_fallback_non_clifford_mechanism"] is None
    assert any("magic_aux T-factory transition metadata applies only" in str(w) for w in report["warnings"])

    json.dumps(report, allow_nan=False)
    md = report_to_markdown(report)
    assert "oratomic_gold_path" in md


def test_rsa_magic_aux_recommends_fallback_when_n_above_transition() -> None:
    root = find_square_root()
    scenario = root / "Configs" / "rsa2048_gidney_ekera_2021_parallel.yaml"
    bundle = load_scenario_bundle(scenario, root=root)
    report = build_scenario_report(bundle, modulus_bits_override=40_000)
    dash = report["dashboard"]
    assert dash["t_factory_magic_aux_applicable_to_target"] is True
    assert dash["t_factory_fallback_recommended"] is True
    assert any("t_distillation_fowler_et_al_style" in str(w) for w in report["warnings"])


def test_build_report_surfaces_qcvv_qem_layers_when_loaded(tmp_path: Path) -> None:
    root = find_square_root()
    scen = tmp_path / "_test_qcvv_qem_report.yaml"
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


def test_rsa_mvp_repo_scenario_identity_qcvv_qem_heuristics() -> None:
    """MVP RSA flagship includes identity QCVV/QEM, Table-2 heuristics, VER, and mitigated ceiling."""
    root = find_square_root()
    report = build_scenario_report(
        load_scenario_bundle(root / "Configs" / "rsa2048_gidney_ekera_2021_parallel.yaml", root=root)
    )
    assert report["layers"]["qcvv"] is not None
    assert report["layers"]["qem"] is not None
    assert report["sources"]["qcvv"]["document_id"] == "qcvv_identity_no_overhead"
    assert report["sources"]["qem"]["document_id"] == "qem_identity_no_overhead"
    assert report["qec_distance_resolution"]["distance_d"] == 25
    assert report["dashboard"]["code_distance_d"] == 25
    assert report["system_metrics"]["validated_error_rate_ver"] == pytest.approx(0.001)
    lob = float(report["system_metrics"]["logical_operations_budget_lob"])
    assert report["system_metrics"]["mitigated_operations_ceiling"] == pytest.approx(lob)


def test_illustrative_ecdlp_qcvv_qem_repo_scenario_ver_and_mitigated_ceiling() -> None:
    """Illustrative QCVV σ=1.15 and QEM Γ=4: VER and mitigated ceiling match contract formulas."""
    root = find_square_root()
    report = build_scenario_report(
        load_scenario_bundle(
            root / "tests" / "fixtures" / "ecdlp_illustrative_qcvv_qem.yaml",
            root=root,
        )
    )
    assert report["layers"]["qcvv"]["header"]["document_id"] == "qcvv_benchmarking_operational_error_sigma_1_15"
    assert report["layers"]["qem"]["header"]["document_id"] == "qem_example_zne_style_stub"
    sm = report["system_metrics"]
    assert sm["validated_error_rate_ver"] == pytest.approx(0.001 * 1.15)
    lob = sm["logical_operations_budget_lob"]
    assert lob is not None
    assert sm["mitigated_operations_ceiling"] == pytest.approx(float(lob) / 4.0)


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

    json.dumps(report, allow_nan=False)


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


def test_build_scenario_report_mc_metrics_slice_matches_full_for_mc_extract() -> None:
    root = find_square_root()
    bundle = load_scenario_bundle(
        root / "Configs" / "ecdlp_secp256k1_babbush_2026_low_toffoli.yaml",
        root=root,
    )
    full = build_scenario_report(bundle)
    slim = build_scenario_report(bundle, outputs="mc_metrics")
    assert extract_default_mc_metrics(full) == extract_default_mc_metrics(slim)


def test_system_metrics_lob_note_distinguishes_p_l_from_ver() -> None:
    """LOB copy must not imply validated_error_rate_ver drives phenomenological p_L."""
    root = find_square_root()
    report = build_scenario_report(
        load_scenario_bundle(
            root / "Configs" / "rsa2048_gidney_ekera_2021_parallel.yaml",
            root=root,
        )
    )
    notes = report["system_metrics"]["notes"]
    lob_lines = [n for n in notes if n.startswith("LOB uses")]
    assert len(lob_lines) == 1
    assert "validated_error_rate_ver" in lob_lines[0]
    assert "VER+scaling in p_L" not in lob_lines[0]


def test_read_qcvv_characterization_error_multiplier() -> None:
    w: list[str] = []
    assert read_qcvv_characterization_error_multiplier(None, w) is None
    doc = {"effective_physical_error_rate_multiplier_from_characterization": {"value": 1.2, "unit": "ratio"}}
    assert read_qcvv_characterization_error_multiplier(doc, w, context="t") == pytest.approx(1.2)


def test_heuristic_phenomenological_disabled_skips_distance_and_p_l(tmp_path: Path) -> None:
    """``qec.heuristic_phenomenological_logical_error_model_applies: false`` gates phenomenology + heuristic d."""
    root = find_square_root()
    scen = tmp_path / "phenom_off.yaml"
    scen.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "scenario: _pytest_phenom_off",
                "description: test",
                "target:",
                "  problem: ecdlp_secp256k1_256_bit",
                "  curve_bit_length: 256",
                "  ecdlp_variant: low_toffoli_variant",
                "qec:",
                "  distance_policy: heuristic_union_bound",
                "  logical_error_budget: 0.1",
                "  heuristic_phenomenological_logical_error_model_applies: false",
                "paths:",
                "  modality: Assumptions/Modalities/superconducting_babbush_et_al_2026.yaml",
                "  qec_code: Assumptions/QEC_Codes/surface_gidney_ekera_2021.yaml",
                "  magic: Assumptions/MagicStateProduction/ccz_factory_gidney_ekera_2021.yaml",
                "  magic_aux: Assumptions/MagicStateProduction/t_factory_fallback_gidney_ekera_2021.yaml",
                "  algorithm: Algorithms/ecdlp_secp256k1_babbush_et_al_2026.yaml",
            ]
        ),
        encoding="utf-8",
    )
    report = build_scenario_report(load_scenario_bundle(scen, root=root))
    assert report["qec_distance_resolution"]["mode"] == "heuristic_disabled_by_assumption"
    assert report["qec_distance_resolution"]["distance_d"] is None
    assert report["logical_fault_model"]["status"] == "model_disabled_by_assumption"
    assert report["logical_fault_model"]["logical_error_rate_per_cycle"] is None
    assert report["dashboard"]["code_distance_d"] is None
    assert report["dashboard"][DASHBOARD_LOGICAL_FAILURE_PROXY_KEY] is None
