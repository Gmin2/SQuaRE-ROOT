"""Non-ECDLP algorithm formula evaluation for ``algorithm_metrics.evaluated``."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from square.formula_eval import FormulaEvalError, eval_numeric_formula

FORMULA_METRICS: tuple[tuple[str, str], ...] = (
    ("abstract_logical_qubits_formula", "abstract_logical_qubits"),
    ("abstract_measurement_depth_formula", "abstract_measurement_depth_layers"),
    ("abstract_toffoli_plus_t_halves_count_formula", "abstract_toffoli_plus_t_halves_count"),
)


@dataclass(frozen=True)
class NonEcdlpFormulaMetricsResult:
    """Outputs of :func:`evaluate_non_ecdlp_formula_metrics` (mutates ``warnings`` in place)."""

    evaluated: dict[str, Any]
    evaluated_skipped: list[str]
    n: int | None


def evaluate_non_ecdlp_formula_metrics(
    algo: Mapping[str, Any],
    target: Mapping[str, Any],
    *,
    modulus_bits_override: int | None,
    warnings: list[str],
) -> NonEcdlpFormulaMetricsResult:
    """
    Resolve ``n`` from override or ``target``, evaluate YAML formulas into ``evaluated``.

    Skips asymptotic ``O(...)`` entries and records ``exponent_register_qubits_ne_asymptotic`` when marked O(...).
    """
    evaluated: dict[str, Any] = {}
    evaluated_skipped: list[str] = []
    n_raw = modulus_bits_override if modulus_bits_override is not None else target.get("modulus_bit_length")
    n: int | None = None
    if n_raw is None:
        warnings.append("No modulus_bit_length in scenario target (and no override); formula metrics skipped.")
    else:
        try:
            n = int(n_raw)
        except (TypeError, ValueError):
            n = None
            warnings.append("modulus_bit_length is not an integer; formula metrics skipped.")
        if n is not None and n <= 0:
            n = None
            warnings.append("modulus_bit_length must be positive; formula metrics skipped.")

    if n is not None:
        for src_key, out_key in FORMULA_METRICS:
            entry = algo.get(src_key)
            if not isinstance(entry, dict):
                evaluated_skipped.append(src_key)
                continue
            raw = entry.get("value")
            if not isinstance(raw, str):
                evaluated_skipped.append(src_key)
                continue
            if "O(" in raw or "O(1)" in raw:
                evaluated_skipped.append(src_key)
                continue
            try:
                value = eval_numeric_formula(raw, float(n))
            except (FormulaEvalError, ZeroDivisionError, OverflowError) as exc:
                warnings.append(f"Could not evaluate {src_key!r}: {exc}")
                evaluated_skipped.append(src_key)
                continue
            evaluated[out_key] = {
                "value": value,
                "source_parameter": src_key,
                "provenance": "computed_from_yaml_formula",
            }

    exp = algo.get("exponent_register_qubits_ne_asymptotic")
    if isinstance(exp, dict) and isinstance(exp.get("value"), str) and "O(" in str(exp["value"]):
        evaluated_skipped.append("exponent_register_qubits_ne_asymptotic")

    return NonEcdlpFormulaMetricsResult(
        evaluated=evaluated,
        evaluated_skipped=evaluated_skipped,
        n=n,
    )
