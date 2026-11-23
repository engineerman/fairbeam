"""Lumped prototype values and bandpass J-inverter extraction."""

from __future__ import annotations

import numpy as np
from openEMS.physical_constants import C0

from fairbeam import analytic
from fairbeam.filter_synthesis.stripline import stripline_center_width


def lowpass_prototype_g(n: int, ripple_db: float = 0.0) -> list[float]:
    """Normalized low-pass prototype g_1 … g_{n+1} (Pozar); thin wrapper over ``analytic``."""
    return analytic.lowpass_prototype(n, ripple_db)


def bandpass_j_inverters(order: int, fbw: float, ripple_db: float, z0: float = 50.0) -> np.ndarray:
    """Admittance inverters J for a coupled-line bandpass (Pozar / coupled_line_filter_fixture).

    ``fbw`` is the fractional bandwidth (Δf/f₀). ``z0`` is reserved for later modal-Z helpers.
    """
    del z0  # API parity with design builders; J values are independent of port Z₀.
    if order < 1:
        raise ValueError("order must be at least 1")
    if fbw <= 0:
        raise ValueError("fbw must be positive")
    g = np.r_[1.0, lowpass_prototype_g(order, ripple_db)]
    j = np.r_[
        np.sqrt(np.pi * fbw / (2 * g[0] * g[1])),
        np.pi * fbw / (2 * np.sqrt(g[1:-2] * g[2:-1])),
        np.sqrt(np.pi * fbw / (2 * g[-2] * g[-1])),
    ]
    if len(j) > 2:
        j = j.copy()
        n = len(j)
        for i in range((n + 1) // 2, n):
            j[i] = j[n - 1 - i]
    return np.asarray(j, float)


def stepped_impedance_lowpass_stripline(
    fc: float,
    n: int,
    ripple_db: float,
    z0: float,
    z_high: float,
    z_low: float,
    eps_r: float,
    b_mm: float,
    unit: float = 1e-3,
    first: str = "C",
) -> list[dict]:
    """Stepped-impedance stripline low-pass: same g and beta*l as Pozar microstrip, stripline widths."""
    g = lowpass_prototype_g(n, ripple_db)[:n]
    out: list[dict] = []
    for k, gk in enumerate(g):
        is_c = (k % 2 == 0) == (first == "C")
        z = z_low if is_c else z_high
        bl = gk * z_low / z0 if is_c else gk * z0 / z_high
        w = float(stripline_center_width(z, eps_r, b_mm))
        e = float(eps_r)
        length = bl / (2 * np.pi * fc * np.sqrt(e) / C0) / unit
        out.append(
            {
                "kind": "C" if is_c else "L",
                "g": float(gk),
                "z": float(z),
                "width": w,
                "eps_eff": e,
                "beta_l": float(bl),
                "length": float(length),
            }
        )
    return out
