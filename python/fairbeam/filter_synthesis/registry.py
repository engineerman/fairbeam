"""Topology registry for the filter designer."""

from __future__ import annotations

from typing import Any

from fairbeam.filter_synthesis.hairpin_microstrip_bp import (
    hairpin_microstrip_bp_spec_from_body,
    synthesize_hairpin_microstrip_bp,
)
from fairbeam.filter_synthesis.hairpin_stripline_bp import (
    hairpin_stripline_bp_spec_from_body,
    synthesize_hairpin_stripline_bp,
)
from fairbeam.filter_synthesis.types import SynthesisResult, TopologySpec


def _synthesize_hairpin_microstrip_bp(body: dict[str, Any]) -> SynthesisResult:
    return synthesize_hairpin_microstrip_bp(hairpin_microstrip_bp_spec_from_body(body))


def _synthesize_hairpin_microstrip_bp_mitered(body: dict[str, Any]) -> SynthesisResult:
    payload = dict(body)
    layout = dict(payload.get("layout") or {})
    layout["fold_style"] = "mitered"
    payload["layout"] = layout
    if not payload.get("name"):
        payload["name"] = "Hairpin microstrip bandpass (mitered)"
    if not payload.get("design_id"):
        payload["design_id"] = "filter-hairpin-microstrip-bp-mitered"
    return synthesize_hairpin_microstrip_bp(hairpin_microstrip_bp_spec_from_body(payload))


def _synthesize_hairpin_stripline_bp(body: dict[str, Any]) -> SynthesisResult:
    return synthesize_hairpin_stripline_bp(hairpin_stripline_bp_spec_from_body(body))


TOPOLOGIES: dict[str, TopologySpec] = {
    "hairpin_microstrip_bp": TopologySpec(
        id="hairpin_microstrip_bp",
        label_key="filterDesigner.topologies.hairpin_microstrip_bp",
        filter_class="bandpass",
        medium="microstrip",
        input_schema={},
        synthesize=_synthesize_hairpin_microstrip_bp,
    ),
    "hairpin_microstrip_bp_mitered": TopologySpec(
        id="hairpin_microstrip_bp_mitered",
        label_key="hairpinDesigner.topology.hairpin_microstrip_bp_mitered",
        filter_class="bandpass",
        medium="microstrip",
        input_schema={},
        synthesize=_synthesize_hairpin_microstrip_bp_mitered,
    ),
    "hairpin_stripline_bp": TopologySpec(
        id="hairpin_stripline_bp",
        label_key="filterDesigner.topologies.hairpin_stripline_bp",
        filter_class="bandpass",
        medium="stripline",
        input_schema={},
        synthesize=_synthesize_hairpin_stripline_bp,
    ),
}


def topology_public_dict(spec: TopologySpec) -> dict[str, Any]:
    return {
        "id": spec.id,
        "label_key": spec.label_key,
        "filter_class": spec.filter_class,
        "medium": spec.medium,
        "input_schema": spec.input_schema,
    }


def list_topologies() -> list[dict[str, Any]]:
    return [topology_public_dict(spec) for spec in TOPOLOGIES.values()]


def get_topology(topology_id: str) -> TopologySpec | None:
    return TOPOLOGIES.get(topology_id)


def synthesize(topology_id: str, body: dict[str, Any]) -> SynthesisResult:
    spec = get_topology(topology_id)
    if spec is None:
        raise KeyError(f"unknown filter topology: {topology_id!r}")
    return spec.synthesize(body)
