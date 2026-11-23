"""Shared types for filter topology synthesis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class SynthesisResult:
    """Output of a topology synthesize() call."""

    design: dict[str, Any]
    dimensions: list[dict[str, Any]]
    preview: dict[str, Any]
    caveats: list[str]
    geometry_preview: dict[str, Any] | None = None


class BandwidthInfeasible(ValueError):
    """Synthesis refused because layout features are below substrate scale (narrow BW / high order)."""

    code = "bandwidth_infeasible"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class TopologySpec:
    """Registered filter topology (card id → synthesis entry point)."""

    id: str
    label_key: str
    filter_class: str
    medium: str
    input_schema: dict[str, Any]
    synthesize: Callable[[dict[str, Any]], SynthesisResult]
