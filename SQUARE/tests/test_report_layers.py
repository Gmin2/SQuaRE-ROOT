"""Tests for ``square.report_layers``."""

from __future__ import annotations

from pathlib import Path

from square.loader import find_square_root, load_scenario_bundle
from square.report_layers import build_report_sources_and_layers, split_document


def test_split_document_separates_header_and_parameters() -> None:
    doc = {
        "document_id": "x",
        "schema_version": 1,
        "foo": {"value": 1.0, "unit": "u"},
        "extra_meta": "keep in header side",
    }
    h, p = split_document(doc)
    assert h["document_id"] == "x"
    assert "foo" in p
    assert "extra_meta" in h


def test_build_report_sources_and_layers_smoke(tmp_path: Path) -> None:
    root = find_square_root()
    scen = tmp_path / "s.yaml"
    scen.write_text(
        "schema_version: 1\nscenario: t\npaths:\n"
        "  modality: Assumptions/Modalities/superconducting_gidney_ekera_2021.yaml\n"
        "  qec_code: Assumptions/QEC_Codes/surface_gidney_ekera_2021.yaml\n"
        "  magic: Assumptions/MagicStateProduction/ccz_factory_gidney_ekera_2021.yaml\n"
        "  algorithm: Algorithms/shor_rsa_gidney_ekera_2021.yaml\n",
        encoding="utf-8",
    )
    bundle = load_scenario_bundle(scen, root=root)
    sl = build_report_sources_and_layers(bundle, bundle.algorithm)
    assert "modality" in sl.sources
    assert sl.layers["algorithm"]["document_id"] == "shor_rsa_gidney_ekera_2021"
    assert sl.modality_parameters
