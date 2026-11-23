"""Substrate stack presets for the filter designer (microstrip vs stripline)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

StackKind = Literal["microstrip", "stripline"]


@dataclass(frozen=True)
class StackPreset:
    id: str
    stack_kind: StackKind
    label: str
    eps_r: float
    tan_d: float
    tan_d_freq_ghz: float | None
    thickness_mm: float
    material_id: str | None = None


FILTER_STACK_PRESETS: tuple[StackPreset, ...] = (
    StackPreset("fr4_ms_160", "microstrip", "FR4 · 1.60 mm (microstrip)", 4.3, 0.02, 1.0, 1.60, "fr4"),
    StackPreset("ro4003c_ms_152", "microstrip", "RO4003C · 1.52 mm (microstrip)", 3.38, 0.0027, 10.0, 1.524, "ro4003c"),
    StackPreset("ro4350b_ms_076", "microstrip", "RO4350B · 0.76 mm (microstrip)", 3.48, 0.0037, 10.0, 0.762, "ro4350b"),
    StackPreset("fr4_sl_320", "stripline", "FR4 · 3.20 mm (stripline core)", 4.3, 0.02, 1.0, 3.20, "fr4"),
    StackPreset("ro4003c_sl_318", "stripline", "RO4003C · 3.18 mm (stripline core)", 3.38, 0.0027, 10.0, 3.175, "ro4003c"),
    StackPreset("ro4350b_sl_254", "stripline", "RO4350B · 2.54 mm (stripline core)", 3.48, 0.0037, 10.0, 2.54, "ro4350b"),
)

_PRESETS_BY_ID = {p.id: p for p in FILTER_STACK_PRESETS}


def presets_for(stack_kind: StackKind) -> list[dict[str, Any]]:
    return [
        {
            "id": p.id,
            "stack_kind": p.stack_kind,
            "label": p.label,
            "eps_r": p.eps_r,
            "tan_d": p.tan_d,
            "tan_d_freq_ghz": p.tan_d_freq_ghz,
            "thickness_mm": p.thickness_mm,
            "material_id": p.material_id,
        }
        for p in FILTER_STACK_PRESETS
        if p.stack_kind == stack_kind
    ]


def get_preset(preset_id: str) -> StackPreset | None:
    return _PRESETS_BY_ID.get(preset_id)


def resolve_stack(stack: dict[str, Any], topology_medium: str) -> dict[str, Any]:
    """Merge preset fields into stack; validate preset_id vs topology medium."""
    if not isinstance(stack, dict):
        raise ValueError("stack must be an object")
    medium: StackKind = "stripline" if topology_medium == "stripline" else "microstrip"
    out = dict(stack)
    out.setdefault("stack_kind", medium)
    preset_id = out.get("preset_id")
    if preset_id:
        preset = get_preset(str(preset_id))
        if preset is None:
            raise ValueError(f"unknown stack preset: {preset_id!r}")
        if preset.stack_kind != medium:
            raise ValueError(
                f"preset {preset_id!r} is for {preset.stack_kind}, but topology expects {medium}"
            )
        out.setdefault("eps_r", preset.eps_r)
        out.setdefault("tan_d", preset.tan_d)
        if preset.tan_d_freq_ghz is not None:
            out.setdefault("tan_d_freq_ghz", preset.tan_d_freq_ghz)
        out.setdefault("thickness_mm", preset.thickness_mm)
        out.setdefault("material_id", preset.material_id)
    declared_kind = out.get("stack_kind")
    if declared_kind not in ("microstrip", "stripline"):
        raise ValueError("stack_kind must be microstrip or stripline")
    if declared_kind != medium:
        raise ValueError(f"stack_kind {declared_kind!r} does not match topology medium {medium!r}")
    return out
