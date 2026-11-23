"""Unit tests for Douville–James hairpin fold miters (issue engineerman/fairbeam#2)."""

from __future__ import annotations

import math
import unittest

from fairbeam.filter_synthesis.hairpin_miter import (
    MIN_W_OVER_H,
    douville_james_edge_chamfer_mm,
    douville_james_miter_fraction,
    hairpin_u_outer_xy,
)


class DouvilleJamesMiterTests(unittest.TestCase):
    def test_fraction_at_w_over_h_one(self) -> None:
        # 0.52 + 0.65*exp(-1.35) ≈ 0.6885
        m = douville_james_miter_fraction(1.0)
        self.assertAlmostEqual(m, 0.52 + 0.65 * math.exp(-1.35), places=6)

    def test_fraction_clamps_below_min_wh(self) -> None:
        at_min = douville_james_miter_fraction(MIN_W_OVER_H)
        below = douville_james_miter_fraction(0.1)
        self.assertAlmostEqual(below, at_min, places=12)

    def test_edge_chamfer_is_m_times_w(self) -> None:
        w, h = 3.0, 1.6
        m = douville_james_miter_fraction(w / h)
        self.assertAlmostEqual(douville_james_edge_chamfer_mm(w, h), m * w, places=9)

    def test_rejects_non_positive(self) -> None:
        with self.assertRaises(ValueError):
            douville_james_miter_fraction(0.0)
        with self.assertRaises(ValueError):
            douville_james_edge_chamfer_mm(-1.0, 1.0)


class HairpinUOuterXyTests(unittest.TestCase):
    def test_square_open_down_has_eight_corners(self) -> None:
        pts = hairpin_u_outer_xy(
            x0=0.0, w=2.0, gap=1.0, q_len=10.0, open_down=True, chamfer=0.0
        )
        self.assertEqual(len(pts), 8)
        self.assertEqual(pts[0], [0.0, 0.0])
        self.assertEqual(pts[-1], [0.0, 10.0])
        self.assertEqual(pts[-2], [5.0, 10.0])  # x_right = 2*2+1

    def test_mitered_open_down_replaces_outer_fold_corners(self) -> None:
        a = 0.5
        pts = hairpin_u_outer_xy(
            x0=0.0, w=2.0, gap=1.0, q_len=10.0, open_down=True, chamfer=a
        )
        self.assertEqual(len(pts), 10)
        # Last four points are the chamfered fold (right then left).
        self.assertEqual(pts[-4], [5.0, 10.0 - a])
        self.assertEqual(pts[-3], [5.0 - a, 10.0])
        self.assertEqual(pts[-2], [a, 10.0])
        self.assertEqual(pts[-1], [0.0, 10.0 - a])
        # Outer square corners must be gone.
        self.assertNotIn([0.0, 10.0], pts)
        self.assertNotIn([5.0, 10.0], pts)

    def test_chamfer_must_be_less_than_w(self) -> None:
        with self.assertRaises(ValueError):
            hairpin_u_outer_xy(
                x0=0.0, w=2.0, gap=1.0, q_len=10.0, open_down=True, chamfer=2.0
            )


if __name__ == "__main__":
    unittest.main()
