"""Monte Carlo forward model, sampling loop, CLI."""

from __future__ import annotations

import json
import random
import uuid
from pathlib import Path

import pytest
from square.loader import find_square_root, load_scenario_bundle
from square.mc import (
    MC_SUMMARY_CONTRACT_VERSION,
    PARAMETER_LAYERS,
    evaluate_forward_model,
    load_monte_carlo_study_spec,
    run_monte_carlo_study,
    sample_parameter_value,
    validate_distribution_spec,
    write_mc_samples_csv,
    write_mc_summary_json,
)
from square.mc.forward_model import MC_STRICT_REQUIRED_METRIC_KEYS
from square.mc.lhs import generate_lhs_uniform_thetas
from square.mc.overrides import apply_numeric_overrides


def test_parameter_layers_nonempty() -> None:
    assert "characteristic_physical_gate_error_rate" in PARAMETER_LAYERS
    assert PARAMETER_LAYERS["single_qubit_gate_error_rate"] == "modality"
    assert PARAMETER_LAYERS["two_qubit_gate_error_rate"] == "modality"


def test_parameter_layers_covers_modality_gate_rates_for_heuristic_p_nominal() -> None:
    """Monte Carlo must be able to perturb every modality key that feeds ``read_modality_nominal_gate_error_for_heuristic``."""
    required = frozenset(
        {
            "characteristic_physical_gate_error_rate",
            "single_qubit_gate_error_rate",
            "two_qubit_gate_error_rate",
        }
    )
    missing = sorted(k for k in required if k not in PARAMETER_LAYERS)
    assert not missing, f"PARAMETER_LAYERS missing keys: {missing}"


def test_apply_numeric_overrides_two_qubit_changes_p_nominal_in_report() -> None:
    root = find_square_root()
    bundle = load_scenario_bundle(
        root / "Configs" / "ecdlp_secp256k1_babbush_2026_low_toffoli.yaml",
        root=root,
    )
    from square.report import build_scenario_report

    base = build_scenario_report(bundle)
    assert base["logical_fault_model"]["inputs"]["p_nominal"] == pytest.approx(0.001)
    b2 = apply_numeric_overrides(bundle, {"two_qubit_gate_error_rate": 0.009})
    r2 = build_scenario_report(b2)
    assert r2["logical_fault_model"]["inputs"]["p_nominal"] == pytest.approx(0.009)


def test_monte_carlo_study_with_1q2q_parameters_runs() -> None:
    root = find_square_root()
    spec = load_monte_carlo_study_spec(root / "tests" / "fixtures" / "monte_carlo_study_ecdlp_with_1q2q.yaml", root=root)
    assert spec.study_id == "mc_ecdlp_gate_rates_and_cycle_priors"
    assert len(spec.parameters) == 5
    bundle = load_scenario_bundle(root / spec.base_scenario, root=root)
    result = run_monte_carlo_study(spec, bundle, n_samples=6, seed=42, include_full_report=False)
    assert len(result.rows) == 6


def test_evaluate_forward_model_baseline_matches_report() -> None:
    root = find_square_root()
    bundle = load_scenario_bundle(
        root / "Configs" / "ecdlp_secp256k1_babbush_2026_low_toffoli.yaml",
        root=root,
    )
    from square.report import build_scenario_report

    r1 = build_scenario_report(bundle)
    r2 = evaluate_forward_model(bundle, numeric_overrides=None, include_full_report=True).report
    assert r2 is not None
    assert r1["dashboard"]["code_distance_d"] == r2["dashboard"]["code_distance_d"]


def test_apply_numeric_overrides_unknown_key() -> None:
    root = find_square_root()
    bundle = load_scenario_bundle(
        root / "Configs" / "ecdlp_secp256k1_babbush_2026_low_toffoli.yaml",
        root=root,
    )
    with pytest.raises(ValueError, match="Unknown override parameter"):
        apply_numeric_overrides(bundle, {"not_a_parameter": 1.0})


def test_load_study_spec_relative() -> None:
    spec = load_monte_carlo_study_spec("tests/fixtures/monte_carlo_study_ecdlp_example.yaml")
    assert spec.study_id == "mc_ecdlp_gate_and_cycle_priors"
    assert len(spec.parameters) == 3
    assert spec.sampling_strategy == "independent"
    assert spec.strict_metrics is False


def test_load_monte_carlo_study_strict_metrics_from_yaml() -> None:
    root = find_square_root()
    study = root / "tests" / "fixtures" / "mc_study_strict_metrics_true.yaml"
    spec = load_monte_carlo_study_spec(study, root=root)
    assert spec.strict_metrics is True


def test_load_monte_carlo_study_spec_rejects_escape_relative_to_root() -> None:
    root = find_square_root()
    with pytest.raises(ValueError, match="under SQuaRE root"):
        load_monte_carlo_study_spec("..", root=root)


def test_evaluate_forward_model_mc_metrics_matches_full_extract() -> None:
    """``include_full_report=False`` must not change extracted MC metrics vs full report."""
    root = find_square_root()
    bundle = load_scenario_bundle(
        root / "Configs" / "ecdlp_secp256k1_babbush_2026_low_toffoli.yaml",
        root=root,
    )
    theta = {
        "characteristic_physical_gate_error_rate": 0.001,
        "surface_code_cycle_time": 1.0,
        "heuristic_surface_code_physical_threshold_order_of_magnitude": 0.01,
    }
    full_m = evaluate_forward_model(
        bundle, numeric_overrides=theta, include_full_report=True
    ).metrics
    slim_m = evaluate_forward_model(
        bundle, numeric_overrides=theta, include_full_report=False
    ).metrics
    assert full_m == slim_m


def test_validate_distribution_requires_strictly_increasing_bounds() -> None:
    with pytest.raises(ValueError, match="low < high"):
        validate_distribution_spec({"distribution": "uniform", "low": 1.0, "high": 1.0})
    with pytest.raises(ValueError, match="low < high"):
        validate_distribution_spec({"distribution": "uniform", "low": 2.0, "high": 1.0})
    with pytest.raises(ValueError, match="low < high"):
        validate_distribution_spec({"distribution": "log_uniform", "low": 1.0, "high": 0.5})
    with pytest.raises(ValueError, match="strictly positive"):
        validate_distribution_spec({"distribution": "log_uniform", "low": 0.0, "high": 1.0})


def test_load_monte_carlo_study_rejects_inverted_uniform_bounds() -> None:
    root = find_square_root()
    with pytest.raises(ValueError, match="low < high"):
        load_monte_carlo_study_spec(root / "tests" / "fixtures" / "mc_study_bad_uniform_bounds.yaml", root=root)


def test_sample_parameter_value_rejects_inverted_uniform() -> None:
    rng = random.Random(0)
    with pytest.raises(ValueError, match="low < high"):
        sample_parameter_value({"distribution": "uniform", "low": 3.0, "high": 1.0}, rng)


def _stratum_index(x: float, lo: float, hi: float, n: int) -> int:
    w = (hi - lo) / n
    idx = int((x - lo) / w)
    if idx >= n:
        idx = n - 1
    if idx < 0:
        idx = 0
    return idx


def test_lhs_uniform_one_draw_per_stratum_per_dimension() -> None:
    """Each LHS dimension should visit each equal-width stratum exactly once across n_samples."""
    n_samples = 11
    blocks = [
        {"parameter_key": "p0", "distribution": "uniform", "low": 0.0, "high": 10.0},
        {"parameter_key": "p1", "distribution": "uniform", "low": -3.0, "high": 7.0},
        {"parameter_key": "p2", "distribution": "uniform", "low": 100.0, "high": 200.0},
    ]
    thetas = generate_lhs_uniform_thetas(blocks, n_samples, random.Random(12345))
    assert len(thetas) == n_samples
    for b in blocks:
        key = str(b["parameter_key"])
        lo_r, hi_r = b["low"], b["high"]
        assert isinstance(lo_r, (int, float)) and isinstance(hi_r, (int, float))
        lo, hi = float(lo_r), float(hi_r)
        for th in thetas:
            v = th[key]
            assert lo <= v <= hi
        strata = sorted(_stratum_index(th[key], lo, hi, n_samples) for th in thetas)
        assert strata == list(range(n_samples))


def test_sample_parameter_reproducible() -> None:
    spec = {"distribution": "uniform", "low": 0.0, "high": 1.0}
    rng = random.Random(7)
    a = sample_parameter_value(spec, rng)
    rng = random.Random(7)
    b = sample_parameter_value(spec, rng)
    assert a == b


def test_run_monte_carlo_study_small() -> None:
    root = find_square_root()
    spec = load_monte_carlo_study_spec(
        root / "tests" / "fixtures" / "monte_carlo_study_ecdlp_example.yaml",
        root=root,
    )
    bundle = load_scenario_bundle(root / spec.base_scenario, root=root)
    result = run_monte_carlo_study(spec, bundle, n_samples=8, seed=123, include_full_report=False)
    assert len(result.rows) == 8
    assert result.rows[0]["sample_index"] == 0
    assert "naive_serial_time_days" in result.rows[0]
    q = result.summary["quantiles"]
    assert "naive_serial_time_days" in q
    assert "p50" in q["naive_serial_time_days"]
    assert "moments" in result.summary
    assert "mean" in result.summary["moments"]["naive_serial_time_days"]
    assert "correlations" in result.summary
    assert result.summary["mc_summary_contract_version"] == MC_SUMMARY_CONTRACT_VERSION
    assert result.summary["strict_metrics"] is False
    assert "column_numeric_present_counts" in result.summary
    assert "summary_degraded_from_row_filtering" in result.summary
    assert "notes" in result.summary
    assert result.summary["mc_joint_sampling_disclaimer"]
    assert result.summary["strict_metrics_required_keys"] == list(MC_STRICT_REQUIRED_METRIC_KEYS)


def test_latin_hypercube_requires_all_uniform() -> None:
    root = find_square_root()
    spec = load_monte_carlo_study_spec(
        root / "tests" / "fixtures" / "monte_carlo_study_ecdlp_example.yaml",
        root=root,
    )
    bundle = load_scenario_bundle(root / spec.base_scenario, root=root)
    with pytest.raises(ValueError, match="latin_hypercube requires"):
        run_monte_carlo_study(
            spec,
            bundle,
            n_samples=4,
            seed=1,
            include_full_report=False,
            sampling_strategy="latin_hypercube",
        )


def test_latin_hypercube_study_runs() -> None:
    root = find_square_root()
    spec = load_monte_carlo_study_spec(root / "tests" / "fixtures" / "monte_carlo_study_ecdlp_lhs.yaml", root=root)
    assert spec.sampling_strategy == "latin_hypercube"
    bundle = load_scenario_bundle(root / spec.base_scenario, root=root)
    result = run_monte_carlo_study(spec, bundle, n_samples=12, seed=99, include_full_report=False)
    assert len(result.rows) == 12
    assert result.summary["sampling_strategy"] == "latin_hypercube"
    assert result.summary["mc_joint_sampling_disclaimer"]
    assert result.summary["strict_metrics_required_keys"] == list(MC_STRICT_REQUIRED_METRIC_KEYS)
    bounds = {str(b["parameter_key"]): (float(b["low"]), float(b["high"])) for b in spec.parameters}
    for row in result.rows:
        for k, (lo, hi) in bounds.items():
            v = row[k]
            assert isinstance(v, (int, float))
            assert lo <= float(v) <= hi
    for key, (lo, hi) in bounds.items():
        strata = sorted(_stratum_index(float(row[key]), lo, hi, 12) for row in result.rows)
        assert strata == list(range(12))


def test_monte_carlo_parallel_threads() -> None:
    root = find_square_root()
    spec = load_monte_carlo_study_spec(
        root / "tests" / "fixtures" / "monte_carlo_study_ecdlp_example.yaml",
        root=root,
    )
    bundle = load_scenario_bundle(root / spec.base_scenario, root=root)
    result = run_monte_carlo_study(
        spec, bundle, n_samples=6, seed=2, include_full_report=False, n_jobs=2
    )
    assert len(result.rows) == 6
    assert result.summary["n_jobs"] == 2


def test_write_mc_summary_json_rejects_non_finite_floats(tmp_path: Path) -> None:
    from square.mc.run_sampling import write_mc_summary_json

    bad = {"x": float("nan")}
    with pytest.raises(ValueError, match="cannot serialize MC summary"):
        write_mc_summary_json(tmp_path / "bad.json", bad)


def test_write_csv_and_summary_roundtrip(tmp_path: Path) -> None:
    rows = [
        {"sample_index": 0, "x": 1.0, "m": 2.0},
        {"sample_index": 1, "x": 3.0, "m": 4.0},
    ]
    summary = {"quantiles": {"m": {"p50": 3.0}}}
    csv_p = tmp_path / "s.csv"
    json_p = tmp_path / "s.json"
    write_mc_samples_csv(csv_p, rows)
    write_mc_summary_json(json_p, summary)
    assert csv_p.read_text(encoding="utf-8")
    assert json.loads(json_p.read_text(encoding="utf-8"))["quantiles"]["m"]["p50"] == 3.0


def test_cli_mc_main_smoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from square import cli_mc

    root = find_square_root()
    monkeypatch.chdir(tmp_path)
    code = cli_mc.main(
        [
            str(root / "tests" / "fixtures" / "monte_carlo_study_ecdlp_example.yaml"),
            "--samples",
            "4",
            "--seed",
            "1",
            "--output-csv",
            str(tmp_path / "out.csv"),
            "--summary-json",
            str(tmp_path / "out.json"),
            "--root",
            str(root),
        ]
    )
    assert code == 0
    assert (tmp_path / "out.csv").is_file()
    assert (tmp_path / "out.json").is_file()
    data = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert data["n_samples"] == 4
    assert "quantiles" in data
    assert data["mc_summary_contract_version"] == MC_SUMMARY_CONTRACT_VERSION


def test_cli_mc_rejects_non_positive_jobs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from square import cli_mc

    root = find_square_root()
    monkeypatch.chdir(tmp_path)
    code = cli_mc.main(
        [
            str(root / "tests" / "fixtures" / "monte_carlo_study_ecdlp_example.yaml"),
            "--samples",
            "1",
            "--jobs",
            "0",
            "--root",
            str(root),
        ]
    )
    assert code == 2


def test_cli_mc_rejects_non_positive_samples(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from square import cli_mc

    root = find_square_root()
    monkeypatch.chdir(tmp_path)
    code = cli_mc.main(
        [
            str(root / "tests" / "fixtures" / "monte_carlo_study_ecdlp_example.yaml"),
            "--samples",
            "-1",
            "--root",
            str(root),
        ]
    )
    assert code == 2


def test_cli_mc_rejects_base_scenario_path_outside_root(tmp_path: Path) -> None:
    """``base_scenario`` must resolve under ``--root`` (no absolute fallback outside the tree)."""
    from square import cli_mc

    root = find_square_root()
    study = tmp_path / "bad_escape.yaml"
    study.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "study_id: bad_escape",
                "description: test",
                "scope: prior_predictive_only",
                "base_scenario: ..",
                "parameters:",
                "  - parameter_key: characteristic_physical_gate_error_rate",
                "    distribution: uniform",
                "    low: 0.0005",
                "    high: 0.002",
            ]
        ),
        encoding="utf-8",
    )
    code = cli_mc.main([str(study), "--samples", "1", "--root", str(root)])
    assert code == 1


def test_cli_mc_malformed_study_yaml_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    from square import cli_mc

    root = find_square_root()
    fname = f"_pytest_cli_mc_bad_parameters_{uuid.uuid4().hex}.yaml"
    study = root / "Configs" / fname
    study.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "study_id: bad_params",
                "description: test",
                "scope: prior_predictive_only",
                "base_scenario: Configs/ecdlp_secp256k1_babbush_2026_low_toffoli.yaml",
                "parameters: not_a_list",
            ]
        ),
        encoding="utf-8",
    )
    try:
        monkeypatch.chdir(root)
        code = cli_mc.main([f"Configs/{fname}", "--samples", "1", "--root", str(root)])
        assert code == 1
    finally:
        study.unlink(missing_ok=True)


def test_cli_mc_bad_schema_version_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    from square import cli_mc

    root = find_square_root()
    fname = f"_pytest_cli_mc_bad_schema_version_{uuid.uuid4().hex}.yaml"
    study = root / "Configs" / fname
    study.write_text(
        "\n".join(
            [
                "schema_version: not_an_int",
                "study_id: bad_schema",
                "description: test",
                "scope: prior_predictive_only",
                "base_scenario: Configs/ecdlp_secp256k1_babbush_2026_low_toffoli.yaml",
                "parameters:",
                "  - parameter_key: characteristic_physical_gate_error_rate",
                "    distribution: uniform",
                "    low: 0.0005",
                "    high: 0.002",
            ]
        ),
        encoding="utf-8",
    )
    try:
        monkeypatch.chdir(root)
        code = cli_mc.main([f"Configs/{fname}", "--samples", "1", "--root", str(root)])
        assert code == 1
    finally:
        study.unlink(missing_ok=True)


def test_cli_mc_bundle_load_failure_returns_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Valid study + scenario file, but scenario ``paths.*`` points at a missing file → exit 1."""
    from square import cli_mc

    root = find_square_root()
    uid = uuid.uuid4().hex
    scen_name = f"_pytest_mc_bad_scenario_paths_{uid}.yaml"
    study_name = f"_pytest_mc_study_bad_bundle_{uid}.yaml"
    scen = root / "Configs" / scen_name
    study = root / "Configs" / study_name
    scen.write_text(
        "schema_version: 1\nscenario: _pytest_mc_bad_paths\npaths:\n"
        "  modality: Assumptions/Modalities/superconducting_gidney_ekera_2021.yaml\n"
        "  qec_code: Assumptions/QEC_Codes/surface_gidney_ekera_2021.yaml\n"
        "  magic: Assumptions/MagicStateProduction/ccz_factory_gidney_ekera_2021.yaml\n"
        "  algorithm: Algorithms/does_not_exist_mc_cli_bundle.yaml\n",
        encoding="utf-8",
    )
    study.write_text(
        "\n".join(
            [
                "schema_version: 1",
                "study_id: mc_bad_bundle_cli",
                "description: test",
                "scope: prior_predictive_only",
                f"base_scenario: Configs/{scen_name}",
                "parameters:",
                "  - parameter_key: characteristic_physical_gate_error_rate",
                "    distribution: uniform",
                "    low: 0.0005",
                "    high: 0.002",
                "  - parameter_key: surface_code_cycle_time",
                "    distribution: log_uniform",
                "    low: 0.5",
                "    high: 2.0",
                "  - parameter_key: heuristic_surface_code_physical_threshold_order_of_magnitude",
                "    distribution: uniform",
                "    low: 0.005",
                "    high: 0.02",
            ]
        ),
        encoding="utf-8",
    )
    try:
        monkeypatch.chdir(root)
        code = cli_mc.main([f"Configs/{study_name}", "--samples", "2", "--root", str(root)])
        assert code == 1
    finally:
        study.unlink(missing_ok=True)
        scen.unlink(missing_ok=True)
