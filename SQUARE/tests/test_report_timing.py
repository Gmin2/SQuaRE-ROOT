"""Tests for ``square.report_timing``."""

from __future__ import annotations

from square.report_timing import build_timing_section


def test_build_timing_section_empty_evaluated_minimal_block() -> None:
    warnings: list[str] = []
    out = build_timing_section(
        evaluated={},
        modality={},
        scenario={},
        table2_block=None,
        table2_rsa2048_rows_key="paper_table2_rsa2048_reference_rows",
        ecdlp_block_for_metrics=None,
        early_pins={},
        warnings=warnings,
    )
    assert out.timing_block["reported_table2_pinned"] is None
    assert out.timing_block["naive_serial_from_measurement_depth"] is None
    assert out.timing_block["schedule_model_v1"] is None
    assert out.naive_serial_timing is None
