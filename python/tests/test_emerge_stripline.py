import ast
import copy
import math
import sys
import unittest
from pathlib import Path

from fairbeam import emerge_stripline
from fairbeam.emerge_planar import METAL_EDGE_MM
from fairbeam.emerge_stripline import admit
from fairbeam.filter_synthesis.hairpin_stripline_bp import (
    HairpinStriplineBpSpec,
    synthesize_hairpin_stripline_bp,
)


def tearDownModule():
    if "emerge" in sys.modules:
        raise AssertionError("emerge is in sys.modules after stripline admit tests")


def settings(**over):
    s = dict(analysis="emerge_nport", accept_finite_feed=True, padding_mm=5.0,
             resolution="coarse", f_min_hz=1.7e9, f_max_hz=2.3e9, points=5)
    s.update(over)
    return s


def _set_filter_elevation(design, z_expr):
    for part in design["parts"]:
        if part.get("name") != "filter":
            continue
        for prim in part["primitives"]:
            if prim.get("kind") == "box":
                prim["start"][2] = z_expr
                prim["stop"][2] = z_expr
            elif prim.get("kind") == "polygon":
                prim["elevation"] = z_expr


def _drop_part(design, name):
    design["parts"] = [p for p in design["parts"] if p.get("name") != name]


class TestStriplineAdmit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = HairpinStriplineBpSpec(f0_hz=2e9, order=3, bw_hz=0.2e9)
        cls.base = synthesize_hairpin_stripline_bp(spec).design

    def hairpin(self):
        return copy.deepcopy(self.base)

    def test_hairpin_admits(self):
        raw = self.hairpin()
        snapshot = copy.deepcopy(raw)
        case = admit(raw, settings())
        self.assertEqual(raw, snapshot)
        self.assertEqual(case["kind"], "stripline")
        self.assertEqual(case["phasor_convention_out"], "exp(+i omega t)")
        self.assertEqual(case["resolution"], 0.25)
        self.assertEqual(case["resolution_name"], "coarse")
        self.assertEqual(case["frequencies_hz"][0], 1.7e9)
        self.assertEqual(case["frequencies_hz"][-1], 2.3e9)
        self.assertEqual(len(case["frequencies_hz"]), 5)
        self.assertAlmostEqual(case["metal_edge_m"], METAL_EDGE_MM * 1e-3)
        self.assertAlmostEqual(case["padding_m"], 0.005)

        strip_z = case["traces"][0]["z"]
        self.assertEqual(strip_z, 0.0)
        self.assertTrue(all(t["z"] == strip_z for t in case["traces"]))
        bottom = case["grounds"]["bottom_z"]
        top = case["grounds"]["top_z"]
        self.assertLess(bottom, strip_z)
        self.assertLess(strip_z, top)
        self.assertAlmostEqual(bottom, case["substrate"]["lo"][2])
        self.assertAlmostEqual(top, case["substrate"]["hi"][2])

        pad = case["padding_m"]
        self.assertAlmostEqual(case["air"]["lo"][0], case["substrate"]["lo"][0] - pad)
        self.assertAlmostEqual(case["air"]["hi"][0], case["substrate"]["hi"][0] + pad)
        self.assertAlmostEqual(case["air"]["lo"][1], case["substrate"]["lo"][1] - pad)
        self.assertAlmostEqual(case["air"]["hi"][1], case["substrate"]["hi"][1] + pad)
        self.assertAlmostEqual(case["air"]["lo"][2], case["substrate"]["lo"][2])
        self.assertAlmostEqual(case["air"]["hi"][2], case["substrate"]["hi"][2])

        text = " ".join(case["limitations"])
        for phrase in ("ground separation", "enclosure", "air_height_mm", "padding_mm", "PEC", "far field"):
            self.assertIn(phrase, text)

        self.assertGreaterEqual(len(case["terminals"]), 1)
        for term in case["terminals"]:
            self.assertEqual(term["mapped_bc"], "LumpedPort")
            z0, z1 = term["lo"][2], term["hi"][2]
            self.assertTrue(math.isclose(z0, strip_z) or math.isclose(z1, strip_z))
            meets_bottom = math.isclose(z0, bottom) or math.isclose(z1, bottom)
            meets_top = math.isclose(z0, top) or math.isclose(z1, top)
            self.assertTrue(meets_bottom or meets_top)
            self.assertFalse(meets_bottom and meets_top)

    def test_microstrip_board_rejected(self):
        design = self.hairpin()
        _drop_part(design, "gnd_top")
        _set_filter_elevation(design, "b/2")
        with self.assertRaises(ValueError):
            admit(design, settings())

    def test_missing_top_ground_rejected(self):
        design = self.hairpin()
        _drop_part(design, "gnd_top")
        with self.assertRaises(ValueError):
            admit(design, settings())

    def test_strip_on_top_ground_rejected(self):
        design = self.hairpin()
        _set_filter_elevation(design, "b/2")
        with self.assertRaises(ValueError):
            admit(design, settings())

    def test_port_spanning_both_grounds_rejected(self):
        design = self.hairpin()
        for port in design["ports"]:
            port["stop"][2] = "b/2"
        with self.assertRaises(ValueError):
            admit(design, settings())

    def test_unknown_settings_rejected(self):
        for key, value in (("enclosure", "open"), ("air_height_mm", 4.0)):
            with self.subTest(key=key):
                s = settings()
                s[key] = value
                with self.assertRaises(ValueError):
                    admit(self.hairpin(), s)

    def test_huge_padding_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Domain too large"):
            admit(self.hairpin(), settings(padding_mm=100000, f_min_hz=1e9, f_max_hz=1e11))

    def test_emerge_not_in_sys_modules(self):
        source = Path(emerge_stripline.__file__).read_text(encoding="utf-8")
        found = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                found.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
        self.assertFalse(found & {"emerge", "gmsh", "emsutil"}, found)
        self.assertNotIn("emerge", sys.modules)
        self.assertIn("fairbeam.emerge_stripline", sys.modules)
