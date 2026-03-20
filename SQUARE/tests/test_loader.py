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

    assert bundle.algorithm["toffoli_plus_t_halves_count_billions_n_2048"]["value"] == 2.7


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
