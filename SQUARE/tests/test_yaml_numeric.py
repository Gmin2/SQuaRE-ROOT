"""Tests for square.yaml_numeric helpers."""

from __future__ import annotations

from square.yaml_numeric import (
    read_modality_characteristic_gate_error,
    read_parameter_entry_float,
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
