"""Tests for square.yaml_numeric helpers."""

from __future__ import annotations

from square.yaml_numeric import (
    read_evaluated_metric_float,
    read_modality_characteristic_gate_error,
    read_parameter_entry_float,
    read_parameter_entry_float_default,
    read_positive_parameter_microseconds,
    read_scalar_float,
)


def test_read_parameter_entry_float_warns_on_bad_value() -> None:
    warnings: list[str] = []
    doc = {"x": {"value": "not-a-float", "unit": "1"}}
    assert read_parameter_entry_float(doc, "x", warnings, context="test") is None
    assert any("non-numeric" in w for w in warnings)


def test_read_modality_characteristic_gate_error_warns_negative() -> None:
    warnings: list[str] = []
    modality = {"characteristic_physical_gate_error_rate": {"value": -0.1, "unit": "x"}}
    assert read_modality_characteristic_gate_error(modality, warnings) is None
    assert any("negative" in w for w in warnings)


def test_read_scalar_float_warns_on_bad_scalar() -> None:
    warnings: list[str] = []
    assert read_scalar_float("nope", warnings, context="t2") is None
    assert any("numeric" in w for w in warnings)


def test_read_evaluated_metric_float_warns_on_bad_value() -> None:
    warnings: list[str] = []
    ev = {"abstract_logical_qubits": {"value": "x"}}
    assert read_evaluated_metric_float(ev, "abstract_logical_qubits", warnings, context="t") is None
    assert any("non-numeric" in w for w in warnings)


def test_read_parameter_entry_float_default_warns_and_falls_back() -> None:
    warnings: list[str] = []
    v = read_parameter_entry_float_default(
        {"value": "bad", "unit": "1"},
        0.01,
        warnings,
        context="qec",
        param_name="p_th",
    )
    assert v == 0.01
    assert any("p_th" in w and "default" in w for w in warnings)


def test_read_positive_parameter_microseconds_warns_non_positive() -> None:
    warnings: list[str] = []
    doc = {"surface_code_cycle_time": {"value": 0.0, "unit": "us"}}
    assert read_positive_parameter_microseconds(doc, "surface_code_cycle_time", warnings, context="m") is None
    assert any("> 0" in w for w in warnings)
