"""Tests for ``square.report_physical_layout``."""

from __future__ import annotations

from square.report_physical_layout import build_physical_rollup_and_layout_estimate


def test_build_physical_rollup_minimal() -> None:
    warnings: list[str] = []
    phys = build_physical_rollup_and_layout_estimate(
        magic={},
        evaluated={"abstract_logical_qubits": {"value": 10.0}},
        early_pins={"ccz_count": None, "rsa2048_phys": None},
        d_resolved=5,
        patch_physical_per_logical=18.0,
        qec_patch_status="evaluated",
        warnings=warnings,
    )
    assert phys.logical_qubits_val == 10.0
    assert phys.approx_data_physical == 180.0
    assert phys.physical_rollup["code_distance_d"] == 5
