"""Latin hypercube sampling for uniform marginal parameters (variance reduction)."""

from __future__ import annotations

import random
from typing import Any


def all_blocks_uniform_for_lhs(parameters: list[dict[str, Any]]) -> bool:
    return all(str(b.get("distribution", "")).strip().lower() == "uniform" for b in parameters)


def generate_lhs_uniform_thetas(
    parameters: list[dict[str, Any]],
    n_samples: int,
    rng: random.Random,
) -> list[dict[str, float]]:
    """
    Latin hypercube in K dimensions (one uniform parameter per dimension).

    Each dimension uses a random permutation of stratum indices; within stratum ``i``,
    draws ``U ~ uniform(stratum_lo, stratum_hi)``.
    """
    k = len(parameters)
    if k == 0:
        return []
    perms: list[list[int]] = [list(range(n_samples)) for _ in range(k)]
    for perm in perms:
        rng.shuffle(perm)

    thetas: list[dict[str, float]] = []
    for i in range(n_samples):
        theta: dict[str, float] = {}
        for j, block in enumerate(parameters):
            key = str(block["parameter_key"]).strip()
            lo, hi = float(block["low"]), float(block["high"])
            stratum_idx = perms[j][i]
            w = (hi - lo) / n_samples
            a = lo + stratum_idx * w
            b = a + w
            theta[key] = rng.uniform(a, b)
        thetas.append(theta)
    return thetas
