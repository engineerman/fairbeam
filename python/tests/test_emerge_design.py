import ast
import copy
import math
import unittest
from pathlib import Path

from fairbeam import elmer_driven, emerge_design
from fairbeam.design import blank_design
from fairbeam.emerge_design import admit

C0 = 299792458.0


def settings(**over):
    s = dict(analysis="driven", accept_finite_feed=True, feed_width_mm=1., padding_mm=40.,
             resolution="coarse", f_min_hz=2e9, f_max_hz=3e9, points=5)
    s.update(over)
    return s


def patch():
    return blank_design("p", "Patch")


def part(d, name):
    return next(p for p in d["parts"] if p["name"] == name)


def box(start, stop):
    return {"kind": "box", "start": start, "stop": stop}


def second_dielectric(d, start, stop):
    d["parts"].append({"name": "extra", "material": "substrate", "label": "Extra", "primitives": [box(start, stop)]})


def conductive(d):
    next(m for m in d["materials"] if m["kind"] == "metal").update(conductivity=5.8e7, thickness=.035)


def two_ports(d):
    d["ports"].append({**copy.deepcopy(d["ports"][0]), "number": 2})


def resistor(d):
    d["resistors"] = [{"name": "r1", "R": "100", "start": ["0", "0", "0"], "stop": ["0", "0", "h"], "direction": "z"}]


def lumped_element(d):
    d["lumped_elements"] = [{"name": "c1", "type": "C", "value": "1e-12"}]


def transform(d):
    part(d, "patch")["transforms"] = [{"type": "translate", "copies": 1, "step": [0, 50, 0]}]


def cut(d):
    part(d, "patch")["cuts"] = [{"start": [-1, -1, "h"], "stop": [1, 1, "h"]}]


def curved(d):
    part(d, "patch")["primitives"] = [{"kind": "cylinder", "axis": "z", "center": [0, 0], "radius": 5,
                                       "range": ["h", "h"]}]


def rotated(d):
    part(d, "patch")["transforms"] = [{"type": "rotate", "axis": "z", "center": [0, 0, 0], "angle": 45, "copies": 0}]


def metal_volume(d):
    part(d, "patch")["primitives"] = [box(["-W/2", "-L/2", "h"], ["W/2", "L/2", "h+1"])]


def flat_dielectric(d):
    part(d, "substrate")["primitives"] = [box(["-G/2", "-G/2", "0"], ["G/2", "G/2", "0"])]


def overlap(d):
    second_dielectric(d, ["-10", "-10", "0"], ["10", "10", "h"])


def no_tan_d_freq(d):
    next(m for m in d["materials"] if m["kind"] == "dielectric").pop("tan_d_freq")


def feed_floats(d):
    d["ports"][0]["stop"][2] = "h/2"


def crossing_sheet(d):
    d["parts"].append({"name": "mid", "material": "copper", "label": "Mid",
                       "primitives": [box(["-G/2", "-G/2", "h/2"], ["G/2", "G/2", "h/2"])]})


def real_feed(d):
    d["ports"][0]["start"][1] = "1"


def reactive(d):
    d["ports"][0]["X"] = 5


def unknown_port_key(d):
    d["ports"][0]["extra"] = 1


def unknown_material_key(d):
    next(m for m in d["materials"] if m["kind"] == "dielectric")["anisotropy"] = 1


def not_excited(d):
    d["ports"][0]["excite"] = False


def edge_feed(d):
    d["ports"][0]["start"][0] = "G/2 + 1"
    d["ports"][0]["stop"][0] = "G/2 + 1"


class AdmitTests(unittest.TestCase):
    def test_patch_is_admitted_in_metres_with_the_documented_shape(self):
        case = admit(patch(), settings())
        self.assertEqual(case["kind"], "design")
        self.assertEqual(len(case["boxes"]), 1)
        self.assertEqual(len(case["sheets"]), 2)
        box_ = case["boxes"][0]
        self.assertEqual(set(box_), {"lo", "hi", "eps_r", "mu_r", "tan_d"})
        self.assertEqual((box_["eps_r"], box_["mu_r"], box_["tan_d"]), (3.38, 1., .0027))
        for got, want in zip(box_["lo"], (-.03, -.03, 0.)):
            self.assertAlmostEqual(got, want, places=12)
        for got, want in zip(box_["hi"], (.03, .03, .001524)):
            self.assertAlmostEqual(got, want, places=12)
        self.assertEqual(sorted(s["normal_axis"] for s in case["sheets"]), [2, 2])
        self.assertEqual(set(case["sheets"][0]), {"lo", "hi", "normal_axis"})
        self.assertEqual(set(case["port"]), {"lo", "hi", "direction_axis", "sign", "width", "height", "z0"})
        self.assertEqual(case["frequencies_hz"][0], 2e9)
        self.assertEqual(case["frequencies_hz"][-1], 3e9)
        self.assertEqual(len(case["frequencies_hz"]), 5)
        self.assertAlmostEqual(case["frequencies_hz"][1], 2.25e9)
        self.assertEqual(case["resolution"], .25)
        self.assertEqual(case["phasor_convention_out"], "exp(+i omega t)")
        self.assertEqual(case["pec_approximations"], [])
        self.assertTrue(any("constant loss tangent" in t.lower() for t in case["limitations"]))
        self.assertEqual(admit(patch(), settings(resolution="fine"))["resolution"], .15)

    def test_air_box_is_bounding_box_plus_padding(self):
        case = admit(patch(), settings(padding_mm=25))
        for got, want in zip(case["air"]["lo"], (-.055, -.055, -.025)):
            self.assertAlmostEqual(got, want, places=12)
        for got, want in zip(case["air"]["hi"], (.055, .055, .026524)):
            self.assertAlmostEqual(got, want, places=12)

    def test_feed_width_is_applied_on_the_transverse_axis_not_the_gap(self):
        case = admit(patch(), settings(feed_width_mm=3))
        port = case["port"]
        self.assertEqual(port["direction_axis"], 2)
        self.assertEqual(port["sign"], 1)
        self.assertAlmostEqual(port["width"], .003)
        self.assertAlmostEqual(port["height"], .001524)
        self.assertEqual(port["z0"], 50.)
        # the design feed sits at x = -6 mm, y = 0: width axis is x (first transverse axis)
        self.assertAlmostEqual(port["lo"][0], -.0075)
        self.assertAlmostEqual(port["hi"][0], -.0045)
        self.assertEqual((port["lo"][1], port["hi"][1]), (0., 0.))
        self.assertEqual((port["lo"][2], port["hi"][2]), (0., .001524))

    def test_reversed_feed_flips_the_sign_and_keeps_the_box(self):
        d = patch()
        d["ports"][0]["start"], d["ports"][0]["stop"] = d["ports"][0]["stop"], d["ports"][0]["start"]
        case = admit(d, settings())
        self.assertEqual(case["port"]["sign"], -1)
        self.assertEqual(case["port"]["lo"][2], 0.)

    def test_input_is_not_modified(self):
        d = patch()
        conductive(d)
        original = copy.deepcopy(d)
        s = settings(approximate_metals=True)
        s_original = copy.deepcopy(s)
        admit(d, s)
        self.assertEqual(d, original)
        self.assertEqual(s, s_original)

    def test_approximate_metals_is_explicit_and_recorded(self):
        d = patch()
        conductive(d)
        with self.assertRaises(ValueError):
            admit(d, settings())
        with self.assertRaises(ValueError):
            admit(d, settings(approximate_metals=False))
        case = admit(d, settings(approximate_metals=True))
        self.assertEqual(case["pec_approximations"], ["copper"])
        self.assertTrue(any("PEC approximation" in t and "copper" in t for t in case["limitations"]))
        self.assertEqual(case["boxes"], admit(patch(), settings())["boxes"])

    def test_lossless_dielectric_has_no_loss_limitation(self):
        d = patch()
        m = next(m for m in d["materials"] if m["kind"] == "dielectric")
        m.pop("tan_d")
        m.pop("tan_d_freq")
        case = admit(d, settings())
        self.assertEqual(case["boxes"][0]["tan_d"], 0.)
        self.assertFalse(any("loss tangent" in t for t in case["limitations"]))

    def test_rejections(self):
        cases = [
            (two_ports, "one rectangular lumped port"), (resistor, "lumped elements"),
            (lumped_element, "lumped elements"), (transform, "untransformed"), (rotated, "untransformed"),
            (cut, "untransformed"), (curved, "axis-aligned boxes"), (metal_volume, "PEC sheet"),
            (flat_dielectric, "must have volume"), (overlap, "Overlapping"),
            (no_tan_d_freq, "tan_d_freq"), (feed_floats, "contact PEC"), (crossing_sheet, "crosses the feed gap"),
            (real_feed, "ideal line feed"), (reactive, "port properties"),
            (unknown_port_key, "port properties"), (unknown_material_key, "material properties"),
            (not_excited, "excited"), (edge_feed, "contact PEC"),
        ]
        for mutate, text in cases:
            with self.subTest(mutate.__name__):
                d = patch()
                mutate(d)
                with self.assertRaises(ValueError) as caught:
                    admit(d, settings())
                if text:
                    self.assertIn(text, str(caught.exception))

    def test_unsupported_material_kind_and_missing_parts_are_rejected(self):
        d = patch()
        d["parts"] = [p for p in d["parts"] if p["name"] != "substrate"]
        with self.assertRaises(ValueError):
            admit(d, settings())
        d = patch()
        d["parts"] = [p for p in d["parts"] if p["name"] == "substrate"]
        d["ports"] = []
        with self.assertRaises(ValueError):
            admit(d, settings())

    def test_adjacent_dielectric_boxes_are_not_overlapping(self):
        d = patch()
        part(d, "substrate")["primitives"] = [box(["-G/2", "-G/2", "0"], ["0", "G/2", "h"])]
        second_dielectric(d, ["0", "-G/2", "0"], ["G/2", "G/2", "h"])
        self.assertEqual(len(admit(d, settings())["boxes"]), 2)

    def test_settings_validation(self):
        bad = [
            dict(unknown=1), dict(analysis="eigen"), dict(accept_finite_feed=False),
            dict(accept_finite_feed="yes"), dict(feed_width_mm=0), dict(feed_width_mm=True),
            dict(feed_width_mm=float("nan")), dict(padding_mm=-1), dict(padding_mm="40"),
            dict(resolution="medium"), dict(resolution=.2),
            dict(points=2), dict(points=22), dict(points=5.), dict(points=True),
            dict(f_min_hz=3e9), dict(f_min_hz=4e9), dict(f_min_hz=5e5), dict(f_max_hz=2e11),
            dict(f_max_hz=float("inf")), dict(f_min_hz=True), dict(approximate_metals="no"),
            dict(approximate_metals=1),
        ]
        for over in bad:
            with self.subTest(over):
                with self.assertRaises(ValueError):
                    admit(patch(), settings(**over))
        for key in ("analysis", "accept_finite_feed", "feed_width_mm", "padding_mm", "resolution",
                    "f_min_hz", "f_max_hz", "points"):
            with self.subTest(missing=key):
                s = settings()
                s.pop(key)
                with self.assertRaises(ValueError):
                    admit(patch(), s)
        with self.assertRaises(ValueError):
            admit(patch(), None)
        self.assertEqual(admit(patch(), settings(points=3))["frequencies_hz"], [2e9, 2.5e9, 3e9])
        self.assertEqual(len(admit(patch(), settings(points=21))["frequencies_hz"]), 21)

    def test_too_large_domain_is_rejected_before_launch(self):
        with self.assertRaisesRegex(ValueError, "Domain too large"):
            admit(patch(), settings(padding_mm=2000))
        # a domain that passes at coarse resolution is rejected at fine resolution
        d, edge = patch(), 0
        for pad in range(100, 1000, 10):
            try:
                admit(d, settings(padding_mm=pad))
            except ValueError:
                edge = pad
                break
        self.assertGreater(edge, 100)
        self.assertEqual(admit(d, settings(padding_mm=edge - 10))["resolution"], .25)
        with self.assertRaises(ValueError):
            admit(d, settings(padding_mm=edge - 10, resolution="fine"))

    def test_limit_is_the_documented_proxy(self):
        pad = 300.
        case = admit(patch(), settings(padding_mm=pad))
        volume = math.prod(h - l for l, h in zip(case["air"]["lo"], case["air"]["hi"]))
        cells = volume / (C0 / 3e9 * .25) ** 3
        self.assertLess(cells, 200000)
        with self.assertRaises(ValueError):
            admit(patch(), settings(padding_mm=pad, f_max_hz=1e11, f_min_hz=2e9))

    def test_isolation_from_emerge_gmsh_and_emsutil(self):
        source = Path(emerge_design.__file__).read_text(encoding="utf-8")
        found = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                found.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
        self.assertFalse(found & {"emerge", "gmsh", "emsutil"}, found)
        self.assertNotIn("__import__", source)
        self.assertNotIn("importlib", source)


def _variants():
    out = [("patch", patch, False)]

    def add(name, mutate, conductive_metal=False):
        def make():
            d = patch()
            mutate(d)
            return d
        out.append((name, make, conductive_metal))

    add("approximated conductive metal", conductive, True)
    for fn in (two_ports, resistor, lumped_element, transform, rotated, cut, curved, metal_volume,
               flat_dielectric, overlap, no_tan_d_freq, feed_floats, crossing_sheet, real_feed,
               reactive, unknown_port_key, unknown_material_key, not_excited, edge_feed):
        add(fn.__name__, fn)
    return out


class ParityTests(unittest.TestCase):
    """Admission here and in Elmer's driven adapter must agree on the shared rules."""

    def test_parity_with_elmer_driven_prepare(self):
        variants = _variants()
        self.assertGreaterEqual(len(variants), 10)
        accepted = rejected = 0
        for name, make, approximate in variants:
            with self.subTest(name):
                d = make()
                try:
                    elmer_driven.prepare(d, cell_mm=40, padding_mm=40, approximate_metals=approximate)
                    elmer_ok = True
                except ValueError:
                    elmer_ok = False
                try:
                    admit(make(), settings(padding_mm=40, approximate_metals=approximate))
                    emerge_ok = True
                except ValueError:
                    emerge_ok = False
                self.assertEqual(emerge_ok, elmer_ok, f"{name}: elmer={elmer_ok} emerge={emerge_ok}")
                accepted += emerge_ok
                rejected += not emerge_ok
        self.assertGreaterEqual(accepted, 2)
        self.assertGreaterEqual(rejected, 10)


if __name__ == "__main__":
    unittest.main()
