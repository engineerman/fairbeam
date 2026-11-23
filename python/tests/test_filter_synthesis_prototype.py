import unittest

import numpy as np

from fairbeam import analytic
from fairbeam.filter_synthesis.preview import two_port_preview
from fairbeam.filter_synthesis.prototype import bandpass_j_inverters, lowpass_prototype_g


class FilterSynthesisPrototypeTests(unittest.TestCase):
    def test_lowpass_prototype_butterworth_n3(self):
        g = lowpass_prototype_g(3, 0.0)
        expect = analytic.lowpass_prototype(3, 0.0)
        self.assertEqual(len(g), len(expect))
        np.testing.assert_allclose(g, expect, rtol=0, atol=0)

    def test_bandpass_j_inverters_coupled_fixture(self):
        from tests.coupled_line_filter_fixture import FBW, ORDER, RIPPLE_DB, prototype

        g = prototype()
        expect = np.r_[
            np.sqrt(np.pi * FBW / (2 * g[0] * g[1])),
            np.pi * FBW / (2 * np.sqrt(g[1:-2] * g[2:-1])),
            np.sqrt(np.pi * FBW / (2 * g[-2] * g[-1])),
        ]
        expect = expect.copy()
        expect[2:] = expect[1::-1]

        got = bandpass_j_inverters(ORDER, FBW, RIPPLE_DB, 50.0)
        np.testing.assert_allclose(got, expect, rtol=1e-4, atol=1e-6)
        self.assertEqual(len(got), len(expect))

    def test_two_port_preview_from_cascade_lines(self):
        f_hz = np.linspace(1.5e9, 2.5e9, 51)
        sections = [{"z": 50.0, "eps_eff": 2.2, "length": 2.0}]
        s = analytic.cascade_lines_s(f_hz, sections, z0=50.0)
        out = two_port_preview(f_hz, s)
        self.assertEqual(len(out["s21_db"]), len(f_hz))
        self.assertEqual(len(out["s11_db"]), len(f_hz))
        self.assertEqual(len(out["s21_group_delay_ns"]), len(f_hz))
        self.assertEqual(out["f_hz"], f_hz.tolist())
        self.assertTrue(np.all(np.isfinite(out["s21_group_delay_ns"])))


if __name__ == "__main__":
    unittest.main()
