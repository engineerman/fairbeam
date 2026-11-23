"""Homogeneous centered thin-PEC stripline conformal-map helpers (Cohn / coupled_line_filter_fixture)."""

from __future__ import annotations

import numpy as np
from openEMS.physical_constants import Z0 as ETA0

from fairbeam.analytic import C0


def _agm(a: float, b: float) -> float:
    for _ in range(32):
        a, b = (a + b) / 2, np.sqrt(a * b)
    return a


def mode_impedance(k: float, eps_r: float) -> float:
    """Even-mode characteristic impedance for elliptic modulus ``k`` in (0, 1)."""
    k = float(k)
    if not np.isfinite(k) or k <= 0 or k >= 1:
        raise ValueError("elliptic modulus strictly between zero and one required")
    return float(ETA0 / (4 * np.sqrt(eps_r)) * _agm(1.0, np.sqrt(1 - k * k)) / _agm(1.0, k))


def modulus_from_impedance(z_ohm: float, eps_r: float) -> float:
    if not np.isfinite(z_ohm) or z_ohm <= 0:
        raise ValueError("positive modal impedance required")
    lo, hi = 1e-12, 1 - 1e-12
    for _ in range(64):
        mid = (lo + hi) / 2
        if mode_impedance(mid, eps_r) > z_ohm:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def stripline_coupled_from_modal(z_even: float, z_odd: float, eps_r: float, b_mm: float) -> tuple[float, float]:
    """Strip width and edge gap for target even/odd modal impedances (Rogers Cohn map)."""
    if b_mm <= 0:
        raise ValueError("positive ground separation required")
    ke = modulus_from_impedance(z_even, eps_r)
    ko = modulus_from_impedance(z_odd, eps_r)
    u = float(np.arctanh(np.sqrt(ke * ko)))
    v = float(np.arctanh(np.sqrt(ke / ko)))
    width_mm = float(2 * b_mm * u / np.pi)
    gap_mm = float(2 * b_mm * (v - u) / np.pi)
    if width_mm <= 0 or gap_mm <= 0:
        raise ValueError("non-positive strip width or gap from modal targets")
    return width_mm, gap_mm


def stripline_center_width(z0: float, eps_r: float, b_mm: float) -> float:
    k = modulus_from_impedance(z0, eps_r)
    return float(2 * b_mm * np.arctanh(k) / np.pi)


def stripline_coupled_impedances(width_mm: float, gap_mm: float, eps_r: float, b_mm: float) -> dict[str, float]:
    if min(width_mm, gap_mm) <= 0:
        raise ValueError("positive finite strip width and gap required")
    a = float(np.tanh(np.pi * width_mm / (2 * b_mm)))
    b = float(np.tanh(np.pi * (width_mm + gap_mm) / (2 * b_mm)))
    ze, zo = mode_impedance(a * b, eps_r), mode_impedance(a / b, eps_r)
    return {"z_even": ze, "z_odd": zo}


def stripline_quarter_length_mm(f0_hz: float, eps_r: float) -> float:
    return float(C0 / (4 * f0_hz * np.sqrt(eps_r)) * 1e3)
