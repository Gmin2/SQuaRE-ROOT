"""Tests for scenario → YAML bundle loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from square.loader import find_square_root, load_scenario_bundle


def test_find_square_root_from_repo() -> None:
    root = find_square_root()
    assert (root / "Assumptions" / "Schemas.yaml").is_file()


def test_load_rsa2048_gidney_ekera_2021_parallel() -> None:
    root = find_square_root()
    scenario = root / "Configs" / "rsa2048_gidney_ekera_2021_parallel.yaml"
    assert scenario.is_file(), f"Missing scenario file: {scenario}"

    bundle = load_scenario_bundle(scenario, root=root)

    assert bundle.scenario.get("scenario") == "rsa2048_gidney_ekera_2021_parallel"
    assert bundle.scenario.get("schema_version") == 1

    assert bundle.modality["document_id"] == "superconducting_gidney_ekera_2021"
    assert bundle.qec["document_id"] == "surface_gidney_ekera_2021"
    assert bundle.magic["document_id"] == "ccz_factory_gidney_ekera_2021"
    assert bundle.algorithm["document_id"] == "shor_rsa_gidney_ekera_2021"

    assert bundle.magic_aux is not None
    assert bundle.magic_aux["document_id"] == "t_factory_fallback_gidney_ekera_2021"

    assert bundle.qcvv is None
    assert bundle.qem is None

    t1 = bundle.algorithm["paper_table1_pins_by_modulus_bit_length"]["value"]["2048"]
    assert t1["toffoli_plus_t_halves_billions"] == 2.7
    assert t1["minimum_spacetime_volume_megaqubit_days"] == 5.9


def test_load_scenario_missing_path_raises() -> None:
    root = find_square_root()
    bad = Path(root / "Configs" / "_nonexistent_scenario.yaml")
    bad.write_text(
        "schema_version: 1\nscenario: x\npaths:\n  modality: Assumptions/Modalities/superconducting_gidney_ekera_2021.yaml\n"
        "  qec_code: Assumptions/QEC_Codes/surface_gidney_ekera_2021.yaml\n"
        "  magic: Assumptions/MagicStateProduction/ccz_factory_gidney_ekera_2021.yaml\n"
        "  algorithm: Algorithms/does_not_exist.yaml\n",
        encoding="utf-8",
    )
    try:
        with pytest.raises(FileNotFoundError):
            load_scenario_bundle(bad, root=root)
    finally:
        bad.unlink(missing_ok=True)


def test_load_optional_qcvv_and_qem_paths() -> None:
    root = find_square_root()
    scen = root / "Configs" / "_test_qcvv_qem_bundle.yaml"
    scen.write_text(
        "schema_version: 1\nscenario: _test_qcvv_qem\npaths:\n"
        "  modality: Assumptions/Modalities/superconducting_gidney_ekera_2021.yaml\n"
        "  qec_code: Assumptions/QEC_Codes/surface_gidney_ekera_2021.yaml\n"
        "  magic: Assumptions/MagicStateProduction/ccz_factory_gidney_ekera_2021.yaml\n"
        "  algorithm: Algorithms/shor_rsa_gidney_ekera_2021.yaml\n"
        "  qcvv: Assumptions/QCVV/identity_no_overhead.yaml\n"
        "  qem: Assumptions/QEM/identity_no_overhead.yaml\n",
        encoding="utf-8",
    )
    try:
        bundle = load_scenario_bundle(scen, root=root)
        assert bundle.qcvv is not None
        assert bundle.qcvv["document_id"] == "qcvv_identity_no_overhead"
        assert bundle.qem is not None
        assert bundle.qem["document_id"] == "qem_identity_no_overhead"
    finally:
        scen.unlink(missing_ok=True)


def test_load_ecdlp_secp256k1_babbush_2026_low_toffoli() -> None:
    root = find_square_root()
    scenario = root / "Configs" / "ecdlp_secp256k1_babbush_2026_low_toffoli.yaml"
    assert scenario.is_file(), f"Missing scenario file: {scenario}"

    bundle = load_scenario_bundle(scenario, root=root)

    assert bundle.scenario.get("scenario") == "ecdlp_secp256k1_babbush_2026_low_toffoli"
    assert bundle.modality["document_id"] == "superconducting_babbush_et_al_2026"
    assert bundle.algorithm["document_id"] == "ecdlp_secp256k1_babbush_et_al_2026"
    env = bundle.algorithm["ecdlp_logical_resource_envelopes_secp256k1"]["value"]["low_toffoli_variant"]
    assert env["logical_qubits_upper_bound"] == 1450
    assert env["toffoli_gates_upper_bound"] == 70_000_000


def test_load_ecdlp_secp256k1_cain_2026_neutral_atom_qldpc() -> None:
    root = find_square_root()
    scenario = root / "Configs" / "ecdlp_secp256k1_cain_2026_neutral_atom_qldpc.yaml"
    assert scenario.is_file(), f"Missing scenario file: {scenario}"

    bundle = load_scenario_bundle(scenario, root=root)

    assert bundle.scenario.get("scenario") == "ecdlp_secp256k1_cain_2026_neutral_atom_qldpc"
    assert bundle.modality["document_id"] == "neutral_atom_cain_et_al_2026"
    assert bundle.qec["document_id"] == "qldpc_cain_et_al_2026"
    assert bundle.qec["code_family"]["value"] == "quantum_ldpc"
    assert bundle.algorithm["document_id"] == "ecdlp_secp256k1_babbush_et_al_2026"
