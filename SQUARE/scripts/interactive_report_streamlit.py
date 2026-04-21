"""
Thin interactive UI: sliders bind to :data:`square.mc.overrides.PARAMETER_LAYERS` entries present
in the loaded scenario stack; one shot rebuild shows frozen ``dashboard`` keys, failure proxy,
magic flags, and ``warnings``.

Run from the ``SQUARE/`` directory (so ``Assumptions/Schemas.yaml`` resolves), after
``pip install -e ".[web]"``::

    streamlit run scripts/interactive_report_streamlit.py
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from square.loader import find_square_root, load_scenario_bundle
from square.mc.overrides import PARAMETER_LAYERS, apply_numeric_overrides
from square.plotting import extract_report_plot_frame, write_report_semantics_png
from square.report import build_scenario_report
from square.yaml_assumption import is_parameter_entry


def _slider_bounds(value: float) -> tuple[float, float, float]:
    if value == 0.0:
        return -1e-6, 1e-6, 0.0
    lo = value * 0.25
    hi = value * 4.0
    if lo > hi:
        lo, hi = hi, lo
    return lo, hi, value


def main() -> None:
    st.set_page_config(page_title="SQuaRE interactive report", layout="wide")
    st.title("SQuaRE — interactive report (frozen keys)")
    st.caption(
        "Sliders only touch ``PARAMETER_LAYERS`` overrides documented for Monte Carlo; "
        "outputs mirror ``square-report`` JSON (subset below)."
    )

    col_a, col_b = st.columns(2)
    with col_a:
        scen_rel = st.text_input("Scenario path (under repo)", "Configs/oratomic_gold_path.yaml")
    with col_b:
        root_in = st.text_input("SQuaRE root (empty = search from cwd)", "")

    try:
        root = Path(root_in).resolve() if root_in.strip() else find_square_root(Path.cwd())
    except FileNotFoundError as exc:
        st.error(str(exc))
        st.stop()

    scen_path = (root / scen_rel).resolve()
    if not scen_path.is_file():
        st.error(f"Scenario not found: {scen_path}")
        st.stop()
    try:
        scen_path.relative_to(root.resolve())
    except ValueError:
        st.error("Scenario path must lie under the SQuaRE root.")
        st.stop()

    try:
        bundle0 = load_scenario_bundle(scen_path, root=root, require_scenario_under_root=True)
    except (TypeError, ValueError, FileNotFoundError) as exc:
        st.error(f"Load failed: {exc}")
        st.stop()

    st.subheader("θ overrides (PARAMETER_LAYERS present in YAML)")
    overrides: dict[str, float] = {}
    for key, layer in PARAMETER_LAYERS.items():
        doc = bundle0.modality if layer == "modality" else bundle0.qec
        entry = doc.get(key)
        if not is_parameter_entry(entry):
            continue
        assert isinstance(entry, dict)
        raw = entry.get("value")
        if not isinstance(raw, (int, float)):
            continue
        base = float(raw)
        lo, hi, _ = _slider_bounds(base)
        overrides[key] = st.slider(f"{key} ({layer})", min_value=lo, max_value=hi, value=base, format="%g")

    d_raw = st.number_input("Optional code distance override (0 = use scenario heuristic)", 0, 10_000, 0)
    code_distance_override = None if d_raw == 0 else int(d_raw)

    if st.button("Build report", type="primary"):
        b = apply_numeric_overrides(bundle0, overrides) if overrides else bundle0
        try:
            report = build_scenario_report(b, code_distance_override=code_distance_override)
        except (TypeError, ValueError) as exc:
            st.error(f"Report build failed: {exc}")
            st.stop()

        frame = extract_report_plot_frame(report)
        st.json(frame)

        warns = report.get("warnings")
        if isinstance(warns, list) and warns:
            with st.expander("Warnings", expanded=True):
                for w in warns:
                    st.text(str(w))

        plot_path = Path(".streamlit_last_report_semantics.png")
        try:
            write_report_semantics_png(plot_path, report)
            st.image(str(plot_path), caption="Semantics chart (same as ``square-report --plot``)")
        except RuntimeError as exc:
            st.warning(str(exc))


if __name__ == "__main__":
    main()
