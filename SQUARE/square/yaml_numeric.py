"""
Parse ``parameter_entry`` numeric ``value`` fields from loaded assumption YAML with explicit warnings.

Centralizes coercion that previously failed silently (``None`` without explanation).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def read_parameter_entry_float(
    doc: Mapping[str, Any] | None,
    key: str,
    warnings: list[str],
    *,
    context: str,
) -> float | None:
    """
    Return ``float(entry['value'])`` for a top-level ``parameter_entry`` key, or ``None``.

    Emits a **warning** when the key exists but ``value`` is not coercible to float.

    :param doc: Loaded YAML root (modality, QEC, QCVV, QEM, etc.).
    :param key: Parameter name.
    :param warnings: Mutable list to append parse issues.
    :param context: Short label for messages (e.g. ``"paths.qem"``).
    :returns: Parsed float, or ``None`` if absent or unusable.
    """
    if doc is None:
        return None
    entry = doc.get(key)
    if not isinstance(entry, dict) or entry.get("value") is None:
        return None
    try:
        return float(entry["value"])
    except (TypeError, ValueError):
        warnings.append(f"{context}: parameter {key!r} has non-numeric value; treated as absent.")
        return None


def read_modality_characteristic_gate_error(
    modality: Mapping[str, Any],
    warnings: list[str],
    *,
    context: str = "modality",
) -> float | None:
    """
    Modality ``characteristic_physical_gate_error_rate.value`` when present and non-negative.

    Warns on non-numeric or negative values.
    """
    v = read_parameter_entry_float(
        modality, "characteristic_physical_gate_error_rate", warnings, context=context
    )
    if v is None:
        return None
    if v < 0.0:
        warnings.append(f"{context}: characteristic_physical_gate_error_rate negative; omitted.")
        return None
    return v


def read_modality_nonnegative_gate_error_parameter(
    modality: Mapping[str, Any],
    key: str,
    warnings: list[str],
    *,
    context: str,
) -> float | None:
    """
    Read a modality ``parameter_entry`` gate-style error probability (non-negative).

    Returns ``None`` when the key is absent, ``value`` is not numeric, or the value is negative (with a
    warning in the latter two cases).
    """
    v = read_parameter_entry_float(modality, key, warnings, context=context)
    if v is None:
        return None
    if v < 0.0:
        warnings.append(f"{context}: {key!r} is negative; omitted from nominal gate proxy.")
        return None
    return v


def read_modality_nominal_gate_error_for_heuristic(
    modality: Mapping[str, Any],
    warnings: list[str],
    *,
    context: str = "paths.modality",
) -> tuple[float | None, str | None, float | None]:
    """
    Base gate-error probability **p_nominal** fed into ``p_effective = p_nominal × σ_QCVV × (penalty)``.

    **Precedence:** If both ``single_qubit_gate_error_rate`` and ``two_qubit_gate_error_rate`` are present
    and usable (non-negative numeric ``parameter_entry`` values), use ``max(1Q, 2Q)``. If exactly one is
    usable, use that value alone. Otherwise use ``characteristic_physical_gate_error_rate`` when it is
    usable. **Invariants:** ``p_nominal`` is always ``None`` when no usable rate exists; when falling back
    to characteristic because both extended keys are absent or unusable, emit one explicit warning; when
    only one extended key is usable, emit a warning naming the missing/unusable sibling.

    :returns: ``(p_nominal, method_id, characteristic_or_none)`` where ``method_id`` is one of
        ``max_1q_2q``, ``single_1q_only``, ``two_2q_only``, ``characteristic_fallback``, or
        ``(None, None, None)`` if nothing is usable.
    """
    sq = read_modality_nonnegative_gate_error_parameter(
        modality, "single_qubit_gate_error_rate", warnings, context=context
    )
    tq = read_modality_nonnegative_gate_error_parameter(
        modality, "two_qubit_gate_error_rate", warnings, context=context
    )
    ch = read_modality_characteristic_gate_error(modality, warnings, context=context)

    if sq is not None and tq is not None:
        return (max(sq, tq), "max_1q_2q", ch)
    if sq is not None:
        warnings.append(
            f"{context}: effective_physical_gate_error: using single_qubit_gate_error_rate only; "
            "two_qubit_gate_error_rate absent or unusable."
        )
        return (sq, "single_1q_only", ch)
    if tq is not None:
        warnings.append(
            f"{context}: effective_physical_gate_error: using two_qubit_gate_error_rate only; "
            "single_qubit_gate_error_rate absent or unusable."
        )
        return (tq, "two_2q_only", ch)
    if ch is not None:
        warnings.append(
            f"{context}: effective_physical_gate_error: using characteristic_physical_gate_error_rate; "
            "single_qubit_gate_error_rate and two_qubit_gate_error_rate absent or unusable."
        )
        return (ch, "characteristic_fallback", ch)
    return (None, None, None)


def read_scalar_float(
    value: Any,
    warnings: list[str],
    *,
    context: str,
) -> float | None:
    """
    Coerce a YAML scalar (number or string) to ``float`` for non-``parameter_entry`` fields (e.g. Table 2 rows).

    :param value: Raw cell from a mapping (may be ``None``).
    :param warnings: Mutable list to append parse issues.
    :param context: Short label for messages (include row id when applicable).
    :returns: Parsed float, or ``None`` if absent or not coercible.
    """
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        warnings.append(f"{context}: expected numeric scalar; got {type(value).__name__!r}.")
        return None


def read_evaluated_metric_float(
    evaluated: Mapping[str, Any],
    key: str,
    warnings: list[str],
    *,
    context: str,
) -> float | None:
    """
    Read ``float(evaluated[key]['value'])`` when ``evaluated[key]`` is a mapping with ``value``.

    Emits a warning when the entry exists but ``value`` is not coercible to float.
    """
    entry = evaluated.get(key)
    if not isinstance(entry, dict) or entry.get("value") is None:
        return None
    try:
        return float(entry["value"])
    except (TypeError, ValueError):
        warnings.append(f"{context}: evaluated metric {key!r} has non-numeric value.")
        return None


def read_positive_parameter_microseconds(
    container: Mapping[str, Any],
    key: str,
    warnings: list[str],
    *,
    context: str,
) -> float | None:
    """
    ``parameter_entry`` microseconds-style field: present, positive, numeric, or ``None`` with warnings.
    """
    entry = container.get(key)
    if not isinstance(entry, dict) or entry.get("value") is None:
        return None
    try:
        v = float(entry["value"])
    except (TypeError, ValueError):
        warnings.append(f"{context}: {key!r} non-numeric; omitted from logical_cycle_time.")
        return None
    if v <= 0.0:
        warnings.append(f"{context}: {key!r} must be > 0; got {v}; omitted.")
        return None
    return v


def read_parameter_entry_float_default(
    entry: Any,
    default: float,
    warnings: list[str],
    *,
    context: str,
    param_name: str,
) -> float:
    """
    Coerce a single ``parameter_entry`` node to float, or return ``default`` with a warning when invalid.
    """
    if not isinstance(entry, dict) or entry.get("value") is None:
        return default
    try:
        return float(entry["value"])
    except (TypeError, ValueError):
        warnings.append(
            f"{context}: parameter {param_name!r} has non-numeric value; using default {default}."
        )
        return default
