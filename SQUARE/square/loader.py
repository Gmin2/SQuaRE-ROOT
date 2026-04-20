"""
Load a scenario YAML and resolve referenced assumption + algorithm documents.

Paths in scenario files are relative to the SQuaRE project root (directory containing
``Assumptions/Schemas.yaml``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_SCHEMA_MARKER = Path("Assumptions") / "Schemas.yaml"


@dataclass(frozen=True)
class ScenarioBundle:
    """Namespaced payloads so overlapping keys (e.g. document_id) do not collide."""

    scenario: Mapping[str, Any]
    modality: Mapping[str, Any]
    qec: Mapping[str, Any]
    magic: Mapping[str, Any]
    algorithm: Mapping[str, Any]
    magic_aux: Mapping[str, Any] | None = None
    qcvv: Mapping[str, Any] | None = None
    qem: Mapping[str, Any] | None = None


def find_square_root(start: Path | None = None) -> Path:
    """
    Walk parents from ``start`` (or this file's location) until ``Assumptions/Schemas.yaml`` exists.

    :param start: File or directory to begin the search; defaults to ``loader.py``'s parent chain.
    :returns: Directory that is the SQuaRE root (contains ``Assumptions/Schemas.yaml``).
    :raises FileNotFoundError: if no root is found.
    """
    if start is None:
        here = Path(__file__).resolve()
        candidates = [here.parent.parent, *here.parent.parent.parents]
    else:
        p = start.resolve()
        candidates = [p, *p.parents] if p.is_dir() else [p.parent, *p.parents]

    for parent in candidates:
        if (parent / _SCHEMA_MARKER).is_file():
            return parent

    raise FileNotFoundError(
        "Could not locate SQuaRE root (no Assumptions/Schemas.yaml in parents). "
        f"Searched from {start or Path(__file__)}"
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        raise ValueError(f"YAML root is null or empty (no document mapping): {path}")
    if not isinstance(data, dict):
        raise TypeError(f"Expected mapping at root of {path}, got {type(data).__name__}")
    return data


def load_scenario_bundle(
    scenario_path: str | Path,
    *,
    root: Path | None = None,
) -> ScenarioBundle:
    """
    Parse ``scenario_path``, load each file listed under ``paths``, return a :class:`ScenarioBundle`.

    Required keys under ``paths``: ``modality``, ``qec_code``, ``magic``, ``algorithm``.
    Optional: ``magic_aux``, ``qcvv``, ``qem`` (separate assumption documents under
    ``Assumptions/QCVV/`` and ``Assumptions/QEM/``).

    :param scenario_path: YAML file under ``Configs/`` (or any path).
    :param root: SQuaRE root; if omitted, inferred via :func:`find_square_root` from ``scenario_path``.
    """
    scenario_file = Path(scenario_path).resolve()
    base = root if root is not None else find_square_root(scenario_file)
    scenario = _load_yaml(scenario_file)

    paths = scenario.get("paths")
    if not isinstance(paths, dict):
        raise KeyError("Scenario file must contain a mapping 'paths' with file references.")

    required = ("modality", "qec_code", "magic", "algorithm")
    for key in required:
        if key not in paths or not paths[key]:
            raise KeyError(f"paths.{key} is required and must be non-empty")

    def _resolve(rel: str) -> Path:
        if not isinstance(rel, str) or not rel.strip():
            raise ValueError(f"Invalid path reference: {rel!r}")
        candidate = (base / rel).resolve()
        base_resolved = base.resolve()
        try:
            candidate.relative_to(base_resolved)
        except ValueError as exc:
            raise ValueError(f"Path escapes SQuaRE root: {rel!r}") from exc
        if not candidate.is_file():
            raise FileNotFoundError(f"Referenced file does not exist: {candidate}")
        return candidate

    modality = _load_yaml(_resolve(str(paths["modality"])))
    qec = _load_yaml(_resolve(str(paths["qec_code"])))
    magic = _load_yaml(_resolve(str(paths["magic"])))
    algorithm = _load_yaml(_resolve(str(paths["algorithm"])))

    magic_aux: dict[str, Any] | None = None
    aux = paths.get("magic_aux")
    if aux is not None and str(aux).strip():
        magic_aux = _load_yaml(_resolve(str(aux)))

    qcvv_doc: dict[str, Any] | None = None
    qcvv_path = paths.get("qcvv")
    if qcvv_path is not None and str(qcvv_path).strip():
        qcvv_doc = _load_yaml(_resolve(str(qcvv_path)))

    qem_doc: dict[str, Any] | None = None
    qem_path = paths.get("qem")
    if qem_path is not None and str(qem_path).strip():
        qem_doc = _load_yaml(_resolve(str(qem_path)))

    return ScenarioBundle(
        scenario=scenario,
        modality=modality,
        qec=qec,
        magic=magic,
        algorithm=algorithm,
        magic_aux=magic_aux,
        qcvv=qcvv_doc,
        qem=qem_doc,
    )
