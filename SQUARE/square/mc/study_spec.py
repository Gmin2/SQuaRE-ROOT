"""Load Monte Carlo study YAML (priors over theta).

Study files are parsed with ``yaml.safe_load`` and are treated as **trusted configuration**
(same trust model as scenario YAML). Do not point ``square-mc`` at untrusted paths.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from square.loader import find_square_root, resolve_path_under_square_root
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
    sampling_strategy: str = "independent"
    #: When true, each draw must yield all :data:`MC_STRICT_REQUIRED_METRIC_KEYS`; else the run aborts.
    strict_metrics: bool = False


def load_monte_carlo_study_spec(
    path: str | Path,
    *,
    root: Path | None = None,
) -> MonteCarloStudySpec:
    base = (root if root is not None else find_square_root(Path(__file__))).resolve()
    try:
        resolved = resolve_path_under_square_root(base, str(path))
    except ValueError as exc:
        raise ValueError(
            f"Monte Carlo study path must resolve under SQuaRE root {base}: {path!r}"
        ) from exc
    if not resolved.is_file():
        raise FileNotFoundError(f"Monte Carlo study file not found: {path} (tried {resolved})")

    with resolved.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise TypeError("Study YAML root must be a mapping.")

    raw_sv = raw.get("schema_version", 1)
    try:
        schema_version = int(raw_sv)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Study YAML schema_version must be an integer: {raw_sv!r}") from exc
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

    sampling_strategy = "independent"
    raw_s = raw.get("sampling")
    if isinstance(raw_s, dict):
        s = str(raw_s.get("strategy", "independent")).strip().lower()
        if s in ("independent", "latin_hypercube"):
            sampling_strategy = s
        else:
            raise ValueError(f"Unknown sampling.strategy {s!r}; use independent or latin_hypercube.")
    elif raw.get("sampling_strategy") is not None:
        s = str(raw["sampling_strategy"]).strip().lower()
        if s in ("independent", "latin_hypercube"):
            sampling_strategy = s
        else:
            raise ValueError(f"Unknown sampling_strategy {s!r}.")

    strict_metrics = False
    if raw.get("strict_metrics") is True:
        strict_metrics = True
    elif isinstance(raw.get("mc"), dict) and raw["mc"].get("strict_metrics") is True:
        strict_metrics = True

    return MonteCarloStudySpec(
        schema_version=schema_version,
        study_id=study_id,
        description=description,
        scope=scope,
        base_scenario=str(base_scenario).strip(),
        parameters=list(params),
        sampling_strategy=sampling_strategy,
        strict_metrics=strict_metrics,
    )
