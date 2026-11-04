"""EMerge driven shared Results bundle; EMerge is never imported or run here."""
import ast
import copy
import unittest
from pathlib import Path

from fairbeam.design import blank_design
from fairbeam.emerge_bundle import result_bundle

NATIVE = "exp(+i omega t)"


def settings(**over):
    s = dict(analysis="driven", accept_finite_feed=True, feed_width_mm=1., padding_mm=40.,
             resolution="coarse", f_min_hz=2e9, f_max_hz=3e9, points=3)
    s.update(over)
    return s


def synthetic_result(**over):
    value = dict(
        schema="fairbeam.emerge-driven-result/1", status="results_exported",
        precision_converged=False, gain_qualified=False, settings=settings(),
        limitations=["Experimental"], pec_approximations=[],
        frequency_hz=[2e9, 2.5e9, 3e9], s11_re=[0., .2, 0.], s11_im=[.1, 0., -.1],
        z_ref=50., phasor_convention=NATIVE, native_phasor_convention=NATIVE,
        mesh={"nodes": 100, "tetrahedra": 400})
    value.update(over)
    return value


class EmergeBundle(unittest.TestCase):
    def test_preserves_design_run_none_no_conjugation_zin_and_empty_farfield(self):
        design = blank_design("p", "Patch")
        original = copy.deepcopy(design)
        bundle = result_bundle(design, synthetic_result())
        self.assertEqual(design, original)
        self.assertEqual(bundle["model"]["id"], "p")
        self.assertIsNone(bundle["run"])
        self.assertEqual(bundle["solver"]["engine"], "EMerge")
        self.assertEqual(bundle["solver"]["boundaries"]["x+"], "Second-order absorbing")
        self.assertNotIn("preview", bundle)
        self.assertEqual(bundle["results"]["farfield"], [])
        # Native S11 kept (Elmer would conjugate imag).
        self.assertEqual(bundle["results"]["ports"]["1"]["s11_im"], [.1, 0., -.1])
        self.assertEqual(bundle["results"]["ports"]["1"]["s11_re"], [0., .2, 0.])
        self.assertAlmostEqual(bundle["results"]["ports"]["1"]["zin_re"][1], 75.)
        self.assertEqual(bundle["ports"][0]["stop"][0] - bundle["ports"][0]["start"][0], 1.)
        self.assertIn("not conjugated", bundle["experimental"]["phasor_convention"])
        self.assertFalse(bundle["experimental"]["precision_converged"])

    def test_singular_impedance_is_rejected(self):
        design = blank_design("p", "Patch")
        with self.assertRaisesRegex(ValueError, "singular"):
            result_bundle(design, synthetic_result(s11_re=[1., 1., 1.], s11_im=[0., 0., 0.]))

    def test_module_does_not_import_emerge(self):
        source = (Path(__file__).resolve().parents[1] / "fairbeam" / "emerge_bundle.py").read_text(
            encoding="utf-8")
        tree = ast.parse(source)
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module.split(".")[0])
        self.assertNotIn("emerge", names)
        self.assertNotIn("gmsh", names)
        self.assertNotIn("emsutil", names)


if __name__ == "__main__":
    unittest.main()
