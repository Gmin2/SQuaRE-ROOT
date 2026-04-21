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

from square.yaml_validate import validate_assumption_document_header

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


def resolve_path_under_square_root(root: Path, rel: str) -> Path:
    """
    Resolve ``rel`` to an absolute path that must stay under ``root`` (same containment as scenario ``paths``).

    Relative segments like ``..`` are canonicalized; escaping the root raises :class:`ValueError`.
    If ``rel`` is absolute, it must still resolve under ``root``.
    """
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError(f"Invalid path reference: {rel!r}")
    base = root.resolve()
    raw = Path(rel)
    candidate = (raw if raw.is_absolute() else base / raw).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"Path escapes SQuaRE root: {rel!r}") from exc
    return candidate


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
    require_scenario_under_root: bool = False,
) -> ScenarioBundle:
    """
    Parse ``scenario_path``, load each file listed under ``paths``, return a :class:`ScenarioBundle`.

    Required keys under ``paths``: ``modality``, ``qec_code``, ``magic``, ``algorithm``.
    Optional: ``magic_aux``, ``qcvv``, ``qem`` (separate assumption documents under
    ``Assumptions/QCVV/`` and ``Assumptions/QEM/``).

    :param scenario_path: YAML file under ``Configs/`` (or any path).
    :param root: SQuaRE root; if omitted, inferred via :func:`find_square_root` from ``scenario_path``.
    :param require_scenario_under_root: If True, ``scenario_path`` must resolve under ``root`` (or the
        inferred root). References under ``paths.*`` are always resolved under that root; this option
        additionally constrains where the scenario YAML itself may live.
    """
    scenario_file = Path(scenario_path).resolve()
    base = root if root is not None else find_square_root(scenario_file)
    if require_scenario_under_root:
        base_resolved = base.resolve()
        try:
            scenario_file.relative_to(base_resolved)
        except ValueError as exc:
            raise ValueError(
                f"Scenario file must lie under SQuaRE root ({base_resolved}): {scenario_file}"
            ) from exc
    scenario = _load_yaml(scenario_file)

    paths = scenario.get("paths")
    if not isinstance(paths, dict):
        raise ValueError("Scenario file must contain a mapping 'paths' with file references.")

    required = ("modality", "qec_code", "magic", "algorithm")
    for key in required:
        if key not in paths or not paths[key]:
            raise ValueError(f"paths.{key} is required and must be non-empty")

    def _resolve(rel: str) -> Path:
        candidate = resolve_path_under_square_root(base, rel)
        if not candidate.is_file():
            raise FileNotFoundError(f"Referenced file does not exist: {candidate}")
        return candidate

    modality_path = _resolve(str(paths["modality"]))
    modality = _load_yaml(modality_path)
    validate_assumption_document_header(modality, source=str(modality_path))

    qec_path = _resolve(str(paths["qec_code"]))
    qec = _load_yaml(qec_path)
    validate_assumption_document_header(qec, source=str(qec_path))

    magic_path = _resolve(str(paths["magic"]))
    magic = _load_yaml(magic_path)
    validate_assumption_document_header(magic, source=str(magic_path))

    algo_path = _resolve(str(paths["algorithm"]))
    algorithm = _load_yaml(algo_path)
    validate_assumption_document_header(algorithm, source=str(algo_path))

    magic_aux: dict[str, Any] | None = None
    aux = paths.get("magic_aux")
    if aux is not None and str(aux).strip():
        aux_p = _resolve(str(aux))
        magic_aux = _load_yaml(aux_p)
        validate_assumption_document_header(magic_aux, source=str(aux_p))

    qcvv_doc: dict[str, Any] | None = None
    qcvv_path = paths.get("qcvv")
    if qcvv_path is not None and str(qcvv_path).strip():
        q_p = _resolve(str(qcvv_path))
        qcvv_doc = _load_yaml(q_p)
        validate_assumption_document_header(qcvv_doc, source=str(q_p))

    qem_doc: dict[str, Any] | None = None
    qem_path = paths.get("qem")
    if qem_path is not None and str(qem_path).strip():
        em_p = _resolve(str(qem_path))
        qem_doc = _load_yaml(em_p)
        validate_assumption_document_header(qem_doc, source=str(em_p))

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
