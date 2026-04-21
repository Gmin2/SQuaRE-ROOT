"""OSRE extended physical layer parity: every modality YAML defines the canonical keys.

Step 1 of the physical-layer expansion plan: all profiles under ``Assumptions/Modalities/``
must include the same eight ``parameter_entry`` rows documented in
``docs/output-contract.md`` § ``physical_layer`` so ``square-report`` can emit a full
``physical_layer`` passthrough and cross-modality comparisons stay symmetric.
"""

from __future__ import annotations

from pathlib import Path

from square.loader import _load_yaml, find_square_root
from square.report import OSRE_EXTENDED_PHYSICAL_PARAMETER_KEYS
from square.yaml_assumption import is_parameter_entry


def _modality_yaml_paths(root: Path) -> list[Path]:
    modalities_dir = root / "Assumptions" / "Modalities"
    return sorted(p for p in modalities_dir.glob("*.yaml") if p.is_file())


def test_every_modality_yaml_includes_osre_extended_physical_keys() -> None:
    root = find_square_root()
    paths = _modality_yaml_paths(root)
    assert paths, "expected at least one Assumptions/Modalities/*.yaml"
    for path in paths:
        doc = _load_yaml(path)
        missing = sorted(k for k in OSRE_EXTENDED_PHYSICAL_PARAMETER_KEYS if k not in doc)
        assert not missing, (
            f"{path.relative_to(root)}: missing OSRE extended physical keys " f"(see docs/output-contract.md § physical_layer): {missing}"
        )
        for key in OSRE_EXTENDED_PHYSICAL_PARAMETER_KEYS:
            entry = doc[key]
            assert is_parameter_entry(
                entry
            ), f"{path.name}:{key}: expected parameter_entry with value and unit"
            for field in ("confidence", "source", "date"):
                assert field in entry and entry[field] is not None, (
                    f"{path.name}:{key}: parameter_entry must include non-null {field!r} per Schemas.yaml"
                )
