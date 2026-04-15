"""Load Monte Carlo study YAML (priors over theta)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from square.loader import find_square_root
from square.mc.overrides import PARAMETER_LAYERS
from square.mc.parameters import validate_distribution_spec


@dataclass(frozen=True)
class MonteCarloStudySpec:
    schema_version: int
    study_id: str
    description: str
    scope: str
    base_scenario: str
    parameters: list[dict[str, Any]]


def load_monte_carlo_study_spec(
    path: str | Path,
    *,
    root: Path | None = None,
) -> MonteCarloStudySpec:
    base = root if root is not None else find_square_root(Path(__file__))
    p = Path(path)
    if p.is_file():
        resolved = p.resolve()
    else:
        resolved = (base / path).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Monte Carlo study file not found: {path} (tried {resolved})")

    with resolved.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise TypeError("Study YAML root must be a mapping.")

    schema_version = int(raw.get("schema_version", 1))
    study_id = str(raw.get("study_id", resolved.stem))
    description = str(raw.get("description", ""))
    scope = str(raw.get("scope", "prior_predictive_only"))
    base_scenario = raw.get("base_scenario")
    if not base_scenario or not str(base_scenario).strip():
        raise ValueError("Study YAML must set base_scenario.")

    params = raw.get("parameters")
    if not isinstance(params, list) or not params:
        raise ValueError("Study YAML must contain a non-empty parameters: list.")

    for i, block in enumerate(params):
        if not isinstance(block, dict):
            raise TypeError(f"parameters[{i}] must be a mapping.")
        key = block.get("parameter_key")
        if not key or str(key).strip() == "":
            raise ValueError(f"parameters[{i}] must set parameter_key.")
        key_s = str(key).strip()
        if key_s not in PARAMETER_LAYERS:
            raise ValueError(f"Unknown parameter_key {key_s!r}. Supported: {sorted(PARAMETER_LAYERS)}")
        layer_decl = block.get("layer")
        if layer_decl is not None and str(layer_decl).strip() != PARAMETER_LAYERS[key_s]:
            raise ValueError(
                f"parameters[{i}] layer {layer_decl!r} does not match registry ({PARAMETER_LAYERS[key_s]!r})."
            )
        validate_distribution_spec(block)

    return MonteCarloStudySpec(
        schema_version=schema_version,
        study_id=study_id,
        description=description,
        scope=scope,
        base_scenario=str(base_scenario).strip(),
        parameters=list(params),
    )
