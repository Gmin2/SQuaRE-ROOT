"""Evaluate surface-code patch physical-qubits-per-logical from QEC YAML formula."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from square.formula_eval import FormulaEvalError, eval_numeric_formula_with_bindings


def evaluate_patch_physical_per_logical(
    qec: Mapping[str, Any],
    d_resolved: int | None,
    warnings: list[str],
) -> tuple[str | None, float | None, str, dict[str, Any] | None]:
    """
    Read ``logical_qubit_patch_physical_qubit_count_formula`` and evaluate at distance ``d``.

    :returns: ``(formula, physical_per_logical, status, optional_eval_meta)``.
    """
    patch_entry = qec.get("logical_qubit_patch_physical_qubit_count_formula")
    patch_formula: str | None = None
    if isinstance(patch_entry, dict) and isinstance(patch_entry.get("value"), str):
        patch_formula = str(patch_entry["value"])

    patch_physical_per_logical: float | None = None
    qec_patch_status = "no_formula_in_profile"
    qec_patch_eval_meta: dict[str, Any] | None = None

    if not patch_formula:
        return patch_formula, patch_physical_per_logical, qec_patch_status, qec_patch_eval_meta

    if d_resolved is None:
        qec_patch_status = "pending_distance_d"
        warnings.append(
            "Surface-code patch formula is present but code distance d is not set "
            "(use scenario qec_code_distance, qec.distance_policy heuristic, or --d); "
            "physical qubits per logical are not computed."
        )
    elif int(d_resolved) < 1:
        qec_patch_status = "invalid_distance_d"
        warnings.append(
            f"Surface-code patch formula skipped: code distance d={d_resolved!r} must be >= 1."
        )
    else:
        try:
            patch_physical_per_logical = eval_numeric_formula_with_bindings(
                patch_formula, {"d": float(d_resolved)}
            )
            qec_patch_status = "evaluated"
            qec_patch_eval_meta = {
                "provenance": "computed_from_yaml_formula",
                "source_parameter": "logical_qubit_patch_physical_qubit_count_formula",
            }
        except (FormulaEvalError, ZeroDivisionError, OverflowError) as exc:
            qec_patch_status = "eval_failed"
            warnings.append(f"Could not evaluate QEC patch formula: {exc}")

    return patch_formula, patch_physical_per_logical, qec_patch_status, qec_patch_eval_meta
