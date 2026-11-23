"""Shared Design JSON fragments for synthesized filters."""

from __future__ import annotations

from fairbeam.design import DESIGN_SCHEMA
from fairbeam.starters import END_DB, MESH, PML


def microstrip_filter_base(
    *,
    design_id: str,
    name: str,
    description: str,
    stack_params: list[dict],
    electrical_params: list[dict],
    f0_key: str = "f0",
) -> dict:
    """Materials, substrate stack parameters, simulation block, and empty geometry shell."""
    return {
        "schema": DESIGN_SCHEMA,
        "model": {"id": design_id, "name": name, "description": description},
        "params": [*stack_params, *electrical_params],
        "simulation": {
            "f_min": f"0.2*{f0_key}",
            "f_max": f"2*{f0_key}",
            "boundaries": PML,
            "end_criteria_db": END_DB,
        },
        "materials": [
            {"name": "copper", "kind": "metal", "label": "Copper"},
            {
                "name": "substrate",
                "kind": "dielectric",
                "eps_r": "eps_r",
                "tan_d": "tan_d",
                "tan_d_freq": f0_key,
                "label": "Substrate",
            },
        ],
        "parts": [],
        "ports": [],
        "resistors": [],
        "mesh": dict(MESH),
        "far_field": {"enabled": False},
    }


def stripline_filter_base(
    *,
    design_id: str,
    name: str,
    description: str,
    stack_params: list[dict],
    electrical_params: list[dict],
    f0_key: str = "f0",
) -> dict:
    """Sandwich stripline stack: dielectric between two ground planes, center conductor at z = 0."""
    return {
        "schema": DESIGN_SCHEMA,
        "model": {"id": design_id, "name": name, "description": description},
        "params": [*stack_params, *electrical_params],
        "simulation": {
            "f_min": f"f0-1.5*bw",
            "f_max": f"f0+1.5*bw",
            "boundaries": PML,
            "end_criteria_db": END_DB,
        },
        "materials": [
            {"name": "copper", "kind": "metal", "label": "Copper"},
            {
                "name": "substrate",
                "kind": "dielectric",
                "eps_r": "eps_r",
                "tan_d": "tan_d",
                "tan_d_freq": f0_key,
                "label": "Stripline dielectric",
            },
        ],
        "parts": [],
        "ports": [],
        "resistors": [],
        "mesh": dict(MESH),
        "far_field": {"enabled": False},
    }


def stripline_sandwich_parts(*, span_x0: str, span_x1: str) -> list[dict]:
    """Dielectric slab between ``±b/2`` and matching top/bottom ground PEC sheets."""
    substrate_prim = {
        "kind": "box",
        "priority": 0,
        "start": [span_x0, "-y_half", "-b/2"],
        "stop": [span_x1, "y_half", "b/2"],
    }
    gnd_bottom_prim = {
        "kind": "box",
        "priority": 10,
        "start": [span_x0, "-y_half", "-b/2"],
        "stop": [span_x1, "y_half", "-b/2"],
    }
    gnd_top_prim = {
        "kind": "box",
        "priority": 10,
        "start": [span_x0, "-y_half", "b/2"],
        "stop": [span_x1, "y_half", "b/2"],
    }
    return [
        {"name": "substrate", "material": "substrate", "label": "Stripline dielectric", "primitives": [substrate_prim]},
        {"name": "gnd_bottom", "material": "copper", "label": "Bottom ground", "primitives": [gnd_bottom_prim]},
        {"name": "gnd_top", "material": "copper", "label": "Top ground", "primitives": [gnd_top_prim]},
    ]


def add_tunable_layout_params(design: dict, layout_dims: list[dict], *, band_fraction: float = 0.2) -> None:
    """Append independent layout parameters with default ±band_fraction min/max."""
    for dim in layout_dims:
        default = float(dim["default"])
        span = abs(default) * band_fraction or 0.1
        row = {
            "key": dim["key"],
            "default": default,
            "label": dim.get("label", dim["key"]),
            "unit": dim.get("unit", "mm"),
            "min": default - span,
            "max": default + span,
        }
        if desc := dim.get("description"):
            row["description"] = desc
        design["params"].append(row)
