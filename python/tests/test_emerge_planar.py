import ast
import copy
import json
import math
import unittest
from pathlib import Path

from fairbeam import emerge_planar
from fairbeam.emerge_limits import N_MAX
from fairbeam.emerge_planar import admit

C0 = 299792458.0
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "emerge_hairpin.design.json"
PORT_PAD_MM = 1.0
METAL_EDGE_MM = 0.4
MAX_RESOURCE_CELLS = 400000


def hairpin():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def settings(**over):
    s = dict(analysis="emerge_nport", accept_lumped_terminals=True, enclosure="shielded",
             air_height_mm=6.4, resolution="coarse", f_min_hz=0.75e9, f_max_hz=1.25e9, points=5,
             approximate_metals=False)
    s.update(over)
    return s


def discrete_settings(**over):
    """Planar Discrete/lumped runs require accept_finite_feed; not accept_lumped_terminals."""
    s = settings(accept_finite_feed=True)
    s.pop("accept_lumped_terminals", None)
    s.update(over)
    return s


def with_discrete_ports(d):
    """Board-edge strip-to-ground plates matching the hairpin feed faces (width from Design)."""
    d["ports"] = [
        {"number": 1, "type": "lumped", "R": 50, "direction": "z",
         "start": [-15.414, -29, 0], "stop": [-12.874, -29, "sub_h"], "excite": True},
        {"number": 2, "type": "lumped", "R": 50, "direction": "z",
         "start": [12.874, -29, 0], "stop": [15.414, -29, "sub_h"], "excite": False},
    ]
    return d


def one_microstrip_port(d):
    """Keep only port 1 of a planar Design (hairpin left feed)."""
    d["ports"] = d["ports"][:1]
    return d


def simple_n_port_board(n):
    """Minimal substrate + full-top metal with ``n`` edge microstrip ports (synthetic admit)."""
    if n < 1:
        raise ValueError("n must be >= 1")
    # Three distinct board-edge faces; extra ports share the south edge with offset spans.
    face_specs = [
        ("y", [-1.0, -10.0, "sub_h"], [1.0, 0.0, 0]),           # south
        ("y", [-1.0, 10.0, "sub_h"], [1.0, 0.0, 0]),             # north
        ("x", [-10.0, -1.0, "sub_h"], [0.0, 1.0, 0]),            # west
    ]
    ports = []
    for i in range(1, n + 1):
        if i <= 3:
            direction, start, stop = face_specs[i - 1]
        else:
            # Additional ports on the south edge, shifted in x (metal covers full top).
            offset = 2.5 * (i - 3)
            direction, start, stop = (
                "y",
                [-1.0 + offset, -10.0, "sub_h"],
                [1.0 + offset, 0.0, 0],
            )
        ports.append({
            "number": i, "type": "microstrip", "conductor": "copper",
            "direction": direction, "excitation_direction": "z",
            # Nonzero measurement_shift so design.build / preview accept the port.
            "feed_shift": 0, "measurement_shift": 1.0, "reference_ohm": 50,
            "termination": "open", "excite": i == 1,
            "start": start, "stop": stop,
        })
    return {
        "schema": "fairbeam.design/1",
        "model": {"id": f"emerge-planar-n{n}", "name": f"Synthetic planar {n}-port"},
        "params": [{"key": "sub_h", "default": 1.6, "label": "h", "unit": "mm"}],
        "simulation": {
            "f_min": 0.75, "f_max": 1.25,
            "boundaries": ["MUR", "MUR", "MUR", "MUR", "PEC", "MUR"],
            "end_criteria_db": -40, "max_timesteps": 1000,
        },
        "materials": [
            {"name": "substrate", "kind": "dielectric", "eps_r": 4.34, "tan_d": 0.0},
            {"name": "gnd", "kind": "metal"},
            {"name": "copper", "kind": "metal", "conductivity": 58000000, "thickness": 0.035},
        ],
        "parts": [
            {"name": "substrate", "label": "Substrate", "material": "substrate",
             "primitives": [{"kind": "box", "priority": 0,
                             "start": [-10, -10, 0], "stop": [10, 10, "sub_h"]}]},
            {"name": "gnd", "label": "Ground", "material": "gnd",
             "primitives": [{"kind": "box", "priority": 0,
                             "start": [-10, -10, 0], "stop": [10, 10, 0]}]},
            {"name": "copper", "label": "Trace", "material": "copper",
             "primitives": [{"kind": "box", "priority": 10,
                             "start": [-10, -10, "sub_h"], "stop": [10, 10, "sub_h"]}]},
        ],
        "ports": ports,
        "resistors": [],
        "mesh": {"mode": "design", "overrides": {}, "thin_metal": "sheet"},
        "far_field": {"enabled": False},
        "monitors": {"currents": [], "field_planes": []},
    }


def open_settings(**over):
    base = dict(enclosure="open", padding_mm=10.)
    base.update(over)
    return settings(**base)


def part(d, name):
    return next(p for p in d["parts"] if p["name"] == name)


def copper_prims(d):
    return part(d, "copper")["primitives"]


class AdmitTests(unittest.TestCase):
    def test_fixture_is_admitted_with_thin_conductor_traces(self):
        case = admit(hairpin(), settings())
        self.assertEqual(case["kind"], "planar")
        self.assertEqual(case["enclosure"], "shielded")
        self.assertEqual(case["resolution"], 0.25)
        self.assertEqual(case["resolution_name"], "coarse")
        self.assertAlmostEqual(case["metal_edge_m"], METAL_EDGE_MM * 1e-3)
        self.assertEqual(case["phasor_convention_out"], "exp(+i omega t)")
        self.assertEqual(case["pec_approximations"], [])
        self.assertTrue(any("ThinConductor" in t for t in case["limitations"]))
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
        self.assertEqual(set(case["traces"][0]), {"xy", "z", "conductivity", "thickness_m"})
        self.assertEqual(case["traces"][0]["conductivity"], 58000000.0)
        self.assertAlmostEqual(case["traces"][0]["thickness_m"], 0.035e-3, places=15)
        self.assertAlmostEqual(case["traces"][0]["z"], 0.0016, places=12)
        self.assertEqual(len(case["frequencies_hz"]), 5)
        self.assertEqual(case["frequencies_hz"][0], 0.75e9)
        self.assertEqual(case["frequencies_hz"][-1], 1.25e9)
        self.assertAlmostEqual(case["frequencies_hz"][1], 0.875e9)
        self.assertEqual(admit(hairpin(), settings(resolution="fine"))["resolution"], 0.15)

    def test_numeric_resolution_passes_raw_wavelength_fraction(self):
        case = admit(hairpin(), settings(resolution=0.01))
        self.assertEqual(case["resolution"], 0.01)
        self.assertEqual(case["resolution_name"], "custom")
        with self.assertRaises(ValueError):
            admit(hairpin(), settings(resolution=0.0))
        with self.assertRaises(ValueError):
            admit(hairpin(), settings(resolution=0.6))

    def test_refine_conductor_edges_controls_metal_edge_m(self):
        on = admit(hairpin(), settings())
        self.assertAlmostEqual(on["metal_edge_m"], METAL_EDGE_MM * 1e-3)
        explicit = admit(hairpin(), settings(refine_conductor_edges=True))
        self.assertAlmostEqual(explicit["metal_edge_m"], METAL_EDGE_MM * 1e-3)
        off = admit(hairpin(), settings(refine_conductor_edges=False))
        self.assertNotIn("metal_edge_m", off)

    def test_fixture_approximate_metals_forces_pec(self):
        case = admit(hairpin(), settings(approximate_metals=True))
        self.assertEqual(case["pec_approximations"], ["copper"])
        self.assertTrue(any("PEC approximation" in t and "copper" in t for t in case["limitations"]))
        self.assertTrue(all("conductivity" not in t for t in case["traces"]))
        s = settings()
        s.pop("approximate_metals")
        omitted = admit(hairpin(), s)
        self.assertEqual(omitted["pec_approximations"], [])
        self.assertTrue(any(t.get("conductivity") == 58000000.0 for t in omitted["traces"]))

    def test_terminal_1_plate_geometry(self):
        case = admit(hairpin(), settings())
        t1 = next(t for t in case["terminals"] if t["number"] == 1)
        self.assertEqual(
            set(t1),
            {"number", "lo", "hi", "width", "height", "z0",
             "design_port_type", "mapped_bc", "approximations", "accept_used"})
        self.assertEqual(t1["design_port_type"], "microstrip")
        self.assertEqual(t1["mapped_bc"], "LumpedPort")
        self.assertEqual(t1["accept_used"], ["accept_lumped_terminals"])
        self.assertEqual(
            t1["approximations"],
            ["microstrip → lumped strip-to-ground terminal; feed_shift/measurement_shift unused"])
        self.assertEqual(t1["z0"], 50.0)
        self.assertAlmostEqual(t1["width"], 0.00254, places=12)
        self.assertAlmostEqual(t1["height"], 0.0016, places=12)
        for got, want in zip(t1["lo"], (-0.015414, -0.029, 0.0)):
            self.assertAlmostEqual(got, want, places=12)
        for got, want in zip(t1["hi"], (-0.012874, -0.029, 0.0016)):
            self.assertAlmostEqual(got, want, places=12)
        t2 = next(t for t in case["terminals"] if t["number"] == 2)
        self.assertEqual(t2["mapped_bc"], "LumpedPort")
        self.assertEqual(t2["design_port_type"], "microstrip")
        self.assertAlmostEqual(t2["lo"][0], 0.012874, places=12)
        self.assertAlmostEqual(t2["hi"][0], 0.015414, places=12)
        self.assertAlmostEqual(t2["lo"][1], -0.029, places=12)
        self.assertAlmostEqual(t2["hi"][1], -0.029, places=12)

    def test_one_microstrip_port_admits(self):
        case = admit(one_microstrip_port(hairpin()), settings())
        self.assertEqual(case["kind"], "planar")
        self.assertEqual(len(case["terminals"]), 1)
        self.assertEqual(case["terminals"][0]["number"], 1)
        self.assertEqual(case["terminals"][0]["design_port_type"], "microstrip")

    def test_three_microstrip_ports_admit_on_synthetic_board(self):
        case = admit(simple_n_port_board(3), settings())
        self.assertEqual(case["kind"], "planar")
        self.assertEqual([t["number"] for t in case["terminals"]], [1, 2, 3])
        self.assertEqual(len(case["terminals"]), 3)

    def test_nine_ports_exceed_n_max(self):
        with self.assertRaises(ValueError) as caught:
            admit(simple_n_port_board(N_MAX + 1), settings())
        self.assertIn(str(N_MAX), str(caught.exception))

    def test_two_discrete_ports_admit_with_finite_feed(self):
        case = admit(with_discrete_ports(hairpin()), discrete_settings())
        self.assertEqual(case["kind"], "planar")
        self.assertEqual(len(case["terminals"]), 2)
        self.assertTrue(any("Discrete" in t for t in case["limitations"]))
        t1 = next(t for t in case["terminals"] if t["number"] == 1)
        self.assertEqual(t1["design_port_type"], "lumped")
        self.assertEqual(t1["mapped_bc"], "LumpedPort")
        self.assertEqual(t1["accept_used"], ["accept_finite_feed"])
        self.assertEqual(
            t1["approximations"],
            ["planar discrete → LumpedPort plate at board-edge face"])
        self.assertAlmostEqual(t1["width"], 0.00254, places=12)
        self.assertAlmostEqual(t1["height"], 0.0016, places=12)
        for got, want in zip(t1["lo"], (-0.015414, -0.029, 0.0)):
            self.assertAlmostEqual(got, want, places=12)
        for got, want in zip(t1["hi"], (-0.012874, -0.029, 0.0016)):
            self.assertAlmostEqual(got, want, places=12)
        t2 = next(t for t in case["terminals"] if t["number"] == 2)
        self.assertEqual(t2["design_port_type"], "lumped")
        self.assertEqual(t2["mapped_bc"], "LumpedPort")
        self.assertEqual(t2["accept_used"], ["accept_finite_feed"])

    def test_discrete_missing_accept_finite_feed(self):
        with self.assertRaises(ValueError) as caught:
            admit(with_discrete_ports(hairpin()), settings())  # accept_lumped_terminals only
        self.assertIn("finite-feed", str(caught.exception).lower())

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
        def noncontiguous_numbers(d):
            d["ports"][1]["number"] = 3

        def zero_width_discrete(d):
            with_discrete_ports(d)
            d["ports"][0]["stop"] = [-15.414, -29, "sub_h"]  # same x as start → zero width

        def mixed_types(d):
            d["ports"][0]["type"] = "lumped"
            d["ports"][0]["R"] = 50
            d["ports"][0].pop("reference_ohm", None)

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
            (noncontiguous_numbers, "contiguous"),
            (mixed_types, "mixed"),
            (cpw_port, "mixed"),
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

        with self.subTest("zero_width_discrete"):
            d = hairpin()
            zero_width_discrete(d)
            with self.assertRaises(ValueError) as caught:
                admit(d, discrete_settings())
            # Line feed (no plate width) is not a board-edge face plate.
            self.assertIn("board-edge", str(caught.exception).lower(), str(caught.exception))

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
            dict(refine_conductor_edges=1),
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
        for key in ("analysis", "enclosure", "air_height_mm", "resolution",
                    "f_min_hz", "f_max_hz", "points"):
            with self.subTest(missing=key):
                s = settings()
                s.pop(key)
                with self.assertRaises(ValueError):
                    admit(hairpin(), s)
        with self.subTest(missing="accept_lumped_terminals"):
            s = settings()
            s.pop("accept_lumped_terminals")
            with self.assertRaises(ValueError) as caught:
                admit(hairpin(), s)
            self.assertIn("accept_lumped_terminals", str(caught.exception))

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
