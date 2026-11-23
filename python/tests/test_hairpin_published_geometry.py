"""Published Hong 2001 hairpin layout against the closed-form builder. No synthesis edits."""

import unittest

from fairbeam.filter_synthesis.hairpin.verification.hong_2001 import comparison_rows


def _by_name(rows):
    return {row["name"]: row for row in rows}


class Hong2001ClosedFormComparison(unittest.TestCase):
    def test_feed_width_matches_and_em_gaps_do_not(self):
        rows = _by_name(comparison_rows())
        feed = rows["50 ohm feed width"]
        self.assertLess(abs(feed["delta_mm"]), 0.05)
        formula = rows["equation (5.26) with Hong's L, Zr, Qe"]
        self.assertLess(abs(formula["delta_mm"]), 0.01)
        width = rows["line width at Hong's Zr"]
        self.assertLess(abs(width["delta_mm"]), 0.01)
        arm = rows["resonator width"]
        self.assertGreater(arm["designed_mm"], 1.5)
        self.assertGreater(abs(rows["outer coupling gap"]["delta_mm"]), 0.2)
        self.assertGreater(abs(rows["tap vs EM curve"]["delta_mm"]), 1.0)
        self.assertEqual(rows["U arm gap"]["delta_mm"], 0.0)
