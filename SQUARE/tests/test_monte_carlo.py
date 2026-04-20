"""Monte Carlo forward model, sampling loop, CLI."""

from __future__ import annotations

import json
import random
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
    write_mc_samples_csv,
    write_mc_summary_json,
)
from square.mc.overrides import apply_numeric_overrides


def test_parameter_layers_nonempty() -> None:
    assert "characteristic_physical_gate_error_rate" in PARAMETER_LAYERS


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
    with pytest.raises(KeyError):
        apply_numeric_overrides(bundle, {"not_a_parameter": 1.0})


def test_load_study_spec_relative() -> None:
    spec = load_monte_carlo_study_spec("Configs/monte_carlo_study_ecdlp_example.yaml")
    assert spec.study_id == "mc_ecdlp_gate_and_cycle_priors"
    assert len(spec.parameters) == 3
    assert spec.sampling_strategy == "independent"


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
        root / "Configs" / "monte_carlo_study_ecdlp_example.yaml",
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


def test_latin_hypercube_requires_all_uniform() -> None:
    root = find_square_root()
    spec = load_monte_carlo_study_spec(
        root / "Configs" / "monte_carlo_study_ecdlp_example.yaml",
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
    spec = load_monte_carlo_study_spec(root / "Configs" / "monte_carlo_study_ecdlp_lhs.yaml", root=root)
    assert spec.sampling_strategy == "latin_hypercube"
    bundle = load_scenario_bundle(root / spec.base_scenario, root=root)
    result = run_monte_carlo_study(spec, bundle, n_samples=12, seed=99, include_full_report=False)
    assert len(result.rows) == 12
    assert result.summary["sampling_strategy"] == "latin_hypercube"


def test_monte_carlo_parallel_threads() -> None:
    root = find_square_root()
    spec = load_monte_carlo_study_spec(
        root / "Configs" / "monte_carlo_study_ecdlp_example.yaml",
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
            str(root / "Configs" / "monte_carlo_study_ecdlp_example.yaml"),
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
