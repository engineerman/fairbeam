"""Hairpin stripline bandpass synthesis (alternating U + Hong tap)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from fairbeam.filter_synthesis.design_builder import add_tunable_layout_params, stripline_filter_base
from fairbeam.filter_synthesis.geometry_sketch import hairpin_bp_geometry_sketch
from fairbeam.filter_synthesis.hairpin_bp_common import (
    hairpin_filter_primitives,
    modal_z_pairs,
    synthesize_hairpin_layout,
)
from fairbeam.filter_synthesis.preview import coupled_line_bandpass_s, two_port_preview
from fairbeam.filter_synthesis.stripline import (
    stripline_center_width,
    stripline_coupled_from_modal,
)
from fairbeam.filter_synthesis.types import SynthesisResult


@dataclass(frozen=True)
class HairpinStriplineBpSpec:
    f0_hz: float
    order: int
    bw_hz: float
    ripple_db: float = 0.5
    z0: float = 50.0
    eps_r: float = 2.2
    b_mm: float = 3.2
    tan_d: float = 0.0
    feed_len_mm: float = 6.0
    board_margin_mm: float = 8.0
    intra_gap_mm: float | None = None
    design_name: str = "Hairpin stripline bandpass"
    design_id: str = "filter-hairpin-stripline-bp"


DEFAULT_HAIRPIN_STRIPLINE_BP = HairpinStriplineBpSpec(f0_hz=2e9, order=3, bw_hz=0.2e9)


def hairpin_stripline_bp_spec_from_body(body: dict[str, Any]) -> HairpinStriplineBpSpec:
    elec = body.get("electrical") or {}
    stack = body.get("stack") or {}
    layout = body.get("layout") or {}
    f0 = float(elec.get("f0_hz", elec.get("f0", 2e9)))
    bw_ghz = elec.get("bw_ghz")
    if bw_ghz is not None:
        bw_hz = float(bw_ghz) * 1e9
    else:
        bw_hz = float(elec.get("bw_hz", elec.get("bandwidth_hz", 0.2e9)))
    thickness = stack.get("thickness_mm", layout.get("b_mm", 3.2))
    intra = layout.get("intra_gap_mm")
    return HairpinStriplineBpSpec(
        f0_hz=f0,
        order=int(elec.get("order", 3)),
        bw_hz=bw_hz,
        ripple_db=float(elec.get("ripple_db", elec.get("ripple", 0.5))),
        z0=float(elec.get("z0", elec.get("reference_ohm", 50.0))),
        eps_r=float(stack.get("eps_r", 2.2)),
        b_mm=float(thickness),
        tan_d=float(stack.get("tan_d", 0.0)),
        feed_len_mm=float(layout.get("feed_len_mm", 6.0)),
        board_margin_mm=float(layout.get("board_margin_mm", 8.0)),
        intra_gap_mm=None if intra is None else float(intra),
        design_name=str(body.get("name") or "Hairpin stripline bandpass"),
        design_id=str(body.get("design_id") or "filter-hairpin-stripline-bp"),
    )


def _stripline_eps_eff(eps_r: float, _b_mm: float, _w_mm: float) -> float:
    return float(eps_r)


def synthesize_hairpin_stripline_bp(spec: HairpinStriplineBpSpec) -> SynthesisResult:
    fbw = spec.bw_hz / spec.f0_hz
    modal = modal_z_pairs(spec.order, fbw, spec.ripple_db, spec.z0)
    layout = synthesize_hairpin_layout(
        order=spec.order,
        fbw=fbw,
        ripple_db=spec.ripple_db,
        z0=spec.z0,
        eps_r=spec.eps_r,
        thickness_mm=spec.b_mm,
        f0_hz=spec.f0_hz,
        coupled_from_modal=stripline_coupled_from_modal,
        center_width=stripline_center_width,
        line_eps_eff=_stripline_eps_eff,
        intra_gap_mm=spec.intra_gap_mm,
    )
    resonators = layout["resonators"]
    inter_spacing = layout["inter_spacing"]
    w_feed = float(layout["w_feed"])
    quarter = float(layout["q_len"])
    tap = float(layout["tap_from_fold"])
    x_bases = layout["x_bases"]
    x_end = float(layout["x_end"])
    y_feed0 = float(layout["y_feed0"])
    y_feed1 = float(layout["y_feed1"])
    x_feed0 = -spec.feed_len_mm
    n_sec = len(resonators)

    f0_ghz = spec.f0_hz / 1e9
    bw_ghz = spec.bw_hz / 1e9
    stack_params = [
        {"key": "f0", "default": f0_ghz, "label": "Center frequency", "unit": "GHz", "min": 0.5, "max": 30.0},
        {"key": "bw", "default": bw_ghz, "label": "Absolute bandwidth", "unit": "GHz", "min": 0.01, "max": 10.0},
        {"key": "eps_r", "default": spec.eps_r, "label": "Dielectric permittivity", "unit": "", "min": 1.0, "max": 12.0},
        {"key": "b", "default": spec.b_mm, "label": "Ground separation", "unit": "mm", "min": 0.5, "max": 10.0},
        {"key": "tan_d", "default": spec.tan_d, "label": "Loss tangent at f₀", "unit": "", "min": 0.0, "max": 0.1},
    ]
    electrical_params = [
        {"key": "order", "default": float(spec.order), "label": "Filter order", "unit": ""},
        {"key": "ripple_db", "default": spec.ripple_db, "label": "Passband ripple", "unit": "dB"},
        {"key": "z0", "default": spec.z0, "label": "Port impedance", "unit": "Ω"},
        {"key": "feed_len", "default": spec.feed_len_mm, "label": "Feed length", "unit": "mm", "min": 2.0, "max": 30.0},
        {"key": "board_margin", "default": spec.board_margin_mm, "label": "Board margin", "unit": "mm", "min": 2.0, "max": 20.0},
    ]

    design = stripline_filter_base(
        design_id=spec.design_id,
        name=spec.design_name,
        description=(
            "Hairpin stripline bandpass (alternating U resonators, Hong tap offset from fold, "
            "symmetric inter-resonator spacing from Qe/k)."
        ),
        stack_params=stack_params,
        electrical_params=electrical_params,
    )

    layout_dims: list[dict[str, Any]] = [
        {"key": "w_feed", "default": w_feed, "label": "Feed width", "unit": "mm"},
        {"key": "q_len", "default": quarter, "label": "Quarter-wave length", "unit": "mm"},
        {"key": "tap_from_fold", "default": tap, "label": "Tap from fold", "unit": "mm"},
    ]
    for k, sec in enumerate(resonators):
        layout_dims.append({"key": f"w{k}", "default": sec["width_mm"], "label": f"Resonator {k + 1} width", "unit": "mm"})
        layout_dims.append(
            {"key": f"gap{k}", "default": sec["gap_mm"], "label": f"Resonator {k + 1} inner gap", "unit": "mm"}
        )
    for k, sp in enumerate(inter_spacing):
        layout_dims.append(
            {"key": f"sp{k}", "default": sp, "label": f"Spacing {k + 1} (between U resonators)", "unit": "mm"}
        )
    add_tunable_layout_params(design, layout_dims)

    for k in range(n_sec):
        design["params"].append({"key": f"x_base{k}", "default": x_bases[k], "label": f"Resonator {k + 1} x", "unit": "mm"})
    design["params"].append({"key": "x_end", "default": x_end, "label": "Output port x", "unit": "mm"})
    design["params"].append({"key": "y_feed0", "default": y_feed0, "label": "Input feed centre y", "unit": "mm"})
    design["params"].append({"key": "y_feed1", "default": y_feed1, "label": "Output feed centre y", "unit": "mm"})
    design["params"].append(
        {
            "key": "y_half",
            "expr": "max(q_len,y_feed0+w_feed/2,y_feed1+w_feed/2)+board_margin",
            "label": "Board top y",
            "unit": "mm",
        }
    )

    filter_primitives = hairpin_filter_primitives(
        resonators,
        x_feed0=x_feed0,
        feed_len=spec.feed_len_mm,
        x_end=x_end,
        w_feed=w_feed,
        metal_z_expr="0",
    )

    span_x0 = f"{x_feed0}"
    span_x1 = "x_end+feed_len"
    design["parts"] = [
        {
            "name": "substrate",
            "material": "substrate",
            "label": "Stripline dielectric",
            "primitives": [
                {
                    "kind": "box",
                    "priority": 0,
                    "start": [span_x0, "-board_margin", "-b/2"],
                    "stop": [span_x1, "y_half", "b/2"],
                }
            ],
        },
        {
            "name": "gnd_bottom",
            "material": "copper",
            "label": "Bottom ground",
            "primitives": [
                {
                    "kind": "box",
                    "priority": 10,
                    "start": [span_x0, "-board_margin", "-b/2"],
                    "stop": [span_x1, "y_half", "-b/2"],
                }
            ],
        },
        {
            "name": "gnd_top",
            "material": "copper",
            "label": "Top ground",
            "primitives": [
                {
                    "kind": "box",
                    "priority": 10,
                    "start": [span_x0, "-board_margin", "b/2"],
                    "stop": [span_x1, "y_half", "b/2"],
                }
            ],
        },
        {"name": "filter", "material": "copper", "label": "Hairpin filter", "primitives": filter_primitives},
    ]

    design["ports"] = [
        {
            "number": 1,
            "type": "lumped",
            "R": spec.z0,
            "excite": True,
            "start": [f"{x_feed0}", "y_feed0-w_feed/2", "-b/2"],
            "stop": [f"{x_feed0}", "y_feed0+w_feed/2", "b/2"],
            "direction": "z",
        },
        {
            "number": 2,
            "type": "lumped",
            "R": spec.z0,
            "excite": False,
            "start": ["x_end+feed_len", "y_feed1-w_feed/2", "-b/2"],
            "stop": ["x_end+feed_len", "y_feed1+w_feed/2", "b/2"],
            "direction": "z",
        },
    ]

    dimensions = [
        {"key": dim["key"], "value": float(dim["default"]), "unit": dim.get("unit", "mm"), "label": dim.get("label", dim["key"])}
        for dim in layout_dims
    ]

    f_hz = np.linspace(spec.f0_hz - 1.5 * spec.bw_hz, spec.f0_hz + 1.5 * spec.bw_hz, 161)
    f_hz = np.clip(f_hz, 1e6, None)
    s_mat = coupled_line_bandpass_s(
        f_hz, spec.f0_hz, modal, z0=spec.z0, feed_eps=spec.eps_r, feed_len_mm=spec.feed_len_mm
    )
    preview = two_port_preview(f_hz, s_mat)

    geometry_preview = hairpin_bp_geometry_sketch(
        x_feed0=x_feed0,
        x_end=x_end,
        feed_len=spec.feed_len_mm,
        feed_centres=[y_feed0, y_feed1],
        w_feed=w_feed,
        sections=resonators,
        quarter_mm=quarter,
        inter_spacing_mm=inter_spacing,
        tap_from_fold_mm=tap,
    )

    caveats = [
        "Homogeneous stripline hairpin map; fold and launch fields are not modeled.",
        "Layout uses alternating U resonators and a Hong tap-from-fold seed; retune sp* and tap_from_fold with EM.",
        "Preview is the ideal coupled-line prototype, not an openEMS result.",
    ]

    return SynthesisResult(
        design=design,
        dimensions=dimensions,
        preview=preview,
        caveats=caveats,
        geometry_preview=geometry_preview,
    )
