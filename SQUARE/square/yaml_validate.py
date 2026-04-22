"""Minimal structural checks for loaded assumption YAML (not full schema validation)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def validate_assumption_document_header(doc: Mapping[str, Any], *, source: str) -> None:
    """
    Require ``document_header`` fields from ``Assumptions/Schemas.yaml``: ``document_id``,
    ``schema_version``, ``primary_reference``.

    :param doc: Root mapping of a modality / QEC / magic / algorithm / QCVV / QEM YAML.
    :param source: Human-readable label (e.g. file path) for error messages.
    :raises ValueError: if a required field is missing or empty.
    """
    for field in ("document_id", "schema_version", "primary_reference"):
        raw = doc.get(field)
        if raw is None:
            raise ValueError(f"{source}: missing required header field {field!r} (Assumptions/Schemas.yaml)")
        if isinstance(raw, str) and not raw.strip():
            raise ValueError(f"{source}: empty required header field {field!r} (Assumptions/Schemas.yaml)")
