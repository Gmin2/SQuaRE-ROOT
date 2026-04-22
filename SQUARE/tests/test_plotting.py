"""Tests for ``square.plotting`` extractors (matplotlib figures optional)."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path

import pytest
from square.loader import find_square_root, load_scenario_bundle
from square.report_dashboard import DASHBOARD_LOGICAL_FAILURE_PROXY_KEY
from square.plotting import (
    extract_report_plot_frame,
    load_mc_samples_rows_from_csv,
    write_mc_semantics_png,
    write_report_semantics_png,
)
from square.report import build_scenario_report


def test_extract_report_plot_frame_rsa_keys() -> None:
    root = find_square_root()
    bundle = load_scenario_bundle(
        root / "Configs" / "rsa2048_gidney_ekera_2021_parallel.yaml",
        root=root,
    )
    report = build_scenario_report(bundle)
    frame = extract_report_plot_frame(report)
    assert frame["scenario"] == "rsa2048_gidney_ekera_2021_parallel"
    assert frame[DASHBOARD_LOGICAL_FAILURE_PROXY_KEY] is not None
    assert frame["magic_supply_adequate"] is True
    assert frame["magic_limited_runtime_multiplier"] == pytest.approx(1.0)
    assert frame["warnings_count"] is not None


@pytest.mark.skipif(importlib.util.find_spec("matplotlib") is None, reason="matplotlib not installed")
def test_write_report_semantics_png_to_bytesio() -> None:
    root = find_square_root()
    bundle = load_scenario_bundle(
        root / "Configs" / "oratomic_gold_path.yaml",
        root=root,
    )
    report = build_scenario_report(bundle)
    buf = io.BytesIO()
    out = write_report_semantics_png(buf, report)
    assert out is buf
    assert buf.tell() > 0
    buf.seek(0)
    assert buf.read(4) == b"\x89PNG"


@pytest.mark.skipif(importlib.util.find_spec("matplotlib") is None, reason="matplotlib not installed")
def test_write_report_semantics_png_smoke(tmp_path: Path) -> None:
    root = find_square_root()
    bundle = load_scenario_bundle(
        root / "Configs" / "oratomic_gold_path.yaml",
        root=root,
    )
    report = build_scenario_report(bundle)
    outp = tmp_path / "sem.png"
    write_report_semantics_png(outp, report)
    assert outp.is_file() and outp.stat().st_size > 500


def test_load_mc_samples_rows_from_csv_roundtrip(tmp_path: Path) -> None:
    csv_path = tmp_path / "s.csv"
    csv_path.write_text(
        "sample_index,characteristic_physical_gate_error_rate,"
        "logical_failure_proxy_union_depth_phenomenological,magic_limited_runtime_multiplier\n"
        "0,0.001,0.02,1.0\n"
        "1,0.002,0.04,1.0\n",
        encoding="utf-8",
    )
    rows = load_mc_samples_rows_from_csv(csv_path)
    assert len(rows) == 2
    assert rows[0]["characteristic_physical_gate_error_rate"] == pytest.approx(0.001)


@pytest.mark.skipif(importlib.util.find_spec("matplotlib") is None, reason="matplotlib not installed")
def test_write_mc_semantics_png_respects_plot_theta(tmp_path: Path) -> None:
    csv_path = tmp_path / "s.csv"
    csv_path.write_text(
        "sample_index,surface_code_cycle_time,logical_failure_proxy_union_depth_phenomenological,"
        "magic_limited_runtime_multiplier\n"
        "0,1.0,0.02,1.0\n"
        "1,2.0,0.04,1.0\n"
        "2,3.0,0.08,1.0\n",
        encoding="utf-8",
    )
    rows = load_mc_samples_rows_from_csv(csv_path)
    outp = tmp_path / "mc_theta.png"
    write_mc_semantics_png(
        outp,
        rows,
        theta_parameter_key="surface_code_cycle_time",
        study_parameter_key_order=None,
    )
    assert outp.stat().st_size > 400


@pytest.mark.skipif(importlib.util.find_spec("matplotlib") is None, reason="matplotlib not installed")
def test_write_mc_semantics_png_from_csv_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "s.csv"
    csv_path.write_text(
        "sample_index,characteristic_physical_gate_error_rate,"
        "logical_failure_proxy_union_depth_phenomenological,magic_limited_runtime_multiplier\n"
        "0,0.001,0.02,1.0\n"
        "1,0.002,0.05,1.0\n"
        "2,0.003,0.08,1.0\n",
        encoding="utf-8",
    )
    rows = load_mc_samples_rows_from_csv(csv_path)
    outp = tmp_path / "mc.png"
    write_mc_semantics_png(outp, rows)
    assert outp.stat().st_size > 400
