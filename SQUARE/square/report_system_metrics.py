"""OSRE-style system metrics block (LQC, LOB, QOT, headroom, VER, mitigated ceiling)."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from square.yaml_numeric import (
    read_modality_characteristic_gate_error,
    read_parameter_entry_float,
)


def _routing_margin_logical_qubits(scenario: Mapping[str, Any]) -> float:
    """Optional ``scenario.system_metrics.routing_margin_logical_qubits`` (non-negative)."""
    sm = scenario.get("system_metrics")
    if not isinstance(sm, dict):
        return 0.0
    raw = sm.get("routing_margin_logical_qubits", 0.0)
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, v)


def build_system_metrics_block(
    *,
    scenario: Mapping[str, Any],
    modality: Mapping[str, Any],
    qcvv_doc: Mapping[str, Any] | None,
    qem_doc: Mapping[str, Any] | None,
    reported_total_physical_qubits: float | None,
    factory_footprint_physical_qubits: float | None,
    patch_physical_per_logical: float | None,
    logical_fault_model: Mapping[str, Any],
    evaluated: Mapping[str, Any],
    schedule_model_v1: Mapping[str, Any] | None,
    ccz_factory_count: int | None,
    warnings: list[str],
) -> dict[str, Any]:
    """
    OSRE-style **LQC**, **LOB**, **QOT**, and related slots when inputs exist.

    * **LQC** — only when Table-2-scale ``reported_total_physical_qubits``, magic factory footprint,
      and patch ``physical_qubits_per_logical`` are all available; else ``null`` + doc string.
    * **LOB / headroom** — ``ε / (p_L × s_QEM)`` vs ``abstract_measurement_depth_layers`` when
      ``logical_fault_model`` supplies ``p_L`` and scenario ``qec.logical_error_budget`` supplies ε.
    * **QOT** — ``max(1, parallel_ccz_paths) / τ`` in abstract-layer-proxies per second when τ exists.
    * **VER** — modality gate error × QCVV multiplier when ``paths.qcvv`` is set.
    * **Mitigated operations ceiling** — ``LOB / Γ`` with QEM ``sampling_shot_overhead_multiplier`` as Γ;
      LOB already includes QEM ``s`` on ``p_L``.
    """
    _raw_qec = scenario.get("qec")
    qec_block: dict[str, Any] = _raw_qec if isinstance(_raw_qec, dict) else {}
    try:
        logical_error_budget = float(qec_block.get("logical_error_budget", 0.1))
    except (TypeError, ValueError):
        logical_error_budget = 0.1
        warnings.append("system_metrics: qec.logical_error_budget invalid; using 0.1 for LOB.")

    notes: list[str] = []

    lqc: float | None = None
    lqc_method: str | None = None
    if (
        reported_total_physical_qubits is not None
        and reported_total_physical_qubits > 0
        and factory_footprint_physical_qubits is not None
        and factory_footprint_physical_qubits >= 0
        and patch_physical_per_logical is not None
        and patch_physical_per_logical > 0
    ):
        slots_raw = reported_total_physical_qubits / patch_physical_per_logical
        slots_factory = factory_footprint_physical_qubits / patch_physical_per_logical
        margin = _routing_margin_logical_qubits(scenario)
        lqc = float(math.floor(max(0.0, slots_raw - slots_factory - margin)))
        lqc_method = (
            "floor((reported_end_to_end_physical_qubits - factory_footprint_physical_qubits) "
            "/ physical_qubits_per_logical - routing_margin_logical_qubits)"
        )
        notes.append(
            "LQC is a logical-slot proxy from pinned total physical qubits and YAML factory footprint; "
            "routing is only subtracted when scenario.system_metrics.routing_margin_logical_qubits is set."
        )
    else:
        notes.append(
            "LQC omitted: need reported_end_to_end_physical_qubits (e.g. Table 2 RSA pin), "
            "factory_footprint_physical_qubits_from_yaml, and evaluated physical_qubits_per_logical."
        )

    p_l = logical_fault_model.get("logical_error_rate_per_cycle")
    depth_entry = evaluated.get("abstract_measurement_depth_layers")
    d_layers: float | None = None
    if isinstance(depth_entry, dict) and depth_entry.get("value") is not None:
        try:
            d_layers = float(depth_entry["value"])
        except (TypeError, ValueError):
            warnings.append(
                "system_metrics: abstract_measurement_depth_layers.value not numeric; headroom omitted."
            )
            d_layers = None

    s_qem = 1.0
    if qem_doc is not None:
        s_opt = read_parameter_entry_float(
            qem_doc,
            "effective_logical_error_rate_suppression_factor",
            warnings,
            context="paths.qem",
        )
        if s_opt is not None and s_opt > 0.0:
            s_qem = float(s_opt)
        elif s_opt is not None:
            warnings.append(
                "system_metrics: QEM effective_logical_error_rate_suppression_factor <= 0; using 1.0 for LOB."
            )

    lob: float | None = None
    headroom: float | None = None
    if isinstance(p_l, (int, float)) and p_l > 0 and logical_error_budget > 0:
        denom = float(p_l) * s_qem
        lob = float(logical_error_budget / denom)
        notes.append(
            "LOB uses ε / (p_L × s_QEM) with phenomenological p_L from logical_fault_model "
            "(includes VER+scaling in p_L when enabled) and QEM effective_logical_error_rate_suppression_factor "
            "as s_QEM (1 when no QEM path)."
        )
        if d_layers is not None:
            headroom = float(lob - d_layers)
    else:
        notes.append("LOB/headroom omitted: need positive logical_error_rate_per_cycle and budget.")

    tau_us: float | None = None
    lct = logical_fault_model.get("logical_cycle_time")
    if isinstance(lct, dict):
        raw_t = lct.get("logical_cycle_time_microseconds")
        if isinstance(raw_t, (int, float)) and raw_t > 0:
            tau_us = float(raw_t)

    parallel = 1
    if isinstance(schedule_model_v1, dict):
        try:
            parallel = max(1, int(schedule_model_v1.get("ccz_factory_count", 1)))
        except (TypeError, ValueError):
            parallel = 1
    elif ccz_factory_count is not None:
        try:
            parallel = max(1, int(ccz_factory_count))
        except (TypeError, ValueError):
            parallel = 1

    qot: float | None = None
    if tau_us is not None and tau_us > 0:
        tau_s = tau_us * 1e-6
        qot = float(parallel) / tau_s
        notes.append(
            "QOT is abstract-depth-proxies per wall-clock second: parallel_width / τ with τ from "
            "logical_fault_model and width from schedule_model_v1.ccz_factory_count or scenario CCZ count."
        )
    else:
        notes.append("QOT omitted: need logical_cycle_time_microseconds > 0.")

    ver: float | None = None
    p_nominal = read_modality_characteristic_gate_error(modality, warnings, context="paths.modality")
    if qcvv_doc is not None:
        sigma = read_parameter_entry_float(
            qcvv_doc,
            "effective_physical_error_rate_multiplier_from_characterization",
            warnings,
            context="paths.qcvv",
        )
        if p_nominal is None:
            notes.append(
                "VER omitted: need modality characteristic_physical_gate_error_rate for QCVV multiplier."
            )
        elif sigma is None:
            notes.append(
                "VER omitted: QCVV document missing effective_physical_error_rate_multiplier_from_characterization."
            )
        elif sigma <= 0.0:
            warnings.append("system_metrics: QCVV characterization multiplier <= 0; VER omitted.")
        else:
            ver = float(p_nominal * sigma)
            notes.append(
                "VER = modality characteristic_physical_gate_error_rate × "
                "QCVV effective_physical_error_rate_multiplier_from_characterization (scalar proxy)."
            )
    else:
        notes.append("VER omitted: no paths.qcvv (QCVV profile) in scenario.")

    mitigated_ceiling: float | None = None
    if qem_doc is not None:
        if lob is None:
            notes.append("mitigated_operations_ceiling omitted: need LOB (logical_fault_model p_L and budget).")
        else:
            gamma_raw = read_parameter_entry_float(
                qem_doc,
                "sampling_shot_overhead_multiplier",
                warnings,
                context="paths.qem",
            )
            gamma_use = float(gamma_raw) if gamma_raw is not None and gamma_raw > 0.0 else 1.0
            if gamma_raw is None or gamma_raw <= 0.0:
                warnings.append(
                    "system_metrics: QEM sampling_shot_overhead_multiplier missing or invalid; "
                    "using 1.0 for mitigated_operations_ceiling."
                )
            mitigated_ceiling = float(lob / gamma_use)
            notes.append(
                "mitigated_operations_ceiling = LOB / sampling_shot_overhead_multiplier (Γ); "
                "LOB already includes QEM suppression s on p_L."
            )
    else:
        notes.append("mitigated_operations_ceiling omitted: no paths.qem (QEM profile) in scenario.")

    pieces = [lqc is not None, lob is not None, qot is not None]
    if all(pieces):
        status = "computed"
    elif any(pieces):
        status = "partial"
    else:
        status = "insufficient_inputs"

    return {
        "schema": "system_metrics_v2",
        "status": status,
        "notes": notes,
        "logical_qubit_capacity_lqc": lqc,
        "logical_qubit_capacity_lqc_method": lqc_method,
        "logical_operations_budget_lob": lob,
        "headroom_logical_depth": headroom,
        "quantum_operations_throughput_qot": qot,
        "validated_error_rate_ver": ver,
        "mitigated_operations_ceiling": mitigated_ceiling,
    }
