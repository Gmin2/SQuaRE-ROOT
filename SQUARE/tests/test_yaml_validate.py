"""Tests for ``square.yaml_validate``."""

from __future__ import annotations

import pytest
from square.yaml_validate import validate_assumption_document_header


def test_validate_assumption_document_header_ok() -> None:
    validate_assumption_document_header(
        {
            "document_id": "x",
            "schema_version": 1,
            "primary_reference": "ref",
        },
        source="test",
    )


def test_validate_assumption_document_header_rejects_missing_field() -> None:
    with pytest.raises(ValueError, match="primary_reference"):
        validate_assumption_document_header(
            {"document_id": "x", "schema_version": 1},
            source="test.yaml",
        )
