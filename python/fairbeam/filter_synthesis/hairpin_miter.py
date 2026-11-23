"""Douville–James miters for hairpin U fold corners.

Empirical optimum 90° microstrip mitre (independent of εr) from
R. J. P. Douville and D. S. James, IEEE Trans. MTT, vol. MTT-26, no. 3,
pp. 175–181, Mar. 1978. Valid for W/h ≥ 0.25 and εr ≤ 25 (εr is not an
input here; callers should enforce the εr bound if they care).

``fold_style`` values used by ``hairpin_filter_primitives``:

- ``square`` — three axis-aligned boxes (legacy)
- ``mitered`` — same U outline with Douville–James outer-corner chamfers
"""

from __future__ import annotations

import math
from typing import Literal

FoldStyle = Literal["square", "mitered"]

# Measured fit range (Wikipedia / Douville–James).
MIN_W_OVER_H = 0.25
MAX_W_OVER_H = 2.75


def douville_james_miter_fraction(w_over_h: float) -> float:
    """Return the cut-away fraction of the outer-to-inner corner diagonal (0…1).

    M/100 in Douville–James / Wikipedia notation:
    ``M = 52 + 65·exp(−1.35·W/h)`` percent of the diagonal.
    """
    if not math.isfinite(w_over_h) or w_over_h <= 0:
        raise ValueError("w_over_h must be finite and > 0")
    x = max(float(w_over_h), MIN_W_OVER_H)
    return 0.52 + 0.65 * math.exp(-1.35 * x)


def douville_james_edge_chamfer_mm(w_mm: float, h_mm: float) -> float:
    """Chamfer length along each outer edge from the unmitered outer corner (mm).

    With diagonal ``d = W·√2`` and cut depth ``x = m·d`` from the outer corner
    along that diagonal, the hit on each outer edge is ``a = x/√2 = m·W``.
    """
    if not math.isfinite(w_mm) or w_mm <= 0:
        raise ValueError("w_mm must be finite and > 0")
    if not math.isfinite(h_mm) or h_mm <= 0:
        raise ValueError("h_mm must be finite and > 0")
    m = douville_james_miter_fraction(w_mm / h_mm)
    return m * w_mm


def hairpin_u_outer_xy(
    *,
    x0: float,
    w: float,
    gap: float,
    q_len: float,
    open_down: bool,
    chamfer: float,
) -> list[list[float]]:
    """Closed plan-view ring (mm) for one U with optional outer-fold chamfers.

    ``chamfer == 0`` keeps square outer fold corners. ``chamfer > 0`` applies the
    same length on both outer fold corners (left and right). The ring is suitable
    as a ``polygon`` / ``linpoly`` point list with normal ``z``.
    """
    if w <= 0 or gap < 0 or q_len <= w:
        raise ValueError("need w > 0, gap >= 0, and q_len > w")
    if chamfer < 0 or chamfer >= w:
        raise ValueError("chamfer must satisfy 0 <= chamfer < w")

    x_left = x0
    x_left_inner = x0 + w
    x_right_inner = x0 + w + gap
    x_right = x0 + 2.0 * w + gap
    a = float(chamfer)

    if open_down:
        # Open at y=0; fold along y = q_len.
        y_open = 0.0
        y_fold_inner = q_len - w
        y_fold = q_len
        pts: list[list[float]] = [
            [x_left, y_open],
            [x_left_inner, y_open],
            [x_left_inner, y_fold_inner],
            [x_right_inner, y_fold_inner],
            [x_right_inner, y_open],
            [x_right, y_open],
        ]
        if a == 0.0:
            pts.extend([[x_right, y_fold], [x_left, y_fold]])
        else:
            pts.extend(
                [
                    [x_right, y_fold - a],
                    [x_right - a, y_fold],
                    [x_left + a, y_fold],
                    [x_left, y_fold - a],
                ]
            )
        return pts

    # Open at y = q_len; fold along y = 0.
    y_open = q_len
    y_fold_inner = w
    y_fold = 0.0
    pts = [
        [x_left, y_open],
        [x_left_inner, y_open],
        [x_left_inner, y_fold_inner],
        [x_right_inner, y_fold_inner],
        [x_right_inner, y_open],
        [x_right, y_open],
    ]
    if a == 0.0:
        pts.extend([[x_right, y_fold], [x_left, y_fold]])
    else:
        pts.extend(
            [
                [x_right, y_fold + a],
                [x_right - a, y_fold],
                [x_left + a, y_fold],
                [x_left, y_fold + a],
            ]
        )
    return pts
