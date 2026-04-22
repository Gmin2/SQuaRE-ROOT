"""
Evaluate optional ``paths.magic_aux`` documents for dashboard fields (T-factory branch hints).

Keeps string key access localized and encodes applicability so RSA-only G&E caption metadata
is not silently treated as meaningful for ECDLP targets.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from square.yaml_assumption import is_parameter_entry

# YAML key on magic_aux documents: scenario ``target.problem`` must match one entry for transition logic.
APPLIES_WHEN_TARGET_PROBLEM_IN_KEY = "applies_when_target_problem_in"

# Dashboard keys merged from :func:`evaluate_magic_aux_t_factory_dashboard` (no ``magic_aux`` document).
DEFAULT_MAGIC_AUX_T_FACTORY_DASHBOARD: dict[str, Any] = {
    "t_factory_fallback_recommended": False,
    "t_factory_transition_modulus_bits_order_of_magnitude": None,
    "t_factory_magic_aux_applicable_to_target": None,
    "t_factory_transition_scale_confidence": None,
    "t_factory_fallback_non_clifford_mechanism": None,
    "t_factory_branch_yaml_enabled": None,
}


def _read_str_list_parameter(entry: Any, *, warnings: list[str], context: str) -> list[str] | None:
    if not is_parameter_entry(entry):
        return None
    raw = entry.get("value")
    if raw is None:
        return None
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return parts or None
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        out: list[str] = []
        for x in raw:
            if x is None:
                continue
            s = str(x).strip()
            if s:
                out.append(s)
        return out or None
    warnings.append(f"{context}: applies_when_target_problem_in.value must be a string list; ignoring.")
    return None


def _read_bool_parameter(entry: Any, *, default: bool, warnings: list[str], context: str) -> bool:
    if not is_parameter_entry(entry):
        return default
    v = entry.get("value")
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(int(v))
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("true", "1", "yes", "on"):
            return True
        if s in ("false", "0", "no", "off"):
            return False
    warnings.append(f"{context}: expected boolean for t_factory_used_beyond_ccz_error_budget; using default.")
    return default


def _read_str_parameter(entry: Any, *, warnings: list[str], context: str) -> str | None:
    if not is_parameter_entry(entry):
        return None
    v = entry.get("value")
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _read_transition_bits(entry: Any, *, warnings: list[str], context: str) -> tuple[int | None, str | None]:
    """Return ``(transition_bits, confidence)`` from a ``parameter_entry``."""
    if not is_parameter_entry(entry):
        return None, None
    raw = entry.get("value")
    try:
        bits = int(raw) if raw is not None else None
    except (TypeError, ValueError):
        warnings.append(f"{context}: modulus_bit_length_ccz_to_t_transition_order_of_magnitude not integral; omitted.")
        return None, None
    conf = entry.get("confidence")
    conf_s = str(conf).strip() if conf is not None else None
    return bits, conf_s


def evaluate_magic_aux_t_factory_dashboard(
    magic_aux: Mapping[str, Any] | None,
    *,
    target: Mapping[str, Any],
    n: int | None,
    warnings: list[str],
) -> dict[str, Any]:
    """
    Derive T-factory / CCZ-transition dashboard inputs from ``magic_aux`` when present.

    :returns: Flat dict of dashboard keys (may include ``null`` values). Always includes
        ``t_factory_magic_aux_applicable_to_target`` when ``magic_aux`` is non-``None`` (else all values ``None``).
    """
    if magic_aux is None:
        return dict(DEFAULT_MAGIC_AUX_T_FACTORY_DASHBOARD)

    doc_id = magic_aux.get("document_id")
    doc_label = str(doc_id).strip() if doc_id is not None and str(doc_id).strip() else "magic_aux"

    applies_entry = magic_aux.get(APPLIES_WHEN_TARGET_PROBLEM_IN_KEY)
    allowed_problems = _read_str_list_parameter(applies_entry, warnings=warnings, context=f"{doc_label}.magic_aux")
    if allowed_problems is None:
        allowed_problems = ["rsa_integer_factoring"]

    problem_raw = target.get("problem")
    problem = str(problem_raw).strip() if problem_raw is not None else ""
    applicable = problem in allowed_problems
    if not applicable:
        warnings.append(
            f"{doc_label}: magic_aux T-factory transition metadata applies only when "
            f"target.problem is one of {allowed_problems!r}; this scenario has problem={problem!r}. "
            "Transition scale is not used for t_factory_fallback_recommended (RSA Figure 1 caption context)."
        )

    branch_enabled = _read_bool_parameter(
        magic_aux.get("t_factory_used_beyond_ccz_error_budget"),
        default=True,
        warnings=warnings,
        context=doc_label,
    )
    mechanism = _read_str_parameter(
        magic_aux.get("fallback_non_clifford_mechanism"),
        warnings=warnings,
        context=doc_label,
    )

    trans_entry = magic_aux.get("modulus_bit_length_ccz_to_t_transition_order_of_magnitude")
    t_transition, trans_confidence = _read_transition_bits(trans_entry, warnings=warnings, context=doc_label)
    if applicable and trans_confidence and trans_confidence != "proven":
        warnings.append(
            f"{doc_label}: CCZ→T transition scale is confidence={trans_confidence!r} (caption-derived); "
            "treat threshold as approximate, not a sharp constant."
        )

    t_fallback = False
    if applicable and branch_enabled and n is not None and t_transition is not None and n >= t_transition:
        t_fallback = True
        mech = mechanism or "unknown"
        warnings.append(
            f"n={n} is at or above the documented CCZ→T factory transition scale (~{t_transition} bits); "
            f"magic_aux ({doc_label}) flags a different non-Clifford supply model ({mech})."
        )
    elif not branch_enabled and applicable and n is not None and t_transition is not None and n >= t_transition:
        warnings.append(
            f"{doc_label}: n={n} meets CCZ→T transition scale (~{t_transition}) but "
            "t_factory_used_beyond_ccz_error_budget is false; not setting t_factory_fallback_recommended."
        )

    return {
        "t_factory_fallback_recommended": t_fallback,
        "t_factory_transition_modulus_bits_order_of_magnitude": t_transition if applicable else None,
        "t_factory_magic_aux_applicable_to_target": applicable,
        "t_factory_transition_scale_confidence": trans_confidence if applicable else None,
        "t_factory_fallback_non_clifford_mechanism": mechanism if applicable else None,
        "t_factory_branch_yaml_enabled": branch_enabled,
    }
