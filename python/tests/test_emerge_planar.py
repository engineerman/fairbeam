import ast
import copy
import json
import math
import unittest
from pathlib import Path

from fairbeam import emerge_planar
from fairbeam.emerge_planar import admit

C0 = 299792458.0
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "emerge_hairpin.design.json"
PORT_PAD_MM = 1.0
METAL_EDGE_MM = 0.4
MAX_RESOURCE_CELLS = 400000


def hairpin():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def settings(**over):
    s = dict(analysis="planar_two_port", accept_lumped_terminals=True, enclosure="shielded",
             air_height_mm=6.4, resolution="coarse", f_min_hz=0.75e9, f_max_hz=1.25e9, points=5,
             approximate_metals=True)
    s.update(over)
    return s


def open_settings(**over):
    base = dict(enclosure="open", padding_mm=10.)
    base.update(over)
    return settings(**base)


def part(d, name):
    return next(p for p in d["parts"] if p["name"] == name)


def copper_prims(d):
    return part(d, "copper")["primitives"]


class AdmitTests(unittest.TestCase):
    def test_fixture_is_admitted_with_approximate_metals(self):
        case = admit(hairpin(), settings())
        self.assertEqual(case["kind"], "planar")
        self.assertEqual(case["enclosure"], "shielded")
        self.assertEqual(case["resolution"], 0.25)
        self.assertEqual(case["resolution_name"], "coarse")
        self.assertAlmostEqual(case["metal_edge_m"], METAL_EDGE_MM * 1e-3)
        self.assertEqual(case["phasor_convention_out"], "exp(+i omega t)")
        self.assertEqual(case["pec_approximations"], ["copper"])
        self.assertTrue(any("PEC approximation" in t and "copper" in t for t in case["limitations"]))
        self.assertTrue(any("lumped" in t.lower() for t in case["limitations"]))
        sub = case["substrate"]
        self.assertEqual(set(sub), {"lo", "hi", "eps_r", "mu_r", "tan_d"})
        self.assertEqual((sub["eps_r"], sub["mu_r"], sub["tan_d"]), (4.34, 1.0, 0.0026))
        for got, want in zip(sub["lo"], (-0.025414, -0.029, 0.0)):
            self.assertAlmostEqual(got, want, places=12)
        for got, want in zip(sub["hi"], (0.025414, 0.029, 0.0016)):
            self.assertAlmostEqual(got, want, places=12)
        self.assertAlmostEqual(case["ground_z"], 0.0, places=12)
        self.assertEqual(len(case["traces"]), 5)
        self.assertEqual(set(case["traces"][0]), {"xy", "z"})
        self.assertAlmostEqual(case["traces"][0]["z"], 0.0016, places=12)
        self.assertEqual(len(case["frequencies_hz"]), 5)
        self.assertEqual(case["frequencies_hz"][0], 0.75e9)
        self.assertEqual(case["frequencies_hz"][-1], 1.25e9)
        self.assertAlmostEqual(case["frequencies_hz"][1], 0.875e9)
        self.assertEqual(admit(hairpin(), settings(resolution="fine"))["resolution"], 0.15)

    def test_fixture_rejected_without_approximate_metals(self):
        with self.assertRaises(ValueError) as caught:
            admit(hairpin(), settings(approximate_metals=False))
        self.assertIn("approximate_metals", str(caught.exception).lower())
        with self.assertRaises(ValueError):
            s = settings()
            s.pop("approximate_metals")
            admit(hairpin(), s)

    def test_terminal_1_plate_geometry(self):
        case = admit(hairpin(), settings())
        t1 = next(t for t in case["terminals"] if t["number"] == 1)
        self.assertEqual(set(t1), {"number", "lo", "hi", "width", "height", "z0"})
        self.assertEqual(t1["z0"], 50.0)
        self.assertAlmostEqual(t1["width"], 0.00254, places=12)
        self.assertAlmostEqual(t1["height"], 0.0016, places=12)
        for got, want in zip(t1["lo"], (-0.015414, -0.029, 0.0)):
            self.assertAlmostEqual(got, want, places=12)
        for got, want in zip(t1["hi"], (-0.012874, -0.029, 0.0016)):
            self.assertAlmostEqual(got, want, places=12)
        t2 = next(t for t in case["terminals"] if t["number"] == 2)
        self.assertAlmostEqual(t2["lo"][0], 0.012874, places=12)
        self.assertAlmostEqual(t2["hi"][0], 0.015414, places=12)
        self.assertAlmostEqual(t2["lo"][1], -0.029, places=12)
        self.assertAlmostEqual(t2["hi"][1], -0.029, places=12)

    def test_air_floor_is_substrate_bottom(self):
        case = admit(hairpin(), settings())
        self.assertAlmostEqual(case["air"]["lo"][2], case["substrate"]["lo"][2], places=12)
        self.assertAlmostEqual(case["air"]["lo"][2], case["ground_z"], places=12)

    def test_shielded_domain_pads_terminal_face_only(self):
        case = admit(hairpin(), settings(air_height_mm=6.4))
        for got, want in zip(case["air"]["lo"], (-0.025414, -0.030, 0.0)):
            self.assertAlmostEqual(got, want, places=12)
        for got, want in zip(case["air"]["hi"], (0.025414, 0.029, 0.008)):
            self.assertAlmostEqual(got, want, places=12)

    def test_open_adds_padding_on_sides_and_top(self):
        case = admit(hairpin(), open_settings(air_height_mm=6.4, padding_mm=10.))
        for got, want in zip(case["air"]["lo"], (-0.035414, -0.040, 0.0)):
            self.assertAlmostEqual(got, want, places=12)
        for got, want in zip(case["air"]["hi"], (0.035414, 0.039, 0.018)):
            self.assertAlmostEqual(got, want, places=12)
        self.assertEqual(case["enclosure"], "open")

    def test_input_is_not_modified(self):
        d = hairpin()
        original = copy.deepcopy(d)
        s = settings()
        s_original = copy.deepcopy(s)
        admit(d, s)
        self.assertEqual(d, original)
        self.assertEqual(s, s_original)

    def test_parameterised_substrate_height_is_resolved(self):
        d = hairpin()
        next(p for p in d["params"] if p["key"] == "sub_h")["default"] = 2.0
        case = admit(d, settings())
        self.assertAlmostEqual(case["substrate"]["hi"][2], 0.002, places=12)
        t1 = next(t for t in case["terminals"] if t["number"] == 1)
        self.assertAlmostEqual(t1["height"], 0.002, places=12)
        self.assertAlmostEqual(t1["hi"][2], 0.002, places=12)
        self.assertAlmostEqual(case["traces"][0]["z"], 0.002, places=12)

    def test_box_trace_becomes_four_vertex_polygon(self):
        d = hairpin()
        part(d, "copper")["primitives"] = [{
            "kind": "box", "priority": 10,
            "start": [-15.414, -29, "sub_h"], "stop": [-12.874, -19, "sub_h"],
        }]
        # keep a second feed covered so port 2 still has a trace
        part(d, "copper")["primitives"].append({
            "kind": "box", "priority": 10,
            "start": [12.874, -29, "sub_h"], "stop": [15.414, -19, "sub_h"],
        })
        case = admit(d, settings())
        self.assertEqual(len(case["traces"]), 2)
        self.assertEqual(len(case["traces"][0]["xy"]), 4)

    def test_rejections(self):
        def one_port(d):
            d["ports"] = d["ports"][:1]

        def three_ports(d):
            d["ports"].append({**copy.deepcopy(d["ports"][0]), "number": 3,
                               "start": [-1, -29, "sub_h"], "stop": [1, -19, 0]})

        def lumped_port(d):
            d["ports"][0] = {"number": 1, "type": "lumped", "R": 50, "direction": "z",
                             "start": [-15.414, -29, 0], "stop": [-15.414, -29, "sub_h"], "excite": True}
            d["ports"][1] = {"number": 2, "type": "lumped", "R": 50, "direction": "z",
                             "start": [15.414, -29, 0], "stop": [15.414, -29, "sub_h"], "excite": False}

        def cpw_port(d):
            d["ports"][0]["type"] = "cpw"
            d["ports"][0]["gap"] = 0.2
            # CPW width is center strip only in one plane
            d["ports"][0]["start"] = [-15.414, -29, "sub_h"]
            d["ports"][0]["stop"] = [-12.874, -19, "sub_h"]

        def port_direction_z(d):
            d["ports"][0]["direction"] = "z"
            d["ports"][0]["excitation_direction"] = "y"

        def port_face_not_on_edge(d):
            d["ports"][0]["start"][1] = -28
            d["ports"][0]["stop"][1] = -19

        def terminal_not_covered(d):
            d["ports"][0]["start"][0] = -20.0
            d["ports"][0]["stop"][0] = -17.46

        def resistor(d):
            d["resistors"] = [{"name": "r1", "R": "100", "start": ["0", "0", "0"],
                               "stop": ["0", "0", "sub_h"], "direction": "z"}]

        def transform(d):
            part(d, "copper")["transforms"] = [{"type": "translate", "copies": 1, "step": [0, 1, 0]}]

        def cut(d):
            part(d, "copper")["cuts"] = [{"start": [-15, -20, "sub_h"], "stop": [-14, -19, "sub_h"]}]

        def wrong_elevation(d):
            copper_prims(d)[0]["elevation"] = 0.5

        def wrong_normal(d):
            copper_prims(d)[0]["normal"] = "x"
            copper_prims(d)[0]["points"] = [[0, -29], [1.6, -29], [1.6, 19], [0, 19]]
            copper_prims(d)[0]["elevation"] = -15.414

        def metal_volume(d):
            copper_prims(d).append({
                "kind": "box", "priority": 10,
                "start": [0, 0, "sub_h"], "stop": [1, 1, "sub_h+0.5"],
            })

        def two_dielectrics(d):
            d["parts"].append({
                "name": "extra", "material": "substrate", "label": "Extra",
                "primitives": [{"kind": "box", "start": [-5, -5, 0], "stop": [5, 5, "sub_h"]}],
            })

        def missing_ground(d):
            d["parts"] = [p for p in d["parts"] if p["name"] != "gnd"]
            d["simulation"]["boundaries"][4] = "MUR"

        cases = [
            (one_port, "exactly two microstrip"),
            (three_ports, "exactly two microstrip"),
            (lumped_port, "exactly two microstrip"),
            (cpw_port, "exactly two microstrip"),
            (port_direction_z, "direction"),
            (port_face_not_on_edge, "substrate edge"),
            (terminal_not_covered, "trace"),
            (resistor, "lumped"),
            (transform, "transform"),
            (cut, "cut"),
            (wrong_elevation, "elevation"),
            (wrong_normal, "normal"),
            (metal_volume, "volume"),
            (two_dielectrics, "one dielectric"),
            (missing_ground, "ground"),
        ]
        for mutate, text in cases:
            with self.subTest(mutate.__name__):
                d = hairpin()
                mutate(d)
                with self.assertRaises(ValueError) as caught:
                    admit(d, settings())
                self.assertIn(text.lower(), str(caught.exception).lower(), str(caught.exception))

    def test_settings_rejections(self):
        bad = [
            dict(padding_mm=10.),  # shielded forbids padding
            dict(enclosure="open"),  # missing padding
            dict(unknown=1),
            dict(accept_lumped_terminals=False),
            dict(points=2),
            dict(points=42),
            dict(f_min_hz=1.25e9, f_max_hz=0.75e9),
            dict(f_min_hz=1e9, f_max_hz=1e9),
            dict(analysis="driven"),
            dict(enclosure="vacuum"),
            dict(air_height_mm=0),
            dict(resolution="medium"),
        ]
        for over in bad:
            with self.subTest(over):
                with self.assertRaises(ValueError):
                    if "enclosure" in over and over.get("enclosure") == "open" and "padding_mm" not in over:
                        admit(hairpin(), settings(**over))
                    elif "padding_mm" in over and "enclosure" not in over:
                        admit(hairpin(), settings(**over))
                    else:
                        admit(hairpin(), settings(**over))
        with self.assertRaises(ValueError):
            admit(hairpin(), open_settings(padding_mm=0))
        for key in ("analysis", "accept_lumped_terminals", "enclosure", "air_height_mm", "resolution",
                    "f_min_hz", "f_max_hz", "points"):
            with self.subTest(missing=key):
                s = settings()
                s.pop(key)
                with self.assertRaises(ValueError):
                    admit(hairpin(), s)

    def test_too_large_domain_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Domain too large"):
            admit(hairpin(), open_settings(padding_mm=5000, air_height_mm=5000, f_max_hz=1e11, f_min_hz=1e9))

    def test_resource_proxy_matches_documented_limit(self):
        case = admit(hairpin(), settings())
        volume = math.prod(h - l for l, h in zip(case["air"]["lo"], case["air"]["hi"]))
        cells = volume / (C0 / 1.25e9 * 0.25) ** 3
        self.assertLess(cells, MAX_RESOURCE_CELLS)

    def test_isolation_from_emerge_gmsh_and_emsutil(self):
        source = Path(emerge_planar.__file__).read_text(encoding="utf-8")
        found = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                found.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
        self.assertFalse(found & {"emerge", "gmsh", "emsutil"}, found)
        self.assertNotIn("__import__", source)
        self.assertNotIn("importlib", source)


if __name__ == "__main__":
    unittest.main()
