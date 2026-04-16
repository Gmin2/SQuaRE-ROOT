"""Apply numeric overrides to modality/QEC YAML for Monte Carlo studies."""

from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from square.loader import ScenarioBundle

PARAMETER_LAYERS: dict[str, str] = {
    "characteristic_physical_gate_error_rate": "modality",
    "surface_code_cycle_time": "modality",
    "classical_control_reaction_time": "modality",
    "heuristic_surface_code_physical_threshold_order_of_magnitude": "qec",
    "heuristic_logical_error_prefactor": "qec",
    "heuristic_distance_min_d": "qec",
    "heuristic_distance_max_d": "qec",
}


def _is_parameter_entry(obj: Any) -> bool:
    return isinstance(obj, dict) and "value" in obj and "unit" in obj


def apply_numeric_overrides(
    bundle: ScenarioBundle,
    overrides: Mapping[str, float],
) -> ScenarioBundle:
    if not overrides:
        return bundle

    modality = copy.deepcopy(dict(bundle.modality))
    qec = copy.deepcopy(dict(bundle.qec))

    for key, val in overrides.items():
        layer = PARAMETER_LAYERS.get(key)
        if layer is None:
            raise KeyError(
                f"Unknown override parameter {key!r}. Supported keys: {sorted(PARAMETER_LAYERS)}"
            )
        target = modality if layer == "modality" else qec
        entry = target.get(key)
        if not _is_parameter_entry(entry):
            raise TypeError(f"Cannot override {key!r}: expected a parameter_entry with value/unit.")
        assert isinstance(entry, dict)
        new_entry: dict[str, Any] = copy.deepcopy(entry)
        new_entry["value"] = float(val)
        target[key] = new_entry

    return replace(bundle, modality=modality, qec=qec)
