"""Unit tests for ``square.report_magic_aux`` (T-factory / magic_aux dashboard hints)."""

from __future__ import annotations

import pytest
from square.report_magic_aux import (
    DEFAULT_MAGIC_AUX_T_FACTORY_DASHBOARD,
    evaluate_magic_aux_t_factory_dashboard,
)


def test_evaluate_magic_aux_none_returns_defaults() -> None:
    w: list[str] = []
    out = evaluate_magic_aux_t_factory_dashboard(None, target={}, n=2048, warnings=w)
    assert out == DEFAULT_MAGIC_AUX_T_FACTORY_DASHBOARD
    assert w == []


def test_evaluate_magic_aux_rsa_below_transition_no_fallback() -> None:
    w: list[str] = []
    magic_aux = {
        "document_id": "t_factory_fallback_gidney_ekera_2021",
        "modulus_bit_length_ccz_to_t_transition_order_of_magnitude": {
            "value": 32786,
            "unit": "bits",
            "confidence": "estimated",
        },
        "t_factory_used_beyond_ccz_error_budget": {"value": True, "unit": "boolean"},
        "fallback_non_clifford_mechanism": {
            "value": "t_distillation_fowler_et_al_style",
            "unit": "descriptor",
        },
    }
    out = evaluate_magic_aux_t_factory_dashboard(
        magic_aux,
        target={"problem": "rsa_integer_factoring"},
        n=2048,
        warnings=w,
    )
    assert out["t_factory_fallback_recommended"] is False
    assert out["t_factory_magic_aux_applicable_to_target"] is True
    assert out["t_factory_transition_modulus_bits_order_of_magnitude"] == 32786
    assert out["t_factory_branch_yaml_enabled"] is True
    assert out["t_factory_fallback_non_clifford_mechanism"] == "t_distillation_fowler_et_al_style"
    assert any("CCZ→T transition scale is confidence" in x for x in w)
    assert not any("different non-Clifford supply model" in x for x in w)


def test_evaluate_magic_aux_rsa_at_transition_recommends_fallback() -> None:
    w: list[str] = []
    magic_aux = {
        "document_id": "t_factory_fallback_gidney_ekera_2021",
        "modulus_bit_length_ccz_to_t_transition_order_of_magnitude": {
            "value": 1000,
            "unit": "bits",
            "confidence": "proven",
        },
        "t_factory_used_beyond_ccz_error_budget": {"value": True, "unit": "boolean"},
        "fallback_non_clifford_mechanism": {
            "value": "t_distillation_fowler_et_al_style",
            "unit": "descriptor",
        },
    }
    out = evaluate_magic_aux_t_factory_dashboard(
        magic_aux,
        target={"problem": "rsa_integer_factoring"},
        n=1000,
        warnings=w,
    )
    assert out["t_factory_fallback_recommended"] is True
    assert any("different non-Clifford supply model" in x for x in w)
    assert not any("CCZ→T transition scale is confidence" in x for x in w)


def test_evaluate_magic_aux_ecdlp_not_applicable() -> None:
    w: list[str] = []
    magic_aux = {
        "document_id": "t_factory_fallback_gidney_ekera_2021",
        "modulus_bit_length_ccz_to_t_transition_order_of_magnitude": {
            "value": 32786,
            "unit": "bits",
            "confidence": "estimated",
        },
        "fallback_non_clifford_mechanism": {
            "value": "t_distillation_fowler_et_al_style",
            "unit": "descriptor",
        },
    }
    out = evaluate_magic_aux_t_factory_dashboard(
        magic_aux,
        target={"problem": "ecdlp_secp256k1_256_bit"},
        n=None,
        warnings=w,
    )
    assert out["t_factory_magic_aux_applicable_to_target"] is False
    assert out["t_factory_transition_modulus_bits_order_of_magnitude"] is None
    assert out["t_factory_fallback_recommended"] is False
    assert out["t_factory_fallback_non_clifford_mechanism"] is None
    assert any("applies only when" in x for x in w)


def test_evaluate_magic_aux_branch_disabled_warns_without_fallback() -> None:
    w: list[str] = []
    magic_aux = {
        "document_id": "t_aux",
        "modulus_bit_length_ccz_to_t_transition_order_of_magnitude": {
            "value": 100,
            "unit": "bits",
            "confidence": "proven",
        },
        "t_factory_used_beyond_ccz_error_budget": {"value": False, "unit": "boolean"},
    }
    out = evaluate_magic_aux_t_factory_dashboard(
        magic_aux,
        target={"problem": "rsa_integer_factoring"},
        n=500,
        warnings=w,
    )
    assert out["t_factory_fallback_recommended"] is False
    assert out["t_factory_branch_yaml_enabled"] is False
    assert any("t_factory_used_beyond_ccz_error_budget is false" in x for x in w)


@pytest.mark.parametrize(
    ("raw", "problem", "expect_applicable"),
    [
        ("rsa_integer_factoring,ecdlp_x", "ecdlp_x", True),
        (["rsa_integer_factoring"], "ecdlp_x", False),
    ],
)
def test_evaluate_magic_aux_applies_when_custom_list(
    raw: str | list[str],
    problem: str,
    expect_applicable: bool,
) -> None:
    w: list[str] = []
    magic_aux = {
        "document_id": "t_aux",
        "applies_when_target_problem_in": {"value": raw, "unit": "list"},
        "modulus_bit_length_ccz_to_t_transition_order_of_magnitude": {
            "value": 10,
            "unit": "bits",
            "confidence": "proven",
        },
        "t_factory_used_beyond_ccz_error_budget": {"value": True, "unit": "boolean"},
    }
    out = evaluate_magic_aux_t_factory_dashboard(
        magic_aux,
        target={"problem": problem},
        n=20,
        warnings=w,
    )
    assert out["t_factory_magic_aux_applicable_to_target"] is expect_applicable
    assert out["t_factory_fallback_recommended"] is expect_applicable
