"""Tests for ``square.report_formula_metrics``."""

from __future__ import annotations

from typing import cast

import pytest
from square.report_formula_metrics import (
    EXPONENT_REGISTER_EVALUATED_KEY,
    EXPONENT_REGISTER_SOURCE_KEY,
    FORMULA_METRIC_SOURCE_KEYS,
    FORMULA_METRICS,
    ecdlp_evaluated_skipped_formula_keys,
    evaluate_non_ecdlp_formula_metrics,
    is_asymptotic_formula_string,
)


@pytest.mark.parametrize(
    ("s", "expected"),
    [
        ("3 * n + 0.002 * n * log2(n)", False),
        ("O(n^3)", True),
        ("O(1)", True),
        ("n + O(log n)", True),
    ],
)
def test_is_asymptotic_formula_string(s: str, expected: bool) -> None:
    assert is_asymptotic_formula_string(s) is expected


def test_ecdlp_skipped_formula_keys_match_report_formula_metrics() -> None:
    """ECDLP ``evaluated_skipped`` must stay aligned with :func:`ecdlp_evaluated_skipped_formula_keys`."""
    assert ecdlp_evaluated_skipped_formula_keys() == FORMULA_METRIC_SOURCE_KEYS + (EXPONENT_REGISTER_SOURCE_KEY,)


def test_evaluate_non_ecdlp_formula_metrics_skips_when_no_modulus_bits() -> None:
    warnings: list[str] = []
    algo: dict = {}
    target: dict = {}
    r = evaluate_non_ecdlp_formula_metrics(algo, target, modulus_bits_override=None, warnings=warnings)
    assert r.n is None
    assert r.evaluated == {}
    assert any("modulus_bit_length" in w for w in warnings)


def test_evaluate_rejects_boolean_modulus_bit_length() -> None:
    warnings: list[str] = []
    algo = {"abstract_logical_qubits_formula": {"value": "n", "unit": "c"}}
    r = evaluate_non_ecdlp_formula_metrics(algo, {"modulus_bit_length": True}, modulus_bits_override=None, warnings=warnings)
    assert r.n is None
    assert r.evaluated == {}
    assert any("boolean" in w for w in warnings)


def test_evaluate_rejects_boolean_modulus_bits_override() -> None:
    warnings: list[str] = []
    algo = {"abstract_logical_qubits_formula": {"value": "n", "unit": "c"}}
    r = evaluate_non_ecdlp_formula_metrics(
        algo,
        {"modulus_bit_length": 100},
        modulus_bits_override=cast(int | None, True),
        warnings=warnings,
    )
    assert r.n is None
    assert any("boolean" in w for w in warnings)


def test_evaluate_non_ecdlp_formula_metrics_happy_path() -> None:
    warnings: list[str] = []
    algo = {
        "abstract_logical_qubits_formula": {"value": "3 * n", "unit": "count"},
        "abstract_measurement_depth_formula": {"value": "n * n", "unit": "layers"},
        "abstract_toffoli_plus_t_halves_count_formula": {"value": "2 * n", "unit": "count"},
    }
    target = {"modulus_bit_length": 10}
    r = evaluate_non_ecdlp_formula_metrics(algo, target, modulus_bits_override=None, warnings=warnings)
    assert r.n == 10
    assert r.evaluated["abstract_logical_qubits"]["value"] == pytest.approx(30.0)
    assert r.evaluated["abstract_measurement_depth_layers"]["value"] == pytest.approx(100.0)
    assert r.evaluated["abstract_toffoli_plus_t_halves_count"]["value"] == pytest.approx(20.0)
    assert not warnings


def test_modulus_bits_override_beats_target() -> None:
    warnings: list[str] = []
    algo = {"abstract_logical_qubits_formula": {"value": "n", "unit": "count"}}
    target = {"modulus_bit_length": 100}
    r = evaluate_non_ecdlp_formula_metrics(algo, target, modulus_bits_override=7, warnings=warnings)
    assert r.n == 7
    assert r.evaluated["abstract_logical_qubits"]["value"] == pytest.approx(7.0)


def test_evaluate_skips_asymptotic_with_warning() -> None:
    warnings: list[str] = []
    algo = {
        "abstract_logical_qubits_formula": {"value": "O(n^2)", "unit": "str"},
        "abstract_measurement_depth_formula": {"value": "n", "unit": "layers"},
        "abstract_toffoli_plus_t_halves_count_formula": {"value": "2 * n", "unit": "count"},
    }
    target = {"modulus_bit_length": 8}
    r = evaluate_non_ecdlp_formula_metrics(algo, target, modulus_bits_override=None, warnings=warnings)
    assert "abstract_logical_qubits" not in r.evaluated
    assert "abstract_logical_qubits_formula" in r.evaluated_skipped
    assert r.evaluated["abstract_measurement_depth_layers"]["value"] == pytest.approx(8.0)
    assert r.evaluated["abstract_toffoli_plus_t_halves_count"]["value"] == pytest.approx(16.0)
    assert sum(1 for w in warnings if "asymptotic marker" in w and "abstract_logical_qubits_formula" in w) == 1


def test_evaluate_formula_eval_error_warns_and_skips() -> None:
    warnings: list[str] = []
    algo = {"abstract_logical_qubits_formula": {"value": "unknown_var + n", "unit": "x"}}
    target = {"modulus_bit_length": 4}
    r = evaluate_non_ecdlp_formula_metrics(algo, target, modulus_bits_override=None, warnings=warnings)
    assert "abstract_logical_qubits" not in r.evaluated
    assert "abstract_logical_qubits_formula" in r.evaluated_skipped
    assert any("Could not evaluate" in w for w in warnings)


def test_evaluate_warns_when_formula_entry_not_mapping() -> None:
    warnings: list[str] = []
    algo = {"abstract_logical_qubits_formula": "not_a_dict"}
    target = {"modulus_bit_length": 4}
    r = evaluate_non_ecdlp_formula_metrics(algo, target, modulus_bits_override=None, warnings=warnings)
    assert "abstract_logical_qubits_formula" in r.evaluated_skipped
    assert any("not a parameter mapping" in w for w in warnings)


def test_evaluate_warns_when_formula_value_not_string() -> None:
    warnings: list[str] = []
    algo = {"abstract_logical_qubits_formula": {"value": 3.14}}
    target = {"modulus_bit_length": 4}
    r = evaluate_non_ecdlp_formula_metrics(algo, target, modulus_bits_override=None, warnings=warnings)
    assert "abstract_logical_qubits_formula" in r.evaluated_skipped
    assert any("must be a string expression" in w for w in warnings)


def test_exponent_register_asymptotic_skipped_with_warning() -> None:
    warnings: list[str] = []
    algo = {
        "abstract_logical_qubits_formula": {"value": "n", "unit": "c"},
        "abstract_measurement_depth_formula": {"value": "n", "unit": "layers"},
        "abstract_toffoli_plus_t_halves_count_formula": {"value": "n", "unit": "count"},
        EXPONENT_REGISTER_SOURCE_KEY: {"value": "O(n)", "unit": "str"},
    }
    target = {"modulus_bit_length": 5}
    r = evaluate_non_ecdlp_formula_metrics(algo, target, modulus_bits_override=None, warnings=warnings)
    assert EXPONENT_REGISTER_SOURCE_KEY in r.evaluated_skipped
    assert EXPONENT_REGISTER_EVALUATED_KEY not in r.evaluated
    assert any(EXPONENT_REGISTER_SOURCE_KEY in w for w in warnings)


def test_exponent_register_closed_form_evaluates() -> None:
    warnings: list[str] = []
    algo = {
        "abstract_logical_qubits_formula": {"value": "n", "unit": "c"},
        "abstract_measurement_depth_formula": {"value": "n", "unit": "layers"},
        "abstract_toffoli_plus_t_halves_count_formula": {"value": "n", "unit": "count"},
        EXPONENT_REGISTER_SOURCE_KEY: {"value": "1.5 * n", "unit": "qubits"},
    }
    target = {"modulus_bit_length": 10}
    r = evaluate_non_ecdlp_formula_metrics(algo, target, modulus_bits_override=None, warnings=warnings)
    assert EXPONENT_REGISTER_SOURCE_KEY not in r.evaluated_skipped
    assert r.evaluated[EXPONENT_REGISTER_EVALUATED_KEY]["value"] == pytest.approx(15.0)
    assert r.evaluated[EXPONENT_REGISTER_EVALUATED_KEY]["source_parameter"] == EXPONENT_REGISTER_SOURCE_KEY


def test_exponent_register_not_mapping_warns() -> None:
    warnings: list[str] = []
    algo = {
        "abstract_logical_qubits_formula": {"value": "n", "unit": "c"},
        "abstract_measurement_depth_formula": {"value": "n", "unit": "layers"},
        "abstract_toffoli_plus_t_halves_count_formula": {"value": "n", "unit": "count"},
        EXPONENT_REGISTER_SOURCE_KEY: "not_a_dict",
    }
    target = {"modulus_bit_length": 3}
    r = evaluate_non_ecdlp_formula_metrics(algo, target, modulus_bits_override=None, warnings=warnings)
    assert EXPONENT_REGISTER_SOURCE_KEY in r.evaluated_skipped
    assert any("not a parameter mapping" in w and EXPONENT_REGISTER_SOURCE_KEY in w for w in warnings)


def test_exponent_register_eval_failure_warns() -> None:
    warnings: list[str] = []
    algo = {
        "abstract_logical_qubits_formula": {"value": "n", "unit": "c"},
        "abstract_measurement_depth_formula": {"value": "n", "unit": "layers"},
        "abstract_toffoli_plus_t_halves_count_formula": {"value": "n", "unit": "count"},
        EXPONENT_REGISTER_SOURCE_KEY: {"value": "bad_name + n", "unit": "x"},
    }
    target = {"modulus_bit_length": 4}
    r = evaluate_non_ecdlp_formula_metrics(algo, target, modulus_bits_override=None, warnings=warnings)
    assert EXPONENT_REGISTER_SOURCE_KEY in r.evaluated_skipped
    assert any("Could not evaluate" in w and EXPONENT_REGISTER_SOURCE_KEY in w for w in warnings)


def test_formula_metrics_tuple_three_entries() -> None:
    assert len(FORMULA_METRICS) == 3
    assert len(FORMULA_METRIC_SOURCE_KEYS) == 3
