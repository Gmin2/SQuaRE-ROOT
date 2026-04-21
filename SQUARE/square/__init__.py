"""SQuaRE Python package: scenario loading and structured reports."""

from square.loader import ScenarioBundle, find_square_root, load_scenario_bundle
from square.report import (
    REPORT_CONTRACT_VERSION,
    build_scenario_report,
    report_to_markdown,
)

__all__ = [
    "REPORT_CONTRACT_VERSION",
    "ScenarioBundle",
    "build_scenario_report",
    "find_square_root",
    "load_scenario_bundle",
    "report_to_markdown",
]
