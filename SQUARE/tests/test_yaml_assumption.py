"""Tests for ``square.yaml_assumption``."""

from __future__ import annotations

from square.yaml_assumption import is_parameter_entry


def test_is_parameter_entry_shape() -> None:
    assert is_parameter_entry({"value": 1.0, "unit": "x"})
    assert not is_parameter_entry({"value": 1.0})
    assert not is_parameter_entry({})
