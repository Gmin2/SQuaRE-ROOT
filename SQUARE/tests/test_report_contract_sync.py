"""Guardrail: docs/output-contract.md stays aligned with ``_REPORT_CONTRACT_VERSION`` in code."""

from __future__ import annotations

import re

from square.loader import find_square_root


def test_output_contract_doc_matches_report_contract_version_constant() -> None:
    root = find_square_root()
    report_py = (root / "square" / "report.py").read_text(encoding="utf-8")
    m = re.search(r"^_REPORT_CONTRACT_VERSION = (\d+)\s*$", report_py, re.MULTILINE)
    assert m is not None
    v = m.group(1)
    doc = (root / "docs" / "output-contract.md").read_text(encoding="utf-8")
    assert f"(currently `{v}`)" in doc, (
        f"docs/output-contract.md must mention contract version {v} "
        "in the envelope table (see report_contract_version row)."
    )
    assert f"| `{v}` |" in doc, (
        f"docs/output-contract.md contract history table must include a row for version {v}."
    )
