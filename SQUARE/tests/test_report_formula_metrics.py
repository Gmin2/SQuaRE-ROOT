"""Tests for ``square.report_formula_metrics``."""

from __future__ import annotations

from square.report_formula_metrics import (
    FORMULA_METRICS,
    evaluate_non_ecdlp_formula_metrics,
)


def test_evaluate_non_ecdlp_formula_metrics_skips_when_no_modulus_bits() -> None:
    warnings: list[str] = []
    algo: dict = {}
    target: dict = {}
    r = evaluate_non_ecdlp_formula_metrics(algo, target, modulus_bits_override=None, warnings=warnings)
    assert r.n is None
    assert r.evaluated == {}
    assert any("modulus_bit_length" in w for w in warnings)


def test_formula_metrics_tuple_matches_report_ecdlp_skipped_list_length() -> None:
    assert len(FORMULA_METRICS) == 3
