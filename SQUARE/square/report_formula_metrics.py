"""Non-ECDLP algorithm formula evaluation for ``algorithm_metrics.evaluated``.

The tuple :data:`FORMULA_METRICS` lists algorithm YAML ``parameter_entry`` keys whose string
``value`` is a closed-form expression in ``n`` (modulus bit length), evaluated by
:func:`square.formula_eval.eval_numeric_formula`. Keys are:

- ``abstract_logical_qubits_formula`` → ``abstract_logical_qubits``
- ``abstract_measurement_depth_formula`` → ``abstract_measurement_depth_layers``
- ``abstract_toffoli_plus_t_halves_count_formula`` → ``abstract_toffoli_plus_t_halves_count``

``exponent_register_qubits_ne_asymptotic``: if ``value`` is a string containing ASCII ``O(``,
it is treated as asymptotic documentation only (skipped). Otherwise it is evaluated like the
other formulas and stored under ``exponent_register_qubits_ne`` in ``evaluated``.

False-positive risk: any literal ``O(`` substring is treated as asymptotic; keep ``value``
strings in paper-notation style (see algorithm YAML authoring).
"""

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

FORMULA_METRIC_SOURCE_KEYS: tuple[str, ...] = tuple(src for src, _ in FORMULA_METRICS)

EXPONENT_REGISTER_SOURCE_KEY = "exponent_register_qubits_ne_asymptotic"
EXPONENT_REGISTER_EVALUATED_KEY = "exponent_register_qubits_ne"


def ecdlp_evaluated_skipped_formula_keys() -> tuple[str, ...]:
    """Source keys listed under ``evaluated_skipped`` in ECDLP mode (not envelope-derived)."""
    return FORMULA_METRIC_SOURCE_KEYS + (EXPONENT_REGISTER_SOURCE_KEY,)


def is_asymptotic_formula_string(s: str) -> bool:
    """
    Return True if the algorithm YAML formula string should be skipped for numeric evaluation.

    Contract: a literal ASCII substring ``O(`` (capital O + open parenthesis) denotes an
    asymptotic expression from the literature, not a closed-form in ``n`` for this evaluator.
    """
    return "O(" in s


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

    ``modulus_bits_override`` wins when set. Booleans are rejected for ``n``. Skips asymptotic
    entries (see :func:`is_asymptotic_formula_string`). Closed-form ``exponent_register_qubits_ne_asymptotic``
    values are evaluated into ``exponent_register_qubits_ne`` when ``n`` is available.
    """
    evaluated: dict[str, Any] = {}
    evaluated_skipped: list[str] = []
    n_raw = modulus_bits_override if modulus_bits_override is not None else target.get("modulus_bit_length")
    n: int | None = None
    if n_raw is None:
        warnings.append("No modulus_bit_length in scenario target (and no override); formula metrics skipped.")
    elif isinstance(n_raw, bool):
        warnings.append("modulus_bit_length must be an integer, not a boolean; formula metrics skipped.")
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
                warnings.append(
                    f"Algorithm YAML {src_key!r} is missing or not a parameter mapping; formula metric skipped."
                )
                continue
            raw = entry.get("value")
            if not isinstance(raw, str):
                evaluated_skipped.append(src_key)
                warnings.append(
                    f"Algorithm YAML {src_key!r} value must be a string expression in n for numeric evaluation; skipped."
                )
                continue
            if is_asymptotic_formula_string(raw):
                evaluated_skipped.append(src_key)
                warnings.append(
                    f"{src_key!r}: formula string contains asymptotic marker 'O('; not evaluated numerically."
                )
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

        exp = algo.get(EXPONENT_REGISTER_SOURCE_KEY)
        if exp is not None:
            if not isinstance(exp, dict):
                evaluated_skipped.append(EXPONENT_REGISTER_SOURCE_KEY)
                warnings.append(
                    f"Algorithm YAML {EXPONENT_REGISTER_SOURCE_KEY!r} is not a parameter mapping; skipped."
                )
            else:
                raw = exp.get("value")
                if not isinstance(raw, str):
                    evaluated_skipped.append(EXPONENT_REGISTER_SOURCE_KEY)
                    warnings.append(
                        f"Algorithm YAML {EXPONENT_REGISTER_SOURCE_KEY!r} value must be a string for evaluation; skipped."
                    )
                elif is_asymptotic_formula_string(raw):
                    evaluated_skipped.append(EXPONENT_REGISTER_SOURCE_KEY)
                    warnings.append(
                        f"{EXPONENT_REGISTER_SOURCE_KEY!r}: formula string contains asymptotic marker 'O('; "
                        "not evaluated numerically."
                    )
                else:
                    try:
                        value = eval_numeric_formula(raw, float(n))
                    except (FormulaEvalError, ZeroDivisionError, OverflowError) as exc:
                        warnings.append(f"Could not evaluate {EXPONENT_REGISTER_SOURCE_KEY!r}: {exc}")
                        evaluated_skipped.append(EXPONENT_REGISTER_SOURCE_KEY)
                    else:
                        evaluated[EXPONENT_REGISTER_EVALUATED_KEY] = {
                            "value": value,
                            "source_parameter": EXPONENT_REGISTER_SOURCE_KEY,
                            "provenance": "computed_from_yaml_formula",
                        }

    return NonEcdlpFormulaMetricsResult(
        evaluated=evaluated,
        evaluated_skipped=evaluated_skipped,
        n=n,
    )
