"""Hairpin microstrip bandpass synthesis (alternating U + Hong tap)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from fairbeam.analytic import C0, microstrip_coupled_from_modal, microstrip_eps_eff, microstrip_width
from fairbeam.filter_synthesis.design_builder import add_tunable_layout_params, microstrip_filter_base
from fairbeam.filter_synthesis.geometry_sketch import hairpin_bp_geometry_sketch
from fairbeam.filter_synthesis.hairpin_bp_common import (
    HAIRPIN_RESPONSES,
    RESPONSE_CHEBYSHEV,
    hairpin_filter_primitives,
    modal_z_pairs,
    response_qe_ripple,
    synthesize_hairpin_layout,
)
from fairbeam.filter_synthesis.preview import coupled_line_bandpass_s, two_port_preview
from fairbeam.filter_synthesis.types import SynthesisResult


@dataclass(frozen=True)
class HairpinMicrostripBpSpec:
    f0_hz: float
    order: int
    bw_hz: float
    ripple_db: float = 0.5
    response: str = RESPONSE_CHEBYSHEV
    z0: float = 50.0
    eps_r: float = 4.2
    h_mm: float = 1.58
    tan_d: float = 0.02
    feed_len_mm: float = 6.0
    board_margin_mm: float = 8.0
    intra_gap_mm: float | None = None
    design_name: str = "Hairpin microstrip bandpass"
    design_id: str = "filter-hairpin-microstrip-bp"


DEFAULT_HAIRPIN_MICROSTRIP_BP = HairpinMicrostripBpSpec(f0_hz=2e9, order=3, bw_hz=0.2e9)


def hairpin_x_base_expr(index: int) -> str:
    """Cumulative U origin, the same sum ``hairpin_u_x_layout`` uses."""
    if index < 0:
        raise ValueError("resonator index must be >= 0")
    if index == 0:
        return "0"
    return f"x_base{index - 1}+2*w{index - 1}+gap{index - 1}+sp{index - 1}"


def hairpin_x_end_expr(n_res: int) -> str:
    if n_res < 1:
        raise ValueError("n_res must be at least 1")
    last = n_res - 1
    return f"x_base{last}+2*w{last}+gap{last}"


def hairpin_feed_y_expr(resonator: int) -> str:
    """Tap height: ``q_len - tap`` on an open-down U, otherwise ``tap``."""
    if resonator < 0:
        raise ValueError("resonator index must be >= 0")
    return f"tap_from_fold+open_down{resonator}*(q_len-2*tap_from_fold)"


def set_hairpin_placement_exprs(design: dict, n_res: int) -> None:
    """Write placement expressions for ``n_res`` U's. Independent knobs stay numeric."""
    if n_res < 1:
        raise ValueError("n_res must be at least 1")
    rows = {
        **{f"x_base{k}": hairpin_x_base_expr(k) for k in range(n_res)},
        "x_end": hairpin_x_end_expr(n_res),
        "y_feed0": hairpin_feed_y_expr(0),
        "y_feed1": hairpin_feed_y_expr(n_res - 1),
    }
    for key, expr in rows.items():
        found = False
        for param in design.get("params", []):
            if param.get("key") != key:
                continue
            param.pop("default", None)
            param.pop("min", None)
            param.pop("max", None)
            param["expr"] = expr
            found = True
            break
        if not found:
            raise KeyError(key)


def _order_from_electrical(elec: dict[str, Any]) -> int:
    raw = elec.get("order", 3)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError("order must be an integer >= 1")
    if isinstance(raw, float) and not raw.is_integer():
        raise ValueError("order must be an integer >= 1")
    order = int(raw)
    if order < 1:
        raise ValueError("order must be an integer >= 1")
    return order


def _response_from_electrical(elec: dict[str, Any]) -> str:
    raw = elec.get("response", RESPONSE_CHEBYSHEV)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return RESPONSE_CHEBYSHEV
    if not isinstance(raw, str):
        raise ValueError("response must be chebyshev, butterworth, or equiripple")
    kind = raw.strip().lower()
    if kind not in HAIRPIN_RESPONSES:
        raise ValueError("response must be chebyshev, butterworth, or equiripple")
    return kind


def hairpin_microstrip_bp_spec_from_body(body: dict[str, Any]) -> HairpinMicrostripBpSpec:
    elec = body.get("electrical") or {}
    stack = body.get("stack") or {}
    layout = body.get("layout") or {}
    f0 = float(elec.get("f0_hz", elec.get("f0", 2e9)))
    bw_ghz = elec.get("bw_ghz")
    if bw_ghz is not None:
        bw_hz = float(bw_ghz) * 1e9
    else:
        bw_hz = float(elec.get("bw_hz", elec.get("bandwidth_hz", 0.2e9)))
    thickness = stack.get("thickness_mm", layout.get("h_mm", 1.58))
    intra = layout.get("intra_gap_mm")
    return HairpinMicrostripBpSpec(
        f0_hz=f0,
        order=_order_from_electrical(elec),
        bw_hz=bw_hz,
        ripple_db=float(elec.get("ripple_db", elec.get("ripple", 0.5))),
        response=_response_from_electrical(elec),
        z0=float(elec.get("z0", elec.get("reference_ohm", 50.0))),
        eps_r=float(stack.get("eps_r", 4.2)),
        h_mm=float(thickness),
        tan_d=float(stack.get("tan_d", 0.02)),
        feed_len_mm=float(layout.get("feed_len_mm", 6.0)),
        board_margin_mm=float(layout.get("board_margin_mm", 8.0)),
        intra_gap_mm=None if intra is None else float(intra),
        design_name=str(body.get("name") or "Hairpin microstrip bandpass"),
        design_id=str(body.get("design_id") or "filter-hairpin-microstrip-bp"),
    )


def _prototype_ripple(spec: HairpinMicrostripBpSpec) -> float:
    """Ripple passed into Qe/k and the J-inverter preview.

    The spec still keeps ``ripple_db`` (the wizard's stored number). Equiripple
    does not turn that number into a Chebyshev passband ripple.
    """
    qe_ripple = response_qe_ripple(spec.response, spec.ripple_db)
    if qe_ripple is None:
        raise ValueError(
            "Equiripple ripple is stored and is not used as Chebyshev passband ripple; "
            "no Qe/k formula is defined."
        )
    return qe_ripple


def synthesize_hairpin_microstrip_bp(spec: HairpinMicrostripBpSpec) -> SynthesisResult:
    if (
        not math.isfinite(spec.f0_hz)
        or not math.isfinite(spec.bw_hz)
        or spec.f0_hz == 0
        or not (spec.bw_hz / spec.f0_hz > 0)
    ):
        raise ValueError("fbw must be positive")
    if isinstance(spec.order, bool) or not isinstance(spec.order, int) or spec.order < 1:
        raise ValueError("order must be an integer >= 1")
    prototype_ripple = _prototype_ripple(spec)
    fbw = spec.bw_hz / spec.f0_hz
    modal = modal_z_pairs(spec.order, fbw, prototype_ripple, spec.z0)
    layout = synthesize_hairpin_layout(
        order=spec.order,
        fbw=fbw,
        ripple_db=spec.ripple_db,
        response=spec.response,
        z0=spec.z0,
        eps_r=spec.eps_r,
        thickness_mm=spec.h_mm,
        f0_hz=spec.f0_hz,
        coupled_from_modal=microstrip_coupled_from_modal,
        center_width=microstrip_width,
        line_eps_eff=microstrip_eps_eff,
        intra_gap_mm=spec.intra_gap_mm,
        c0=C0,
    )
    resonators = layout["resonators"]
    inter_spacing = layout["inter_spacing"]
    w_feed = float(layout["w_feed"])
    quarter = float(layout["q_len"])
    tap = float(layout["tap_from_fold"])
    x_end = float(layout["x_end"])
    y_feed0 = float(layout["y_feed0"])
    y_feed1 = float(layout["y_feed1"])
    x_feed0 = -spec.feed_len_mm
    n_sec = len(resonators)

    f0_ghz = spec.f0_hz / 1e9
    bw_ghz = spec.bw_hz / 1e9
    stack_params = [
        {"key": "f0", "default": f0_ghz, "label": "Merkez frekansı", "unit": "GHz", "min": 0.5, "max": 30.0},
        {"key": "bw", "default": bw_ghz, "label": "Bant genişliği", "unit": "GHz", "min": 0.01, "max": 10.0},
        {"key": "eps_r", "default": spec.eps_r, "label": "Dielektrik sabiti", "unit": "", "min": 1.0, "max": 12.0},
        {"key": "h", "default": spec.h_mm, "label": "Alttaş kalınlığı", "unit": "mm", "min": 0.1, "max": 5.0},
        {"key": "tan_d", "default": spec.tan_d, "label": "Kayıp tanjantı", "unit": "", "min": 0.0, "max": 0.1},
    ]
    electrical_params = [
        {"key": "order", "default": float(spec.order), "label": "Filter order", "unit": ""},
        {"key": "ripple_db", "default": spec.ripple_db, "label": "Passband ripple", "unit": "dB"},
        {"key": "z0", "default": spec.z0, "label": "Port impedance", "unit": "Ω"},
        {"key": "feed_len", "default": spec.feed_len_mm, "label": "Besleme uzunluğu", "unit": "mm", "min": 2.0, "max": 30.0},
        {"key": "board_margin", "default": spec.board_margin_mm, "label": "Kart payı", "unit": "mm", "min": 2.0, "max": 20.0},
    ]

    design = microstrip_filter_base(
        design_id=spec.design_id,
        name=spec.design_name,
        description=(
            "Hairpin microstrip bandpass (alternating U resonators, Hong tap offset from fold, "
            "symmetric inter-resonator spacing from Qe/k)."
        ),
        stack_params=stack_params,
        electrical_params=electrical_params,
    )
    design["simulation"]["f_min"] = "f0-1.5*bw"
    design["simulation"]["f_max"] = "f0+1.5*bw"

    layout_dims: list[dict[str, Any]] = [
        {"key": "w_feed", "default": w_feed, "label": "Besleme genişliği", "unit": "mm"},
        {"key": "q_len", "default": quarter, "label": "Çeyrek dalga boyu", "unit": "mm"},
        {"key": "tap_from_fold", "default": tap, "label": "Kıvrımdan tap", "unit": "mm"},
    ]
    for k, sec in enumerate(resonators):
        layout_dims.append({"key": f"w{k}", "default": sec["width_mm"], "label": f"Rezonatör {k + 1} genişliği", "unit": "mm"})
        layout_dims.append(
            {"key": f"gap{k}", "default": sec["gap_mm"], "label": f"Rezonatör {k + 1} iç aralığı", "unit": "mm"}
        )
    for k, sp in enumerate(inter_spacing):
        layout_dims.append(
            {"key": f"sp{k}", "default": sp, "label": f"Aralık {k + 1}", "unit": "mm"}
        )
    add_tunable_layout_params(design, layout_dims)

    for k in range(n_sec):
        design["params"].append(
            {"key": f"x_base{k}", "expr": hairpin_x_base_expr(k), "label": f"Resonator {k + 1} x", "unit": "mm"}
        )
        design["params"].append(
            {
                "key": f"open_down{k}",
                "default": 1.0 if resonators[k]["open_down"] else 0.0,
                "label": f"Resonator {k + 1} open-down",
                "unit": "",
            }
        )
    design["params"].append({"key": "x_end", "expr": hairpin_x_end_expr(n_sec), "label": "Output port x", "unit": "mm"})
    design["params"].append(
        {"key": "y_feed0", "expr": hairpin_feed_y_expr(0), "label": "Input feed centre y", "unit": "mm"}
    )
    design["params"].append(
        {"key": "y_feed1", "expr": hairpin_feed_y_expr(n_sec - 1), "label": "Output feed centre y", "unit": "mm"}
    )
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
        metal_z_expr="h",
    )

    design["parts"] = [
        {
            "name": "substrate",
            "material": "substrate",
            "label": "Substrate",
            "primitives": [
                {
                    "kind": "box",
                    "priority": 0,
                    "start": [f"{x_feed0}", "-board_margin", "0"],
                    "stop": ["x_end+feed_len", "y_half", "h"],
                }
            ],
        },
        {
            "name": "gnd",
            "material": "copper",
            "label": "Ground plane",
            "primitives": [
                {
                    "kind": "box",
                    "priority": 10,
                    "start": [f"{x_feed0}", "-board_margin", "0"],
                    "stop": ["x_end+feed_len", "y_half", "0"],
                }
            ],
        },
        {"name": "filter", "material": "copper", "label": "Hairpin filter", "primitives": filter_primitives},
    ]

    design["ports"] = [
        {
            "number": 1,
            "type": "microstrip",
            "conductor": "copper",
            "dielectric": "substrate",
            "direction": "x",
            "excitation_direction": "z",
            "reference_ohm": spec.z0,
            "termination": "open",
            "excite": True,
            "feed_shift": 2,
            "measurement_shift": "feed_len/2",
            "start": [f"{x_feed0}", "y_feed0-w_feed/2", "h"],
            "stop": ["0", "y_feed0+w_feed/2", "0"],
        },
        {
            "number": 2,
            "type": "microstrip",
            "conductor": "copper",
            "dielectric": "substrate",
            "direction": "x",
            "excitation_direction": "z",
            "reference_ohm": spec.z0,
            "termination": "open",
            "excite": False,
            "feed_shift": 0,
            "measurement_shift": "feed_len/3",
            "start": ["x_end+feed_len", "y_feed1-w_feed/2", "h"],
            "stop": ["x_end", "y_feed1+w_feed/2", "0"],
        },
    ]

    dimensions = [
        {"key": dim["key"], "value": float(dim["default"]), "unit": dim.get("unit", "mm"), "label": dim.get("label", dim["key"])}
        for dim in layout_dims
    ]

    feed_eps = float(microstrip_eps_eff(spec.eps_r, spec.h_mm, w_feed))
    f_hz = np.linspace(spec.f0_hz - 1.5 * spec.bw_hz, spec.f0_hz + 1.5 * spec.bw_hz, 161)
    f_hz = np.clip(f_hz, 1e6, None)
    s_mat = coupled_line_bandpass_s(f_hz, spec.f0_hz, modal, z0=spec.z0, feed_eps=feed_eps, feed_len_mm=spec.feed_len_mm)
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
        "Layout uses alternating U resonators and a Hong tap-from-fold seed; retune sp* and tap_from_fold with full-wave EM.",
        "Intra-U gaps are a shared fold parameter; inter-resonator spacings come from adjacent k (mirrored).",
        "Preview is the ideal J-inverter coupled-line network, not an openEMS result.",
        "Bend radiation and gap fringing are not modeled in the closed-form seed.",
    ]

    return SynthesisResult(
        design=design,
        dimensions=dimensions,
        preview=preview,
        caveats=caveats,
        geometry_preview=geometry_preview,
    )
