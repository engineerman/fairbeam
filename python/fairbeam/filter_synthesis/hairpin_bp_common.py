"""Hairpin bandpass layout — alternating U + tapped feed (Hong-style rewrite).

Electrical path: g → Qe / k → inter-resonator spacings. Intra-U gaps are shared
(fold parameter). Left–right symmetry is enforced. Do not use the old MathWorks
``sections[:N]`` mapping.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from fairbeam.filter_synthesis.prototype import bandpass_j_inverters, lowpass_prototype_g
from fairbeam.filter_synthesis.types import BandwidthInfeasible

MIN_EDGE_GAP_MM_FRAC = 0.02
DEFAULT_INTRA_GAP_MM = 2.0

RESPONSE_CHEBYSHEV = "chebyshev"
RESPONSE_BUTTERWORTH = "butterworth"
RESPONSE_EQUIRIPPLE = "equiripple"
HAIRPIN_RESPONSES = (RESPONSE_CHEBYSHEV, RESPONSE_BUTTERWORTH, RESPONSE_EQUIRIPPLE)


def response_qe_ripple(response: str, ripple_db: float) -> float | None:
    """Ripple argument for ``bandpass_qe_and_k``.

    Butterworth uses the existing ``ripple_db <= 0`` path (argument 0).
    Chebyshev passes the stored passband ripple through.
    Equiripple stores its own number and must not pass that number as the
    Chebyshev argument. No equiripple Qe/k formula is defined, so this
    returns None instead of inventing one.
    """
    kind = str(response or RESPONSE_CHEBYSHEV).strip().lower()
    if kind == RESPONSE_BUTTERWORTH:
        return 0.0
    if kind == RESPONSE_CHEBYSHEV:
        return float(ripple_db)
    if kind == RESPONSE_EQUIRIPPLE:
        return None
    raise ValueError(f"unknown filter response {response!r}")


def bandpass_qe_and_k(order: int, fbw: float, ripple_db: float) -> tuple[float, float, list[float]]:
    """External Q and adjacent coupling coefficients from low-pass g and FBW."""
    if order < 1:
        raise ValueError("order must be at least 1")
    if fbw <= 0:
        raise ValueError("fbw must be positive")
    g = [1.0] + [float(x) for x in lowpass_prototype_g(order, ripple_db)]
    qe1 = g[0] * g[1] / fbw
    qen = g[order] * g[order + 1] / fbw
    ks = [fbw / math.sqrt(g[i] * g[i + 1]) for i in range(1, order)]
    return float(qe1), float(qen), ks


def modal_z_pairs(order: int, fbw: float, ripple_db: float, z0: float) -> list[tuple[float, float]]:
    """Even/odd Z from J-inverters — kept for theoretical S preview only."""
    j = bandpass_j_inverters(order, fbw, ripple_db, z0)
    return [(float(z0 * (1 + k + k * k)), float(z0 * (1 - k + k * k))) for k in j]


def k_to_even_odd(k: float, z0: float) -> tuple[float, float]:
    kk = min(max(float(k), 1e-6), 0.999)
    ze = z0 * math.sqrt((1.0 + kk) / (1.0 - kk))
    zo = z0 * math.sqrt((1.0 - kk) / (1.0 + kk))
    return float(ze), float(zo)


def hong_tap_from_fold_mm(q_len_mm: float, qe: float, z0: float, zr: float | None = None) -> float:
    """Hong / Ramdedović tap seed: t from fold toward open end (mm)."""
    zr_ohm = float(z0 if zr is None else zr)
    qe = max(float(qe), 1e-6)
    arg = math.sqrt((math.pi / 2.0) * (float(z0) / (zr_ohm * qe)))
    arg = min(max(arg, 0.0), 1.0)
    t = (2.0 * float(q_len_mm) / math.pi) * math.asin(arg)
    # High Qe → small t (near fold); keep a tiny clearance only.
    lo = max(0.25, 0.02 * float(q_len_mm))
    hi = float(q_len_mm) - lo
    return float(min(max(t, lo), hi))


def _spacing_from_k(
    k: float,
    *,
    z0: float,
    eps_r: float,
    thickness_mm: float,
    coupled_from_modal: Callable[[float, float, float, float], tuple[float, float]],
) -> float:
    ze, zo = k_to_even_odd(k, z0)
    min_gap = MIN_EDGE_GAP_MM_FRAC * thickness_mm
    try:
        _w, gap_mm = coupled_from_modal(ze, zo, eps_r, thickness_mm)
    except ValueError as exc:
        raise BandwidthInfeasible(
            "Hairpin inter-resonator coupling cannot be realized at this FBW/order; "
            f"try a wider bandwidth or lower order ({exc})."
        ) from exc
    gap_mm = float(gap_mm)
    if gap_mm < min_gap:
        raise BandwidthInfeasible(
            f"Coupling spacing {gap_mm:.4g} mm is below {MIN_EDGE_GAP_MM_FRAC:.0%} of stack thickness "
            f"({thickness_mm} mm); increase bandwidth or reduce order."
        )
    return gap_mm


def synthesize_hairpin_layout(
    *,
    order: int,
    fbw: float,
    ripple_db: float,
    z0: float,
    eps_r: float,
    thickness_mm: float,
    f0_hz: float,
    coupled_from_modal: Callable[[float, float, float, float], tuple[float, float]],
    center_width: Callable[[float, float, float], float],
    line_eps_eff: Callable[[float, float, float], float],
    intra_gap_mm: float | None = None,
    c0: float = 299_792_458.0,
    response: str = RESPONSE_CHEBYSHEV,
) -> dict[str, Any]:
    """Build symmetric alternating hairpin layout parameters (no Design JSON)."""
    qe_ripple = response_qe_ripple(response, ripple_db)
    if qe_ripple is None:
        raise ValueError(
            "Equiripple ripple is stored and is not used as Chebyshev passband ripple; "
            "no Qe/k formula is defined."
        )
    qe1, qen, ks = bandpass_qe_and_k(order, fbw, qe_ripple)
    w_line = float(center_width(z0, eps_r, thickness_mm))
    w_feed = w_line
    intra = float(DEFAULT_INTRA_GAP_MM if intra_gap_mm is None else intra_gap_mm)
    intra = max(intra, MIN_EDGE_GAP_MM_FRAC * thickness_mm)

    raw_sp = [
        _spacing_from_k(
            k,
            z0=z0,
            eps_r=eps_r,
            thickness_mm=thickness_mm,
            coupled_from_modal=coupled_from_modal,
        )
        for k in ks
    ]
    n_sp = len(raw_sp)
    inter_spacing = [0.5 * (raw_sp[i] + raw_sp[n_sp - 1 - i]) for i in range(n_sp)]

    eps_eff = float(line_eps_eff(eps_r, thickness_mm, w_line))
    q_len = float(c0 / (4.0 * f0_hz * math.sqrt(eps_eff)) * 1e3)
    tap = hong_tap_from_fold_mm(q_len, 0.5 * (qe1 + qen), z0, zr=z0)

    resonators: list[dict[str, Any]] = []
    for k in range(order):
        resonators.append(
            {
                "width_mm": w_line,
                "gap_mm": intra,
                "quarter_len_mm": q_len,
                "open_down": k % 2 == 0,
                "input_y_mm": 0.0,
            }
        )

    x_bases, x_end = hairpin_u_x_layout(resonators, inter_spacing)

    def tap_y(open_down: bool) -> float:
        return (q_len - tap) if open_down else tap

    return {
        "qe1": qe1,
        "qen": qen,
        "k": ks,
        "w_feed": w_feed,
        "q_len": q_len,
        "tap_from_fold": tap,
        "resonators": resonators,
        "inter_spacing": inter_spacing,
        "x_bases": x_bases,
        "x_end": x_end,
        "y_feed0": tap_y(resonators[0]["open_down"]),
        "y_feed1": tap_y(resonators[-1]["open_down"]),
        "eps_eff": eps_eff,
    }


def hairpin_u_x_layout(
    sections: list[dict[str, Any]],
    inter_spacing_mm: list[float] | None = None,
) -> tuple[list[float], float]:
    """X positions of U resonators: span 2w+intra_gap per U, plus inter spacings."""
    x_bases: list[float] = []
    x = 0.0
    for k, sec in enumerate(sections):
        x_bases.append(x)
        w = float(sec["width_mm"])
        gap = float(sec["gap_mm"])
        x += 2.0 * w + gap
        if inter_spacing_mm and k < len(inter_spacing_mm):
            x += float(inter_spacing_mm[k])
    return x_bases, x


def hairpin_filter_primitives(
    sections: list[dict[str, Any]],
    *,
    x_feed0: float,
    feed_len: float,
    x_end: float,
    w_feed: float,
    metal_z_expr: str,
) -> list[dict[str, Any]]:
    """Plan-view alternating hairpins with feeds at y_feed0 / y_feed1 (tap height)."""
    # Numeric x_end / w_feed / feed_len seed the caller; geometry uses param expressions.
    _ = (x_end, w_feed, feed_len)
    out: list[dict[str, Any]] = []
    out.append(
        {
            "kind": "box",
            "priority": 10,
            "start": [f"{x_feed0}", "y_feed0-w_feed/2", metal_z_expr],
            "stop": ["0", "y_feed0+w_feed/2", metal_z_expr],
        }
    )
    for k, sec in enumerate(sections):
        open_down = bool(sec.get("open_down", k % 2 == 0))
        x0 = f"x_base{k}"
        w_k = f"w{k}"
        gap_k = f"gap{k}"
        if open_down:
            out.append(
                {
                    "kind": "box",
                    "priority": 10,
                    "start": [x0, "0", metal_z_expr],
                    "stop": [f"{x0}+{w_k}", f"q_len-{w_k}", metal_z_expr],
                }
            )
            out.append(
                {
                    "kind": "box",
                    "priority": 10,
                    "start": [f"{x0}+{w_k}+{gap_k}", "0", metal_z_expr],
                    "stop": [f"{x0}+2*{w_k}+{gap_k}", f"q_len-{w_k}", metal_z_expr],
                }
            )
            out.append(
                {
                    "kind": "box",
                    "priority": 10,
                    "start": [x0, f"q_len-{w_k}", metal_z_expr],
                    "stop": [f"{x0}+2*{w_k}+{gap_k}", "q_len", metal_z_expr],
                }
            )
        else:
            out.append(
                {
                    "kind": "box",
                    "priority": 10,
                    "start": [x0, "0", metal_z_expr],
                    "stop": [f"{x0}+2*{w_k}+{gap_k}", w_k, metal_z_expr],
                }
            )
            out.append(
                {
                    "kind": "box",
                    "priority": 10,
                    "start": [x0, w_k, metal_z_expr],
                    "stop": [f"{x0}+{w_k}", "q_len", metal_z_expr],
                }
            )
            out.append(
                {
                    "kind": "box",
                    "priority": 10,
                    "start": [f"{x0}+{w_k}+{gap_k}", w_k, metal_z_expr],
                    "stop": [f"{x0}+2*{w_k}+{gap_k}", "q_len", metal_z_expr],
                }
            )
    out.append(
        {
            "kind": "box",
            "priority": 10,
            "start": ["x_end", "y_feed1-w_feed/2", metal_z_expr],
            "stop": ["x_end+feed_len", "y_feed1+w_feed/2", metal_z_expr],
        }
    )
    return out
