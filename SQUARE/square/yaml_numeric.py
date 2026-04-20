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
    entry = modality.get("characteristic_physical_gate_error_rate")
    if not isinstance(entry, dict) or entry.get("value") is None:
        return None
    try:
        v = float(entry["value"])
    except (TypeError, ValueError):
        warnings.append(f"{context}: characteristic_physical_gate_error_rate not numeric; omitted.")
        return None
    if v < 0.0:
        warnings.append(f"{context}: characteristic_physical_gate_error_rate negative; omitted.")
        return None
    return v
