"""Theoretical two-port S-parameter previews for the filter designer."""

from __future__ import annotations

import numpy as np

from fairbeam.analytic import C0


def _as_db(linear: np.ndarray) -> np.ndarray:
    return 20.0 * np.log10(np.maximum(np.abs(linear), 1e-30))


def _as_deg(phasor: np.ndarray) -> np.ndarray:
    return np.degrees(np.angle(phasor))


def coupled_line_bandpass_s(
    f_hz,
    f0_hz: float,
    modal_pairs: list[tuple[float, float]],
    z0: float = 50.0,
    feed_eps: float = 1.0,
    feed_len_mm: float = 6.0,
    unit: float = 1e-3,
) -> np.ndarray:
    """Ideal quarter-wave coupled-line BPF S-matrix (Pozar / coupled_line_filter_fixture ``reference``)."""
    f = np.asarray(f_hz, float)
    theta = np.pi * f / (2.0 * f0_hz)
    total = np.broadcast_to(np.eye(2, dtype=complex), (len(f), 2, 2)).copy()
    for ze, zo in modal_pairs:
        diagonal = -1j * (ze + zo) / (2 * np.tan(theta))
        cross = -1j * (ze - zo) / (2 * np.sin(theta))
        block = np.empty_like(total)
        block[:, 0, 0] = block[:, 1, 1] = diagonal / cross
        block[:, 0, 1] = (diagonal**2 - cross**2) / cross
        block[:, 1, 0] = 1 / cross
        total = total @ block
    beta = 2 * np.pi * f * np.sqrt(max(feed_eps, 1.0)) / C0 * unit
    theta_feed = beta * feed_len_mm
    feed = np.empty_like(total)
    feed[:, 0, 0] = feed[:, 1, 1] = np.cos(theta_feed)
    feed[:, 0, 1] = 1j * z0 * np.sin(theta_feed)
    feed[:, 1, 0] = 1j * np.sin(theta_feed) / z0
    t = feed @ total @ feed
    a, b, c, d = (t[:, i, j] for i, j in ((0, 0), (0, 1), (1, 0), (1, 1)))
    den = a + b / z0 + c * z0 + d
    s = np.empty_like(total)
    s[:, 0, 0] = (a + b / z0 - c * z0 - d) / den
    s[:, 1, 1] = (-a + b / z0 - c * z0 + d) / den
    s[:, 0, 1] = s[:, 1, 0] = 2 / den
    return s


def two_port_preview(f_hz, network) -> dict[str, list[float]]:
    """Build magnitude, phase, and group-delay curves from a two-port S-matrix vs frequency.

    ``network`` is either shape ``(n_f, 2, 2)`` or a single ``(2, 2)`` matrix broadcast over ``f_hz``.
    """
    f = np.asarray(f_hz, float)
    if f.ndim != 1 or f.size < 2:
        raise ValueError("f_hz must be a 1-D array with at least two samples")
    s = np.asarray(network, dtype=complex)
    if s.ndim == 2:
        if s.shape != (2, 2):
            raise ValueError("network must have shape (2, 2) or (n_f, 2, 2)")
        s = np.broadcast_to(s, (f.size, 2, 2)).copy()
    elif s.ndim != 3 or s.shape[1:] != (2, 2):
        raise ValueError("network must have shape (2, 2) or (n_f, 2, 2)")
    if s.shape[0] != f.size:
        raise ValueError("network frequency count must match f_hz")

    s11 = s[:, 0, 0]
    s21 = s[:, 1, 0]
    phase21 = np.unwrap(np.angle(s21))
    omega = 2.0 * np.pi * f
    group_delay_s = -np.gradient(phase21, omega)
    group_delay_ns = group_delay_s * 1e9

    return {
        "f_hz": f.tolist(),
        "s11_db": _as_db(s11).tolist(),
        "s21_db": _as_db(s21).tolist(),
        "s11_deg": _as_deg(s11).tolist(),
        "s21_deg": _as_deg(s21).tolist(),
        "s21_group_delay_ns": group_delay_ns.tolist(),
    }
