"""Nominal gate-error proxy for heuristic ``p_effective`` (max 1Q/2Q / fallbacks)."""

from __future__ import annotations

import pytest
from square.report import _effective_physical_gate_error_stack
from square.yaml_numeric import read_modality_nominal_gate_error_for_heuristic


def _mod(
    *,
    ch: float,
    sq: float | None = None,
    tq: float | None = None,
) -> dict:
    m: dict = {
        "document_id": "_test_mod",
        "schema_version": 1,
        "primary_reference": "unit test",
        "characteristic_physical_gate_error_rate": {"value": ch, "unit": "error_probability_per_gate"},
    }
    if sq is not None:
        m["single_qubit_gate_error_rate"] = {"value": sq, "unit": "error_probability_per_gate"}
    if tq is not None:
        m["two_qubit_gate_error_rate"] = {"value": tq, "unit": "error_probability_per_gate"}
    return m


def test_read_modality_nominal_max_1q_2q() -> None:
    w: list[str] = []
    p, method, ch = read_modality_nominal_gate_error_for_heuristic(_mod(ch=0.001, sq=0.002, tq=0.0015), w)
    assert p == pytest.approx(0.002)
    assert method == "max_1q_2q"
    assert ch == pytest.approx(0.001)
    assert not w


def test_read_modality_nominal_single_only_warns() -> None:
    w: list[str] = []
    p, method, ch = read_modality_nominal_gate_error_for_heuristic(_mod(ch=0.001, sq=0.0003), w)
    assert p == pytest.approx(0.0003)
    assert method == "single_1q_only"
    assert ch == pytest.approx(0.001)
    assert any("two_qubit_gate_error_rate absent or unusable" in x for x in w)


def test_read_modality_nominal_fallback_characteristic_warns() -> None:
    w: list[str] = []
    p, method, ch = read_modality_nominal_gate_error_for_heuristic(_mod(ch=0.004), w)
    assert p == pytest.approx(0.004)
    assert method == "characteristic_fallback"
    assert ch == pytest.approx(0.004)
    assert any("characteristic_physical_gate_error_rate" in x and "absent or unusable" in x for x in w)


def test_effective_physical_gate_error_stack_matches_legacy_when_max_equals_char() -> None:
    """When max(1Q,2Q) equals characteristic, ``p_effective`` matches legacy characteristic × σ × penalty."""
    modality = _mod(ch=0.001, sq=0.0006, tq=0.001)
    w: list[str] = []
    stack = _effective_physical_gate_error_stack(
        modality=modality,
        qcvv_doc=None,
        qec={},
        rsa_phys_millions=None,
        evaluated={},
        warnings=w,
    )
    assert stack["p_nominal_gate_proxy_method"] == "max_1q_2q"
    assert stack["p_nominal"] == pytest.approx(0.001)
    assert stack["characteristic_physical_gate_error_rate"] == pytest.approx(0.001)
    assert stack["p_effective"] == pytest.approx(0.001)


def test_effective_physical_gate_error_stack_raises_nominal_when_max_exceeds_char() -> None:
    modality = _mod(ch=0.001, sq=0.01, tq=0.002)
    w: list[str] = []
    stack = _effective_physical_gate_error_stack(
        modality=modality,
        qcvv_doc=None,
        qec={},
        rsa_phys_millions=None,
        evaluated={},
        warnings=w,
    )
    assert stack["p_nominal"] == pytest.approx(0.01)
    assert stack["p_nominal_gate_proxy_method"] == "max_1q_2q"
    assert stack["p_effective"] == pytest.approx(0.01)


def test_read_modality_nominal_two_only_warns() -> None:
    w: list[str] = []
    p, method, ch = read_modality_nominal_gate_error_for_heuristic(_mod(ch=0.001, tq=0.004), w)
    assert p == pytest.approx(0.004)
    assert method == "two_2q_only"
    assert ch == pytest.approx(0.001)
    assert any("single_qubit_gate_error_rate absent or unusable" in x for x in w)


def test_read_modality_nominal_extreme_characteristic_does_not_move_max_branch() -> None:
    """Heuristic ``p_nominal`` follows max(1Q,2Q); headline characteristic may differ (e.g. MC sweep)."""
    w: list[str] = []
    p, method, ch = read_modality_nominal_gate_error_for_heuristic(_mod(ch=0.99, sq=0.0006, tq=0.001), w)
    assert p == pytest.approx(0.001)
    assert method == "max_1q_2q"
    assert ch == pytest.approx(0.99)
    assert not w
