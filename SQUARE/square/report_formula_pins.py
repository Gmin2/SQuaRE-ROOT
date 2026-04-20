"""
ECDLP fixed-problem evaluation, Table 1/2 pins, and algorithm pin resolution for scenario reports.

Kept separate from :mod:`square.report` so contract/dashboard work does not drag the full
orchestrator into every edit.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from square.report_formula_metrics import (
    FORMULA_METRICS,
    evaluate_non_ecdlp_formula_metrics,
)
from square.report_layers import DOCUMENT_HEADER_KEYS
from square.yaml_numeric import read_parameter_entry_float, read_scalar_float

_PINNED_SUFFIX_RE = re.compile(r"_n_(\d+)$")
_CCZ_ROW_RE = re.compile(r"_(\d+)_ccz\b")

TABLE1_PINS_KEY = "paper_table1_pins_by_modulus_bit_length"
TABLE2_RSA2048_ROWS_KEY = "paper_table2_rsa2048_reference_rows"

_ECDLP_DOCUMENT_IDS = frozenset({"ecdlp_secp256k1_babbush_et_al_2026"})
_ECDLP_ENVELOPE_KEY = "ecdlp_logical_resource_envelopes_secp256k1"


def parse_table2_pins_early(
    scenario: Mapping[str, Any], magic: Mapping[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """
    Parse Table-2 RSA pins that do not depend on code distance (before heuristic ``d``).

    :returns: Pin dict suitable for ``layout_estimate`` / dashboard, and warnings to extend.
    """
    local_warnings: list[str] = []
    table2_block = scenario.get("table2_reference_row")
    ccz_count: int | None = None
    if isinstance(table2_block, dict):
        ccz_count = _parse_ccz_count_from_table2(table2_block.get("value"))
    if ccz_count is None and isinstance(table2_block, str):
        ccz_count = _parse_ccz_count_from_table2(table2_block)

    rsa2048_phys: float | None = None
    phys_key: str | None = None
    rsa2048_megaqd: float | None = None
    mega_key: str | None = None
    rsa2048_wall_days: float | None = None
    wall_key: str | None = None
    factory_param_key: str | None = None
    table2_row_layout_descriptor: str | None = None

    if ccz_count is not None:
        row_ref = _table2_dashboard_row_ref(ccz_count)
        phys_key = mega_key = wall_key = row_ref
        t2_row = _table2_rsa2048_row_for_ccz(magic, ccz_count)
        if t2_row is None:
            local_warnings.append(
                f"No row with ccz_factories={ccz_count} in magic YAML {TABLE2_RSA2048_ROWS_KEY!r}; "
                "Table 2 pins omitted."
            )
        else:
            ld = t2_row.get("layout_descriptor")
            table2_row_layout_descriptor = str(ld) if ld is not None else None
            factory_param_key = table2_row_layout_descriptor
            if "physical_qubits_millions" not in t2_row:
                rsa2048_phys = None
                local_warnings.append(
                    f"Table 2 row {row_ref!r} missing physical_qubits_millions."
                )
            else:
                rsa2048_phys = read_scalar_float(
                    t2_row["physical_qubits_millions"],
                    local_warnings,
                    context=f"Table 2 row {row_ref!r} physical_qubits_millions",
                )
            if "megaqubit_days" not in t2_row:
                rsa2048_megaqd = None
                local_warnings.append(f"Table 2 row {row_ref!r} missing megaqubit_days.")
            else:
                rsa2048_megaqd = read_scalar_float(
                    t2_row["megaqubit_days"],
                    local_warnings,
                    context=f"Table 2 row {row_ref!r} megaqubit_days",
                )
            if "wall_clock_days" not in t2_row:
                rsa2048_wall_days = None
                local_warnings.append(f"Table 2 row {row_ref!r} missing wall_clock_days.")
            else:
                rsa2048_wall_days = read_scalar_float(
                    t2_row["wall_clock_days"],
                    local_warnings,
                    context=f"Table 2 row {row_ref!r} wall_clock_days",
                )
    elif table2_block is not None:
        local_warnings.append("Could not parse CCZ factory count from table2_reference_row.value.")

    pins = {
        "ccz_count": ccz_count,
        "rsa2048_phys": rsa2048_phys,
        "phys_key": phys_key,
        "rsa2048_megaqd": rsa2048_megaqd,
        "mega_key": mega_key,
        "rsa2048_wall_days": rsa2048_wall_days,
        "wall_key": wall_key,
        "factory_param_key": factory_param_key,
        "table2_row_layout_descriptor": table2_row_layout_descriptor,
    }
    return pins, local_warnings


def _parse_ccz_count_from_table2(row_value: Any) -> int | None:
    if row_value is None:
        return None
    text = str(row_value)
    m = _CCZ_ROW_RE.search(text)
    return int(m.group(1)) if m else None


def pinned_algorithm_entries_for_n(algorithm: Mapping[str, Any], n: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in algorithm.items():
        if key in DOCUMENT_HEADER_KEYS or not isinstance(val, dict):
            continue
        m = _PINNED_SUFFIX_RE.search(str(key))
        if m and int(m.group(1)) == n:
            out[str(key)] = val
    return out


def table1_pin_row(algo: Mapping[str, Any], n: int) -> dict[str, Any] | None:
    """Return the Table 1 pin sub-map for modulus bit length ``n`` when present."""
    entry = algo.get(TABLE1_PINS_KEY)
    if not isinstance(entry, dict):
        return None
    raw_val = entry.get("value")
    if not isinstance(raw_val, dict):
        return None
    sub = raw_val.get(str(int(n)))
    return sub if isinstance(sub, dict) else None


def _table2_rsa2048_row_for_ccz(magic: Mapping[str, Any], ccz: int) -> dict[str, Any] | None:
    """Match a Table 2 reference row by ``ccz_factories`` (RSA-2048 consolidated block)."""
    entry = magic.get(TABLE2_RSA2048_ROWS_KEY)
    if not isinstance(entry, dict):
        return None
    rows = entry.get("value")
    if not isinstance(rows, list):
        return None
    target = int(ccz)
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = row.get("ccz_factories")
        try:
            if raw is not None and int(raw) == target:
                return row
        except (TypeError, ValueError):
            continue
    return None


def synthetic_pinned_from_table1(algo: Mapping[str, Any], n: int) -> dict[str, Any]:
    """
    Rebuild legacy-style pinned parameter keys from Table 1 pins for ``algorithm_metrics``.
    """
    parent = algo.get(TABLE1_PINS_KEY)
    sub = table1_pin_row(algo, n)
    if not isinstance(parent, dict) or sub is None:
        return {}
    base = {
        "confidence": parent.get("confidence"),
        "source": parent.get("source"),
        "date": parent.get("date"),
        "section": parent.get("section"),
        "layer": "algorithm",
        "notes": f"Resolved from {TABLE1_PINS_KEY} for n={n}.",
    }
    out: dict[str, Any] = {}
    if "toffoli_plus_t_halves_billions" in sub:
        out[f"toffoli_plus_t_halves_count_billions_n_{n}"] = {
            **base,
            "value": sub["toffoli_plus_t_halves_billions"],
            "unit": "billions_of_toffoli_plus_t_halves",
        }
    if "minimum_spacetime_volume_megaqubit_days" in sub:
        out[f"minimum_spacetime_volume_megaqubitdays_n_{n}"] = {
            **base,
            "value": sub["minimum_spacetime_volume_megaqubit_days"],
            "unit": "megaqubit_days",
        }
    return out


def _table2_dashboard_row_ref(ccz: int) -> str:
    """Stable logical pointer into the consolidated Table 2 YAML block."""
    return f"{TABLE2_RSA2048_ROWS_KEY}#ccz_factories={int(ccz)}"


def _resolve_ecdlp_variant(scenario: Mapping[str, Any], warnings: list[str]) -> str:
    """Return scenario ``ecdlp_variant`` (default: low_toffoli_variant)."""
    _raw_target = scenario.get("target")
    tgt: dict[str, Any] = _raw_target if isinstance(_raw_target, dict) else {}
    raw = tgt.get("ecdlp_variant")
    if raw is None:
        raw = scenario.get("ecdlp_variant")
    if raw is None:
        return "low_toffoli_variant"
    s = str(raw).strip()
    allowed = frozenset({"low_logical_qubit_variant", "low_toffoli_variant"})
    if s in allowed:
        return s
    warnings.append(f"Unknown ecdlp_variant {raw!r}; using low_toffoli_variant.")
    return "low_toffoli_variant"


def _ecdlp_depth_multiplier(algo: Mapping[str, Any], warnings: list[str]) -> float:
    """Layers per Toffoli for ``abstract_measurement_depth_layers`` (II.1)."""
    raw = read_parameter_entry_float(
        algo,
        "ecdlp_measurement_depth_layers_per_toffoli_gate",
        warnings,
        context="paths.algorithm",
    )
    if raw is None:
        return 1.0
    if raw <= 0.0:
        warnings.append(
            "ecdlp_measurement_depth_layers_per_toffoli_gate must be positive; using 1.0 for depth multiplier."
        )
        return 1.0
    return float(raw)


def _ecdlp_headline_physical_upper_bound_narrative(algo: Mapping[str, Any]) -> float | None:
    e = algo.get("headline_superconducting_physical_qubits_upper_bound")
    if isinstance(e, dict) and e.get("value") is not None:
        try:
            return float(e["value"])
        except (TypeError, ValueError):
            return None
    return None


def _build_ecdlp_report_context(
    algo: Mapping[str, Any],
    scenario: Mapping[str, Any],
    warnings: list[str],
) -> dict[str, Any] | None:
    """
    Fixed-problem ECDLP profiles: fill ``evaluated`` logical qubits + depth proxy from cited envelopes.

    Depth proxy (II.1): ``abstract_measurement_depth_layers`` =
    ``toffoli_gates_upper_bound`` × ``ecdlp_measurement_depth_layers_per_toffoli_gate``.
    """
    if algo.get("document_id") not in _ECDLP_DOCUMENT_IDS:
        return None

    variant = _resolve_ecdlp_variant(scenario, warnings)
    env_parent = algo.get(_ECDLP_ENVELOPE_KEY)
    if not isinstance(env_parent, dict):
        warnings.append(f"ECDLP algorithm missing {_ECDLP_ENVELOPE_KEY!r}; skipping ECDLP evaluation.")
        return None
    env_val = env_parent.get("value")
    if not isinstance(env_val, dict) or variant not in env_val:
        warnings.append(f"ECDLP envelope missing variant {variant!r}.")
        return None
    row = env_val.get(variant)
    if not isinstance(row, dict):
        warnings.append("ECDLP envelope variant row is not a mapping.")
        return None
    try:
        lq = float(row["logical_qubits_upper_bound"])
        tof = float(row["toffoli_gates_upper_bound"])
    except (KeyError, TypeError, ValueError) as exc:
        warnings.append(f"ECDLP envelope numeric fields invalid: {exc}")
        return None

    mult = _ecdlp_depth_multiplier(algo, warnings)
    depth_layers = tof * mult
    prov = "ecdlp_envelope_fixed_problem"

    evaluated: dict[str, Any] = {
        "abstract_logical_qubits": {
            "value": lq,
            "source_parameter": _ECDLP_ENVELOPE_KEY,
            "provenance": prov,
        },
        "abstract_measurement_depth_layers": {
            "value": depth_layers,
            "source_parameter": _ECDLP_ENVELOPE_KEY,
            "provenance": prov,
            "depth_proxy": (
                "toffoli_gates_upper_bound × ecdlp_measurement_depth_layers_per_toffoli_gate "
                f"({tof} × {mult})"
            ),
        },
    }

    skipped = [src_key for src_key, _ in FORMULA_METRICS]
    skipped.append("exponent_register_qubits_ne_asymptotic")

    ecdlp_block: dict[str, Any] = {
        "active": True,
        "variant": variant,
        "logical_qubits_upper_bound": lq,
        "toffoli_gates_upper_bound": tof,
        "ecdlp_measurement_depth_layers_per_toffoli_gate": mult,
        "abstract_measurement_depth_layers_proxy": depth_layers,
        "depth_proxy_rule": "toffoli_upper_bound_times_layers_per_toffoli_parameter",
    }
    headline_pb = _ecdlp_headline_physical_upper_bound_narrative(algo)
    if headline_pb is not None:
        ecdlp_block["paper_headline_physical_qubits_upper_bound_narrative"] = headline_pb

    warnings.append(
        "ECDLP mode: abstract_measurement_depth_layers is a Toffoli-derived proxy for heuristics, "
        "not a compiled layer schedule from the undisclosed circuits."
    )

    return {
        "evaluated": evaluated,
        "evaluated_skipped": skipped,
        "ecdlp_block": ecdlp_block,
    }


@dataclass(frozen=True)
class FormulaEvaluationAndPins:
    """Result of formula metric evaluation plus algorithm YAML pins for ``algorithm_metrics``."""

    evaluated: dict[str, Any]
    evaluated_skipped: list[str]
    n: int | None
    ecdlp_block_for_metrics: dict[str, Any] | None
    pinned: dict[str, Any]


def build_formula_evaluation_and_pins(
    algo: Mapping[str, Any],
    scenario: Mapping[str, Any],
    target: Mapping[str, Any],
    warnings: list[str],
    *,
    modulus_bits_override: int | None = None,
) -> FormulaEvaluationAndPins:
    """
    ECDLP envelope path or generic formula metrics, then merge Table-1 synthetic pins with ``_n_`` pins.
    """
    ecdlp_ctx = _build_ecdlp_report_context(algo, scenario, warnings)
    ecdlp_block_for_metrics: dict[str, Any] | None = None
    evaluated: dict[str, Any] = {}
    evaluated_skipped: list[str] = []
    n: int | None = None

    if ecdlp_ctx is not None:
        evaluated = ecdlp_ctx["evaluated"]
        evaluated_skipped = ecdlp_ctx["evaluated_skipped"]
        ecdlp_block_for_metrics = ecdlp_ctx["ecdlp_block"]
    else:
        fm = evaluate_non_ecdlp_formula_metrics(
            algo,
            target,
            modulus_bits_override=modulus_bits_override,
            warnings=warnings,
        )
        evaluated = fm.evaluated
        evaluated_skipped = fm.evaluated_skipped
        n = fm.n

    pinned = pinned_algorithm_entries_for_n(algo, n) if n is not None else {}
    if n is not None:
        for k, v in synthetic_pinned_from_table1(algo, n).items():
            pinned.setdefault(k, v)

    return FormulaEvaluationAndPins(
        evaluated=evaluated,
        evaluated_skipped=evaluated_skipped,
        n=n,
        ecdlp_block_for_metrics=ecdlp_block_for_metrics,
        pinned=pinned,
    )
