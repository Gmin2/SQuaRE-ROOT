"""
Build structured reports from a :class:`~square.loader.ScenarioBundle`.

Output shape is documented in ``docs/output-contract.md`` (``report_contract_version``).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Mapping

from square.formula_eval import FormulaEvalError, eval_numeric_formula
from square.loader import ScenarioBundle

_REPORT_CONTRACT_VERSION = 1

_HEADER_KEYS = frozenset(
    {
        "document_id",
        "schema_version",
        "primary_reference",
        "doi",
        "arxiv",
        "date_issued",
        "notes",
    }
)

_FORMULA_METRICS: tuple[tuple[str, str], ...] = (
    ("abstract_logical_qubits_formula", "abstract_logical_qubits"),
    ("abstract_measurement_depth_formula", "abstract_measurement_depth_layers"),
    ("abstract_toffoli_plus_t_halves_count_formula", "abstract_toffoli_plus_t_halves_count"),
)

_PINNED_SUFFIX_RE = re.compile(r"_n_(\d+)$")
_CCZ_ROW_RE = re.compile(r"_(\d+)_ccz\b")


def _is_parameter_entry(obj: Any) -> bool:
    return isinstance(obj, dict) and "value" in obj and "unit" in obj


def _split_document(doc: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    header: dict[str, Any] = {}
    parameters: dict[str, Any] = {}
    for key, val in doc.items():
        sk = str(key)
        if sk in _HEADER_KEYS:
            header[sk] = val
        elif _is_parameter_entry(val):
            parameters[sk] = val
        else:
            header[sk] = val
    return header, parameters


def _source_header(doc: Mapping[str, Any]) -> dict[str, Any]:
    return {k: doc[k] for k in _HEADER_KEYS if k in doc}


def _scenario_public_dict(scenario: Mapping[str, Any]) -> dict[str, Any]:
    return dict(scenario)


def _parse_ccz_count_from_table2(row_value: Any) -> int | None:
    if row_value is None:
        return None
    text = str(row_value)
    m = _CCZ_ROW_RE.search(text)
    return int(m.group(1)) if m else None


def _pinned_algorithm_entries_for_n(algorithm: Mapping[str, Any], n: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in algorithm.items():
        if key in _HEADER_KEYS or not isinstance(val, dict):
            continue
        m = _PINNED_SUFFIX_RE.search(str(key))
        if m and int(m.group(1)) == n:
            out[str(key)] = val
    return out


def _find_ccz_factory_parameter_key(magic: Mapping[str, Any], ccz: int) -> str | None:
    for key, val in magic.items():
        if not str(key).startswith("ccz_factory_count"):
            continue
        if isinstance(val, dict) and val.get("value") == ccz:
            return str(key)
    return None


def _engine_version() -> str:
    try:
        from importlib.metadata import version

        return version("square")
    except Exception:
        return "0.0.1"


def build_scenario_report(
    bundle: ScenarioBundle,
    *,
    modulus_bits_override: int | None = None,
) -> dict[str, Any]:
    """
    Assemble a JSON-serializable report dict for the given bundle.

    :param bundle: Loaded scenario documents.
    :param modulus_bits_override: If set, use this ``n`` instead of ``target.modulus_bit_length``.
    """
    warnings: list[str] = []
    scenario = bundle.scenario
    target = scenario.get("target") if isinstance(scenario.get("target"), dict) else {}
    n_raw = modulus_bits_override if modulus_bits_override is not None else target.get("modulus_bit_length")
    n: int | None
    if n_raw is None:
        n = None
        warnings.append("No modulus_bit_length in scenario target (and no override); formula metrics skipped.")
    else:
        try:
            n = int(n_raw)
        except (TypeError, ValueError):
            n = None
            warnings.append("modulus_bit_length is not an integer; formula metrics skipped.")
        if n is not None and n <= 0:
            n = None
            warnings.append("modulus_bit_length must be positive; formula metrics skipped.")

    algo = bundle.algorithm
    evaluated: dict[str, Any] = {}
    evaluated_skipped: list[str] = []

    if n is not None:
        for src_key, out_key in _FORMULA_METRICS:
            entry = algo.get(src_key)
            if not isinstance(entry, dict):
                evaluated_skipped.append(src_key)
                continue
            raw = entry.get("value")
            if not isinstance(raw, str):
                evaluated_skipped.append(src_key)
                continue
            if "O(" in raw or "O(1)" in raw:
                evaluated_skipped.append(src_key)
                continue
            try:
                value = eval_numeric_formula(raw, float(n))
            except (FormulaEvalError, ZeroDivisionError, OverflowError) as exc:
                warnings.append(f"Could not evaluate {src_key!r}: {exc}")
                evaluated_skipped.append(src_key)
                continue
            evaluated[out_key] = {
                "value": value,
                "source_parameter": src_key,
                "provenance": "computed_from_yaml_formula",
            }

    exp = algo.get("exponent_register_qubits_ne_asymptotic")
    if isinstance(exp, dict) and isinstance(exp.get("value"), str) and "O(" in str(exp["value"]):
        evaluated_skipped.append("exponent_register_qubits_ne_asymptotic")

    pinned = _pinned_algorithm_entries_for_n(algo, n) if n is not None else {}

    patch_entry = bundle.qec.get("logical_qubit_patch_physical_qubit_count_formula")
    patch_formula: str | None = None
    if isinstance(patch_entry, dict) and isinstance(patch_entry.get("value"), str):
        patch_formula = str(patch_entry["value"])
        warnings.append(
            "Surface-code patch formula is present but code distance d is not in the scenario; "
            "physical qubits per logical are not computed."
        )

    table2_block = scenario.get("table2_reference_row")
    ccz_count = None
    if isinstance(table2_block, dict):
        ccz_count = _parse_ccz_count_from_table2(table2_block.get("value"))
    if ccz_count is None and isinstance(table2_block, str):
        ccz_count = _parse_ccz_count_from_table2(table2_block)

    rsa2048_phys: float | None = None
    phys_key: str | None = None
    factory_param_key: str | None = None
    if ccz_count is not None:
        phys_key = f"rsa_2048_reported_physical_qubits_millions_{ccz_count}_ccz"
        phys_entry = bundle.magic.get(phys_key)
        if isinstance(phys_entry, dict) and phys_entry.get("value") is not None:
            try:
                rsa2048_phys = float(phys_entry["value"])
            except (TypeError, ValueError):
                rsa2048_phys = None
                warnings.append(f"Magic YAML key {phys_key!r} has a non-numeric value.")
        else:
            warnings.append(
                f"No magic YAML entry {phys_key!r} for inferred CCZ count {ccz_count}; "
                "dashboard physical qubit headline omitted."
            )
        factory_param_key = _find_ccz_factory_parameter_key(bundle.magic, ccz_count)
        if factory_param_key is None:
            warnings.append(f"No ccz_factory_count* row in magic YAML matches count {ccz_count}.")
    elif table2_block is not None:
        warnings.append("Could not parse CCZ factory count from table2_reference_row.value.")

    toffoli_b = None
    megaqd = None
    if n is not None:
        tb = algo.get(f"toffoli_plus_t_halves_count_billions_n_{n}")
        if isinstance(tb, dict) and tb.get("value") is not None:
            try:
                toffoli_b = float(tb["value"])
            except (TypeError, ValueError):
                pass
        mq = algo.get(f"minimum_spacetime_volume_megaqubitdays_n_{n}")
        if isinstance(mq, dict) and mq.get("value") is not None:
            try:
                megaqd = float(mq["value"])
            except (TypeError, ValueError):
                pass

    t_fallback_recommended = False
    t_transition: int | None = None
    if bundle.magic_aux:
        trans = bundle.magic_aux.get("modulus_bit_length_ccz_to_t_transition_order_of_magnitude")
        if isinstance(trans, dict) and trans.get("value") is not None:
            try:
                t_transition = int(trans["value"])
            except (TypeError, ValueError):
                t_transition = None
        if n is not None and t_transition is not None and n >= t_transition:
            t_fallback_recommended = True
            warnings.append(
                f"n={n} is at or above the documented CCZ→T factory transition scale (~{t_transition} bits); "
                "magic_aux flags a different non-Clifford supply model."
            )

    modality_h, modality_p = _split_document(bundle.modality)
    qec_h, qec_p = _split_document(bundle.qec)
    magic_h, magic_p = _split_document(bundle.magic)
    algo_h, algo_p = _split_document(algo)

    magic_aux_layer = None
    if bundle.magic_aux is not None:
        mx_h, mx_p = _split_document(bundle.magic_aux)
        magic_aux_layer = {"header": mx_h, "parameters": mx_p}

    report: dict[str, Any] = {
        "report_contract_version": _REPORT_CONTRACT_VERSION,
        "engine": {"name": "square", "version": _engine_version()},
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "warnings": warnings,
        "scenario": _scenario_public_dict(scenario),
        "target": dict(target) if isinstance(target, dict) else {},
        "table2_reference": table2_block if isinstance(table2_block, dict) else None,
        "sources": {
            "modality": _source_header(bundle.modality),
            "qec": _source_header(bundle.qec),
            "magic": _source_header(bundle.magic),
            "algorithm": _source_header(algo),
            "magic_aux": _source_header(bundle.magic_aux) if bundle.magic_aux else None,
        },
        "layers": {
            "modality": {"document_id": modality_h.get("document_id"), "header": modality_h, "parameters": modality_p},
            "qec": {"document_id": qec_h.get("document_id"), "header": qec_h, "parameters": qec_p},
            "magic": {"document_id": magic_h.get("document_id"), "header": magic_h, "parameters": magic_p},
            "magic_aux": magic_aux_layer,
            "algorithm": {"document_id": algo_h.get("document_id"), "header": algo_h, "parameters": algo_p},
        },
        "algorithm_metrics": {
            "n": n,
            "evaluated": evaluated,
            "evaluated_skipped": evaluated_skipped,
            "pinned_in_algorithm_yaml": pinned,
        },
        "qec_overhead": {
            "logical_qubit_patch_physical_qubit_count": {
                "formula": patch_formula,
                "distance_d": None,
                "physical_qubits_per_logical": None,
                "status": "pending_distance_d" if patch_formula else "no_formula_in_profile",
            }
        },
        "dashboard": {
            "ccz_factory_count": ccz_count,
            "ccz_factory_parameter_key": factory_param_key,
            "rsa_2048_reported_physical_qubits_millions_key": phys_key,
            "reported_rsa2048_physical_qubits_millions": rsa2048_phys,
            "logical_qubits_at_n": evaluated.get("abstract_logical_qubits", {}).get("value")
            if isinstance(evaluated.get("abstract_logical_qubits"), dict)
            else None,
            "toffoli_plus_t_halves_billions_at_n": toffoli_b,
            "minimum_spacetime_volume_megaqubitdays_at_n": megaqd,
            "logical_qubit_physical_qubits_if_distance_d": None,
            "t_factory_fallback_recommended": t_fallback_recommended,
            "t_factory_transition_modulus_bits_order_of_magnitude": t_transition,
        },
    }

    return report


def report_to_markdown(report: Mapping[str, Any]) -> str:
    """
    Render a short Markdown summary of a report (JSON remains canonical).

    :param report: Output of :func:`build_scenario_report`.
    """
    lines: list[str] = []
    lines.append("# SQuaRE scenario report\n")
    eng = report.get("engine", {})
    lines.append(
        f"**Contract** v{report.get('report_contract_version')} · **Engine** {eng.get('name')} {eng.get('version')}\n"
    )
    lines.append(f"**Generated** {report.get('generated_at')}\n")
    scen = report.get("scenario", {})
    lines.append(f"**Scenario** `{scen.get('scenario')}` (schema {scen.get('schema_version')})\n")

    tgt = report.get("target", {})
    if tgt:
        lines.append(f"**Target** modulus bits **{tgt.get('modulus_bit_length')}**, problem `{tgt.get('problem')}`\n")

    dash = report.get("dashboard", {})
    lines.append("## Headlines\n")
    lines.append(f"- **n (evaluation):** {report.get('algorithm_metrics', {}).get('n')}\n")
    lines.append(f"- **Abstract logical qubits (evaluated):** {dash.get('logical_qubits_at_n')}\n")
    lines.append(f"- **CCZ factories (from scenario row):** {dash.get('ccz_factory_count')}\n")
    lines.append(f"- **Reported RSA-2048 physical qubits (M):** {dash.get('reported_rsa2048_physical_qubits_millions')}\n")
    lines.append(f"- **Toffoli+T/2 (billions) at n:** {dash.get('toffoli_plus_t_halves_billions_at_n')}\n")
    lines.append(f"- **Min. spacetime volume (megaqubit-days) at n:** {dash.get('minimum_spacetime_volume_megaqubitdays_at_n')}\n")
    lines.append(f"- **T-factory fallback flagged:** {dash.get('t_factory_fallback_recommended')}\n")

    warns = report.get("warnings") or []
    if warns:
        lines.append("\n## Warnings\n")
        for w in warns:
            lines.append(f"- {w}\n")

    lines.append("\n## Sources (document_id)\n")
    src = report.get("sources", {})
    for layer, block in src.items():
        if isinstance(block, dict) and block.get("document_id"):
            lines.append(f"- **{layer}:** `{block.get('document_id')}`\n")

    lines.append("\n*Full detail: emit JSON (`square-report` without `--markdown`).*\n")
    return "".join(lines)
