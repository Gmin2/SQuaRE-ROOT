"""Shared predicates for SQuaRE assumption YAML (parameter_entry shape, etc.)."""

from __future__ import annotations

from typing import Any


def is_parameter_entry(obj: Any) -> bool:
    """True when ``obj`` looks like a YAML ``parameter_entry`` (numeric ``value`` + ``unit``)."""
    return isinstance(obj, dict) and "value" in obj and "unit" in obj
