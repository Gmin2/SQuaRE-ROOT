"""Split assumption YAML roots into header vs parameters; build ``sources`` / ``layers`` report sections."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from square.loader import ScenarioBundle

DOCUMENT_HEADER_KEYS: frozenset[str] = frozenset(
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


def is_parameter_entry(obj: Any) -> bool:
    return isinstance(obj, dict) and "value" in obj and "unit" in obj


def split_document(doc: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    header: dict[str, Any] = {}
    parameters: dict[str, Any] = {}
    for key, val in doc.items():
        sk = str(key)
        if sk in DOCUMENT_HEADER_KEYS:
            header[sk] = val
        elif is_parameter_entry(val):
            parameters[sk] = val
        else:
            header[sk] = val
    return header, parameters


def source_header(doc: Mapping[str, Any]) -> dict[str, Any]:
    return {k: doc[k] for k in DOCUMENT_HEADER_KEYS if k in doc}


@dataclass(frozen=True)
class ReportSourcesLayers:
    """``sources`` + ``layers`` blocks and modality split for ``physical_layer``."""

    sources: dict[str, Any]
    layers: dict[str, Any]
    modality_header: dict[str, Any]
    modality_parameters: dict[str, Any]


def build_report_sources_and_layers(
    bundle: ScenarioBundle,
    algorithm: Mapping[str, Any],
) -> ReportSourcesLayers:
    modality_h, modality_p = split_document(bundle.modality)
    qec_h, qec_p = split_document(bundle.qec)
    magic_h, magic_p = split_document(bundle.magic)
    algo_h, algo_p = split_document(algorithm)

    magic_aux_layer = None
    if bundle.magic_aux is not None:
        mx_h, mx_p = split_document(bundle.magic_aux)
        magic_aux_layer = {"header": mx_h, "parameters": mx_p}

    qcvv_layer = None
    if bundle.qcvv is not None:
        qv_h, qv_p = split_document(bundle.qcvv)
        qcvv_layer = {"document_id": qv_h.get("document_id"), "header": qv_h, "parameters": qv_p}

    qem_layer = None
    if bundle.qem is not None:
        qm_h, qm_p = split_document(bundle.qem)
        qem_layer = {"document_id": qm_h.get("document_id"), "header": qm_h, "parameters": qm_p}

    sources = {
        "modality": source_header(bundle.modality),
        "qec": source_header(bundle.qec),
        "magic": source_header(bundle.magic),
        "algorithm": source_header(algorithm),
        "magic_aux": source_header(bundle.magic_aux) if bundle.magic_aux else None,
        "qcvv": source_header(bundle.qcvv) if bundle.qcvv else None,
        "qem": source_header(bundle.qem) if bundle.qem else None,
    }
    layers = {
        "modality": {"document_id": modality_h.get("document_id"), "header": modality_h, "parameters": modality_p},
        "qec": {"document_id": qec_h.get("document_id"), "header": qec_h, "parameters": qec_p},
        "magic": {"document_id": magic_h.get("document_id"), "header": magic_h, "parameters": magic_p},
        "magic_aux": magic_aux_layer,
        "qcvv": qcvv_layer,
        "qem": qem_layer,
        "algorithm": {"document_id": algo_h.get("document_id"), "header": algo_h, "parameters": algo_p},
    }
    return ReportSourcesLayers(
        sources=sources,
        layers=layers,
        modality_header=modality_h,
        modality_parameters=modality_p,
    )
