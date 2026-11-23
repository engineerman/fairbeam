import json
import re
import unittest

from fairbeam.analytic import microstrip_coupled_from_modal, microstrip_eps_eff, microstrip_width
from fairbeam.design import check_design, design_params, resolve_names
from fairbeam.filter_synthesis.design_builder import add_tunable_layout_params
from fairbeam.filter_synthesis.hairpin_bp_common import response_qe_ripple, synthesize_hairpin_layout
from fairbeam.filter_synthesis.hairpin_microstrip_bp import (
    DEFAULT_HAIRPIN_MICROSTRIP_BP,
    HairpinMicrostripBpSpec,
    hairpin_microstrip_bp_spec_from_body,
    synthesize_hairpin_microstrip_bp,
)


def _numeric_literals_in_parts(design: dict) -> set[str]:
    out: set[str] = set()
    for part in design.get("parts", []):
        for prim in part.get("primitives", []):
            for key in ("start", "stop"):
                for coord in prim.get(key, []):
                    if isinstance(coord, (int, float)):
                        out.add(str(coord))
                    elif isinstance(coord, str) and re.fullmatch(r"-?\d+(?:\.\d+)?", coord):
                        out.add(coord)
    return out


class FilterSynthesisHairpinMicrostripBpTests(unittest.TestCase):
    def test_synthesize_order3_defaults_pass_checks(self):
        spec = HairpinMicrostripBpSpec(f0_hz=2e9, order=3, bw_hz=0.2e9)
        result = synthesize_hairpin_microstrip_bp(spec)
        design = result.design
        check_design(design)
        self.assertEqual(len(design.get("ports", [])), 2)
        self.assertEqual(design["ports"][0]["type"], "microstrip")
        self.assertTrue(design["ports"][0].get("excite"))

        layout_keys = {item["key"] for item in result.dimensions}
        param_keys = {p.key for p in design_params(design)}
        self.assertTrue(layout_keys.issubset(param_keys))
        for key in layout_keys:
            if key.startswith("sp") or key == "tap_from_fold":
                continue
            self.assertIn(key, json.dumps(design["parts"]))
        defaults = {item["key"]: item["value"] for item in result.dimensions}
        for lit in _numeric_literals_in_parts(design):
            if lit in {"0", "0.0"}:
                continue
            self.assertNotIn(
                lit,
                {f"{v:.12g}" for v in defaults.values()},
                msg=f"layout default {lit} appears as literal in parts",
            )

        gap_keys = [d["key"] for d in result.dimensions if d["key"].startswith("gap")]
        self.assertEqual(len(gap_keys), spec.order)
        sp_keys = [d["key"] for d in result.dimensions if d["key"].startswith("sp")]
        self.assertEqual(len(sp_keys), max(spec.order - 1, 0))
        self.assertIn("tap_from_fold", defaults)

        metal = [p for p in design["parts"] if p.get("name") == "filter"][0]["primitives"]
        self.assertFalse(any(p.get("kind") == "polygon" for p in metal), "hairpin uses plan-view U boxes, not edge shorts")
        n_u = len([p for p in metal if p.get("kind") == "box"]) - 2
        self.assertEqual(n_u, 3 * spec.order, "order N → N U resonators (3 boxes each)")
        coupled_boxes = [
            p
            for p in metal
            if p.get("kind") == "box"
            and isinstance(p.get("start"), list)
            and len(p["start"]) >= 2
            and str(p["start"][0]) in ("0", "k*q_len")
            and "q_len" in str(p.get("stop", [""])[0])
        ]
        self.assertEqual(coupled_boxes, [], "legacy coupled-line runners along x must be absent")

        sketch = result.geometry_preview
        self.assertIsNotNone(sketch)
        self.assertGreater(len(sketch["elements"]), 0)
        self.assertEqual(len(sketch["bbox"]), 4)
        ports = [el for el in sketch["elements"] if el.get("kind") == "port"]
        self.assertEqual(len(ports), 2)
        self.assertTrue(np_is_finite(sketch["bbox"]))

    def test_default_spec_matches_coupled_task_inputs(self):
        self.assertEqual(DEFAULT_HAIRPIN_MICROSTRIP_BP.f0_hz, 2e9)
        self.assertEqual(DEFAULT_HAIRPIN_MICROSTRIP_BP.order, 3)
        self.assertAlmostEqual(DEFAULT_HAIRPIN_MICROSTRIP_BP.bw_hz, 0.2e9)

    def test_registry_topology_synthesizes(self):
        from fairbeam.filter_synthesis import synthesize

        result = synthesize(
            "hairpin_microstrip_bp",
            {"electrical": {"f0_hz": 2e9, "order": 3, "bw_ghz": 0.2}, "stack": {"thickness_mm": 1.58, "eps_r": 4.2}},
        )
        check_design(result.design)
        self.assertGreater(len(result.geometry_preview["elements"]), 0)

    def test_alternating_u_symmetric_spacing_and_tap(self):
        """Alternating open_down, mirrored sp*, shared intra gap, Hong tap present."""
        spec = HairpinMicrostripBpSpec(f0_hz=2e9, order=3, bw_hz=0.2e9, ripple_db=0.1, eps_r=6.15, h_mm=1.27)
        result = synthesize_hairpin_microstrip_bp(spec)
        dims = {d["key"]: d["value"] for d in result.dimensions}
        self.assertIn("sp0", dims)
        self.assertIn("sp1", dims)
        self.assertAlmostEqual(dims["sp0"], dims["sp1"], places=6)
        self.assertAlmostEqual(dims["gap0"], dims["gap1"], places=6)
        self.assertAlmostEqual(dims["gap1"], dims["gap2"], places=6)
        self.assertAlmostEqual(dims["w0"], dims["w1"], places=6)
        self.assertAlmostEqual(dims["w1"], dims["w2"], places=6)
        self.assertGreater(dims["tap_from_fold"], 0.0)
        self.assertLess(dims["tap_from_fold"], dims["q_len"])

        open_flags = [
            float(p["default"])
            for p in result.design["params"]
            if str(p.get("key", "")).startswith("open_down") and "default" in p
        ]
        self.assertEqual(open_flags, [1.0, 0.0, 1.0])

        names = resolve_names(result.design, {})
        # Outer resonators open_down → tap near fold (high on the arm).
        self.assertAlmostEqual(names["y_feed0"], dims["q_len"] - dims["tap_from_fold"], places=6)
        self.assertAlmostEqual(names["y_feed1"], dims["q_len"] - dims["tap_from_fold"], places=6)

    def test_optimizer_knobs_and_placement_expressions(self):
        """Independent knobs carry ±20% bounds. Placement follows those knobs."""
        spec = HairpinMicrostripBpSpec(f0_hz=2e9, order=3, bw_hz=0.2e9, ripple_db=0.1)
        result = synthesize_hairpin_microstrip_bp(spec)
        params = {p["key"]: p for p in result.design["params"]}

        self.assertIn("expr", params["x_base0"])
        self.assertNotIn("default", params["x_base0"])
        self.assertIn("expr", params["x_end"])
        self.assertIn("expr", params["y_feed0"])
        self.assertNotIn("default", params["y_feed0"])
        self.assertIn("expr", params["y_feed1"])
        self.assertEqual(
            params["y_half"]["expr"],
            "max(q_len,y_feed0+w_feed/2,y_feed1+w_feed/2)+board_margin",
        )
        for key in ("open_down0", "open_down1", "open_down2"):
            self.assertNotIn("expr", params[key])
            self.assertNotIn("min", params[key])
            self.assertNotIn("max", params[key])

        names = resolve_names(result.design, {})
        self.assertGreaterEqual(names["open_down0"], 0.5)
        moved = resolve_names(result.design, {"q_len": names["q_len"] + 1.5})
        self.assertAlmostEqual(moved["y_feed0"], names["y_feed0"] + 1.5)
        self.assertAlmostEqual(moved["x_base1"] - names["x_base1"], 2.0 * (moved["w0"] - names["w0"]))
        wider = resolve_names(result.design, {"w0": names["w0"] + 0.4})
        self.assertAlmostEqual(wider["x_base1"], names["x_base1"] + 0.8)
        self.assertAlmostEqual(wider["x_end"], names["x_end"] + 0.8)

        labels = {
            "w_feed": "Besleme genişliği",
            "q_len": "Çeyrek dalga boyu",
            "tap_from_fold": "Kıvrımdan tap",
            "w0": "Rezonatör 1 genişliği",
            "gap0": "Rezonatör 1 iç aralığı",
            "sp0": "Aralık 1",
            "f0": "Merkez frekansı",
            "bw": "Bant genişliği",
            "eps_r": "Dielektrik sabiti",
            "h": "Alttaş kalınlığı",
            "tan_d": "Kayıp tanjantı",
            "feed_len": "Besleme uzunluğu",
            "board_margin": "Kart payı",
        }
        for key, label in labels.items():
            self.assertEqual(params[key]["label"], label)
            self.assertNotIn("expr", params[key])

        for key in ("w_feed", "q_len", "tap_from_fold", "w0", "gap0", "sp0"):
            row = params[key]
            default = float(row["default"])
            span = abs(default) * 0.2 or 0.1
            self.assertAlmostEqual(row["min"], default - span)
            self.assertAlmostEqual(row["max"], default + span)

        fixed = {
            "f0": (0.5, 30.0),
            "bw": (0.01, 10.0),
            "eps_r": (1.0, 12.0),
            "h": (0.1, 5.0),
            "tan_d": (0.0, 0.1),
            "feed_len": (2.0, 30.0),
            "board_margin": (2.0, 20.0),
        }
        for key, (lo, hi) in fixed.items():
            self.assertAlmostEqual(params[key]["min"], lo)
            self.assertAlmostEqual(params[key]["max"], hi)

        for key in ("order", "ripple_db", "z0"):
            self.assertNotIn("expr", params[key])
            self.assertIn("default", params[key])
            self.assertNotIn("min", params[key])
            self.assertNotIn("max", params[key])

        blank = {"params": []}
        add_tunable_layout_params(blank, [{"key": "sp0", "default": 0.0, "label": "Aralık 1", "unit": "mm"}])
        zero = blank["params"][0]
        self.assertNotIn("expr", zero)
        self.assertAlmostEqual(zero["min"], -0.1)
        self.assertAlmostEqual(zero["max"], 0.1)

    def test_synthesized_design_builds(self):
        """Synthesis layout must resolve for fairbeam.design.build (openEMS geometry)."""
        from fairbeam.design import build

        result = synthesize_hairpin_microstrip_bp(HairpinMicrostripBpSpec(f0_hz=2e9, order=3, bw_hz=0.2e9))
        d = result.design
        d["far_field"] = {"enabled": False}
        d.pop("monitors", None)
        sim = build(d, {})
        self.assertIsNotNone(sim.fdtd)

    def test_chebyshev_ripple_0_1_changes_qe_k_versus_butterworth(self):
        cheby = _layout(ripple_db=0.1, response="chebyshev")
        butter = _layout(ripple_db=0.1, response="butterworth")
        self.assertNotAlmostEqual(cheby["qe1"], butter["qe1"])
        self.assertNotEqual(cheby["k"], butter["k"])
        classic = _layout(ripple_db=0.0, response="chebyshev")
        self.assertAlmostEqual(butter["qe1"], classic["qe1"])
        self.assertEqual(butter["k"], classic["k"])

    def test_equiripple_body_is_not_chebyshev_ripple(self):
        body = {
            "electrical": {
                "f0_hz": 2e9,
                "order": 3,
                "bw_hz": 0.2e9,
                "ripple_db": 0.1,
                "response": "equiripple",
                "z0": 50,
            },
            "stack": {"eps_r": 4.2, "thickness_mm": 1.58, "tan_d": 0.02},
            "layout": {"feed_len_mm": 6, "board_margin_mm": 8, "intra_gap_mm": 2},
        }
        spec = hairpin_microstrip_bp_spec_from_body(body)
        self.assertEqual(spec.response, "equiripple")
        self.assertAlmostEqual(spec.ripple_db, 0.1)
        self.assertIsNone(response_qe_ripple(spec.response, spec.ripple_db))
        self.assertAlmostEqual(response_qe_ripple("chebyshev", spec.ripple_db), 0.1)
        with self.assertRaises(ValueError) as raised:
            synthesize_hairpin_microstrip_bp(spec)
        self.assertIn("not used as Chebyshev passband ripple", str(raised.exception))
        cheby = synthesize_hairpin_microstrip_bp(
            HairpinMicrostripBpSpec(f0_hz=2e9, order=3, bw_hz=0.2e9, ripple_db=0.1, response="chebyshev")
        )
        self.assertGreater(len(cheby.dimensions), 0)


def _layout(*, ripple_db: float, response: str) -> dict:
    return synthesize_hairpin_layout(
        order=3,
        fbw=0.1,
        ripple_db=ripple_db,
        response=response,
        z0=50.0,
        eps_r=4.2,
        thickness_mm=1.58,
        f0_hz=2e9,
        coupled_from_modal=microstrip_coupled_from_modal,
        center_width=microstrip_width,
        line_eps_eff=microstrip_eps_eff,
    )


def np_is_finite(values: list[float]) -> bool:
    import math

    return all(math.isfinite(v) for v in values)


if __name__ == "__main__":
    unittest.main()
