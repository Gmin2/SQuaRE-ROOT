"""Markdown summary of a structured scenario report (JSON remains canonical)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from square.report_dashboard import DASHBOARD_LOGICAL_FAILURE_PROXY_KEY


def report_to_markdown(report: Mapping[str, Any]) -> str:
    """
    Render a short Markdown summary of a report (JSON remains canonical).

    :param report: Output of :func:`square.report.build_scenario_report`.
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
        if report.get("algorithm_metrics", {}).get("ecdlp"):
            lines.append(
                f"**Target** ECDLP `{tgt.get('problem')}` · variant `{tgt.get('ecdlp_variant')}` "
                f"(curve bits {tgt.get('curve_bit_length')})\n"
            )
        else:
            lines.append(
                f"**Target** modulus bits **{tgt.get('modulus_bit_length')}**, problem `{tgt.get('problem')}`\n"
            )

    dash = report.get("dashboard", {})
    lines.append("## Headlines\n")
    lines.append(f"- **n (evaluation):** {report.get('algorithm_metrics', {}).get('n')}\n")
    lines.append(f"- **Abstract logical qubits (evaluated):** {dash.get('logical_qubits_at_n')}\n")
    lines.append(f"- **CCZ factories (from scenario row):** {dash.get('ccz_factory_count')}\n")
    lines.append(f"- **Reported RSA-2048 physical qubits (M):** {dash.get('reported_rsa2048_physical_qubits_millions')}\n")
    lines.append(f"- **Toffoli+T/2 (billions) at n:** {dash.get('toffoli_plus_t_halves_billions_at_n')}\n")
    lines.append(f"- **Min. spacetime volume (megaqubit-days) at n:** {dash.get('minimum_spacetime_volume_megaqubitdays_at_n')}\n")
    lines.append(
        f"- **Table 2 pinned (RSA-2048, inferred CCZ): megaqubit-days:** {dash.get('reported_rsa2048_megaqubit_days')}, "
        f"**wall-clock days:** {dash.get('reported_rsa2048_wall_clock_days')}\n"
    )
    lines.append(
        f"- **Naive serial time (depth × surface cycle, not Table 2 wall-clock):** "
        f"{dash.get('naive_serial_time_days_from_depth_times_cycle')} days\n"
    )
    lines.append(
        f"- **Logical failure proxy (min(1, D×p_L), phenomenological; not P_fail):** "
        f"{dash.get(DASHBOARD_LOGICAL_FAILURE_PROXY_KEY)}\n"
    )
    lines.append(f"- **Code distance d (resolved):** {dash.get('code_distance_d')} (`{dash.get('qec_distance_resolution_mode')}`)\n")
    lines.append(f"- **Physical qubits / logical (at d):** {dash.get('logical_qubit_physical_qubits_if_distance_d')}\n")
    lines.append(f"- **Approx. data-plane physical qubits (logical × patch):** {dash.get('approximate_data_plane_physical_qubits')}\n")
    lines.append(
        f"- **Derived non-data overhead (pinned total − data plane):** {dash.get('derived_non_data_overhead_physical_qubits')}\n"
    )
    lines.append(
        f"- **Factory footprint from YAML (count × per-factory):** {dash.get('factory_footprint_physical_qubits_from_yaml')}\n"
    )
    lines.append(f"- **Schedule model v1 wall-clock (days):** {dash.get('schedule_model_v1_wall_clock_days')}\n")
    lines.append(
        f"- **Table2 / schedule_model_v1 ratio:** {dash.get('schedule_calibration_ratio_table2_over_model_v1')}\n"
    )
    lines.append(
        f"- **Magic supply adequate (proxy):** {dash.get('magic_supply_adequate')} · "
        f"**magic-limited runtime multiplier:** {dash.get('magic_limited_runtime_multiplier')}\n"
    )
    lines.append(
        f"- **T-factory (magic_aux):** fallback_recommended={dash.get('t_factory_fallback_recommended')} · "
        f"applicable_to_target={dash.get('t_factory_magic_aux_applicable_to_target')} · "
        f"transition_bits={dash.get('t_factory_transition_modulus_bits_order_of_magnitude')} · "
        f"transition_confidence={dash.get('t_factory_transition_scale_confidence')} · "
        f"branch_yaml_enabled={dash.get('t_factory_branch_yaml_enabled')} · "
        f"mechanism={dash.get('t_factory_fallback_non_clifford_mechanism')}\n"
    )

    phys_layer = report.get("physical_layer") or {}
    lines.append("\n## Physical layer (OSRE snapshot)\n")
    pn = phys_layer.get("notes") or []
    if pn:
        lines.append(f"- **Notes:** {' '.join(str(x) for x in pn)}\n")
    lines.append(
        f"- **Status:** `{phys_layer.get('status')}` · **document_id** `{phys_layer.get('document_id')}` · "
        f"**extended keys** {phys_layer.get('parameter_keys')}\n"
    )

    lf = report.get("logical_fault_model") or {}
    lfc = lf.get("logical_cycle_time") or {}
    lines.append("\n## Logical fault model\n")
    lines.append(f"- **Status:** `{lf.get('status')}`\n")
    lines.append(f"- **Logical error rate / cycle (phenomenological):** {lf.get('logical_error_rate_per_cycle')}\n")
    lines.append(
        f"- **Logical cycle time (µs, max of available components):** "
        f"{lfc.get('logical_cycle_time_microseconds')}\n"
    )

    sm = report.get("system_metrics") or {}
    lines.append("\n## System metrics (OSRE)\n")
    lines.append(f"- **Status:** `{sm.get('status')}` · **schema** `{sm.get('schema')}`\n")
    lines.append(f"- **LQC (logical qubit capacity proxy):** {sm.get('logical_qubit_capacity_lqc')}\n")
    lines.append(f"- **LOB (ε/p_L depth proxy):** {sm.get('logical_operations_budget_lob')}\n")
    lines.append(f"- **Headroom (LOB − D):** {sm.get('headroom_logical_depth')}\n")
    lines.append(f"- **QOT (parallel width / τ, layer-proxies/s):** {sm.get('quantum_operations_throughput_qot')}\n")
    lines.append(f"- **VER (QCVV-grounded gate error proxy):** {sm.get('validated_error_rate_ver')}\n")
    lines.append(f"- **Mitigated operations ceiling (LOB / Γ):** {sm.get('mitigated_operations_ceiling')}\n")

    ps = report.get("parameter_sensitivity") or {}
    lines.append("\n## Parameter sensitivity (local)\n")
    lines.append(f"- **Status:** `{ps.get('status')}` · **schema** `{ps.get('schema')}`\n")
    rk = ps.get("ranking_by_abs_derivative_code_distance_d") or []
    if rk:
        lines.append(f"- **Top drivers on code_distance_d:** {', '.join(str(x) for x in rk[:5])}\n")

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
