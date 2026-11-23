"""Stage A–C emerge_port_map.resolve outcomes — no emerge / numpy / admit wiring."""
import ast
import unittest
from pathlib import Path

from fairbeam.emerge_port_map import (
    APPROX_COAX_TEM,
    APPROX_DRIVEN_LUMPED,
    APPROX_FIXTURE_WG,
    APPROX_PLANAR_CPW,
    APPROX_PLANAR_CPW_MODAL,
    APPROX_PLANAR_LUMPED,
    APPROX_PLANAR_MICROSTRIP,
    APPROX_PLANAR_MICROSTRIP_MODAL,
    FIXTURE_WAVEGUIDE_SENTINEL,
    MAPPED_COAX,
    MAPPED_LUMPED,
    MAPPED_RECT_WG,
    MAPPED_WAVE,
    resolve,
)


def driven_settings(**over):
    s = dict(accept_finite_feed=True)
    s.update(over)
    return s


def planar_settings(**over):
    s = dict(accept_lumped_terminals=True)
    s.update(over)
    return s


def coax_settings(**over):
    s = dict(accept_coaxial_tem=True)
    s.update(over)
    return s


def lumped(**over):
    p = dict(type="lumped", number=1, R="50", direction="z")
    p.update(over)
    return p


def microstrip(**over):
    p = dict(type="microstrip", number=1, direction="x", excitation_direction="z")
    p.update(over)
    return p


def waveguide(**over):
    p = dict(type="waveguide", number=1, mode="TE10", a="22.86", b="10.16", direction="z")
    p.update(over)
    return p


def coaxial(**over):
    p = dict(type="coaxial", number=1, mode="TEM", direction="z")
    p.update(over)
    return p


def cpw(**over):
    p = dict(type="cpw", number=1, direction="x", excitation_direction="y", gap="0.5")
    p.update(over)
    return p


class ResolveOk(unittest.TestCase):
    def test_driven_lumped_with_accept(self):
        r = resolve(lumped(), path="driven", settings=driven_settings())
        self.assertTrue(r["ok"])
        self.assertEqual(r["mapped_bc"], MAPPED_LUMPED)
        self.assertEqual(r["accept_used"], ["accept_finite_feed"])
        self.assertEqual(r["approximations"], [APPROX_DRIVEN_LUMPED])
        self.assertIsNone(r["error"])

    def test_driven_lumped_default_type(self):
        r = resolve({"number": 1, "R": "50"}, path="driven", settings=driven_settings())
        self.assertTrue(r["ok"])
        self.assertEqual(r["mapped_bc"], MAPPED_LUMPED)

    def test_planar_microstrip_with_lumped_accept(self):
        r = resolve(microstrip(), path="planar", settings=planar_settings())
        self.assertTrue(r["ok"])
        self.assertEqual(r["mapped_bc"], MAPPED_LUMPED)
        self.assertEqual(r["accept_used"], ["accept_lumped_terminals"])
        self.assertEqual(r["approximations"], [APPROX_PLANAR_MICROSTRIP])
        self.assertIsNone(r["error"])

    def test_planar_microstrip_with_modal_accept(self):
        r = resolve(
            microstrip(),
            path="planar",
            settings=dict(accept_modal_ports=True),
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["mapped_bc"], MAPPED_WAVE)
        self.assertEqual(r["accept_used"], ["accept_modal_ports"])
        self.assertEqual(r["approximations"], [APPROX_PLANAR_MICROSTRIP_MODAL])
        self.assertIsNone(r["error"])

    def test_planar_microstrip_modal_wins_over_lumped(self):
        r = resolve(
            microstrip(),
            path="planar",
            settings=dict(accept_modal_ports=True, accept_lumped_terminals=True),
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["mapped_bc"], MAPPED_WAVE)
        self.assertEqual(r["accept_used"], ["accept_modal_ports"])
        self.assertEqual(r["approximations"], [APPROX_PLANAR_MICROSTRIP_MODAL])
        self.assertIsNone(r["error"])

    def test_planar_lumped_with_accept(self):
        r = resolve(lumped(), path="planar", settings=dict(accept_finite_feed=True))
        self.assertTrue(r["ok"])
        self.assertEqual(r["mapped_bc"], MAPPED_LUMPED)
        self.assertEqual(r["accept_used"], ["accept_finite_feed"])
        self.assertEqual(r["approximations"], [APPROX_PLANAR_LUMPED])
        self.assertIsNone(r["error"])

    def test_fixture_waveguide_te10(self):
        r = resolve(waveguide(), path="fixture", settings={})
        self.assertTrue(r["ok"])
        self.assertEqual(r["mapped_bc"], MAPPED_RECT_WG)
        self.assertEqual(r["accept_used"], [])
        self.assertEqual(r["approximations"], [APPROX_FIXTURE_WG])
        self.assertIsNone(r["error"])

    def test_fixture_sentinel(self):
        r = resolve({"type": FIXTURE_WAVEGUIDE_SENTINEL, "mode": "TE10"}, path="fixture", settings={})
        self.assertTrue(r["ok"])
        self.assertEqual(r["mapped_bc"], MAPPED_RECT_WG)

    def test_coax_with_accept(self):
        r = resolve(coaxial(), path="coax", settings=coax_settings())
        self.assertTrue(r["ok"])
        self.assertEqual(r["mapped_bc"], MAPPED_COAX)
        self.assertEqual(r["accept_used"], ["accept_coaxial_tem"])
        self.assertEqual(r["approximations"], [APPROX_COAX_TEM])
        self.assertIsNone(r["error"])

    def test_planar_cpw_with_lumped_accept(self):
        r = resolve(cpw(), path="planar", settings=planar_settings())
        self.assertTrue(r["ok"])
        self.assertEqual(r["mapped_bc"], MAPPED_LUMPED)
        self.assertEqual(r["accept_used"], ["accept_lumped_terminals"])
        self.assertEqual(r["approximations"], [APPROX_PLANAR_CPW])
        self.assertIsNone(r["error"])

    def test_planar_cpw_with_modal_accept(self):
        r = resolve(cpw(), path="planar", settings=dict(accept_modal_ports=True))
        self.assertTrue(r["ok"])
        self.assertEqual(r["mapped_bc"], MAPPED_WAVE)
        self.assertEqual(r["accept_used"], ["accept_modal_ports"])
        self.assertEqual(r["approximations"], [APPROX_PLANAR_CPW_MODAL])
        self.assertIsNone(r["error"])

    def test_planar_cpw_modal_wins_over_lumped(self):
        r = resolve(
            cpw(),
            path="planar",
            settings=dict(accept_modal_ports=True, accept_lumped_terminals=True),
        )
        self.assertTrue(r["ok"])
        self.assertEqual(r["mapped_bc"], MAPPED_WAVE)
        self.assertEqual(r["accept_used"], ["accept_modal_ports"])
        self.assertEqual(r["approximations"], [APPROX_PLANAR_CPW_MODAL])
        self.assertIsNone(r["error"])


class ResolveReject(unittest.TestCase):
    def test_driven_missing_accept(self):
        r = resolve(lumped(), path="driven", settings=driven_settings(accept_finite_feed=False))
        self.assertFalse(r["ok"])
        self.assertIsNone(r["mapped_bc"])
        self.assertIn("finite-feed", r["error"])

    def test_planar_missing_accept(self):
        r = resolve(microstrip(), path="planar", settings={})
        self.assertFalse(r["ok"])
        self.assertIsNone(r["mapped_bc"])
        self.assertIn("accept_modal_ports", r["error"])
        self.assertIn("accept_lumped_terminals", r["error"])

    def test_planar_both_accepts_false(self):
        r = resolve(
            microstrip(),
            path="planar",
            settings=dict(accept_modal_ports=False, accept_lumped_terminals=False),
        )
        self.assertFalse(r["ok"])
        self.assertIn("accept_modal_ports", r["error"])
        self.assertIn("accept_lumped_terminals", r["error"])

    def test_planar_cpw_missing_accept(self):
        r = resolve(cpw(), path="planar", settings={})
        self.assertFalse(r["ok"])
        self.assertIsNone(r["mapped_bc"])
        self.assertIn("accept_modal_ports", r["error"])
        self.assertIn("accept_lumped_terminals", r["error"])
        self.assertIn("CPW", r["error"])

    def test_cpw_rejected_off_planar(self):
        r = resolve(cpw(), path="driven", settings=driven_settings())
        self.assertFalse(r["ok"])
        self.assertIn("CPW", r["error"])

        r = resolve(cpw(), path="fixture", settings={})
        self.assertFalse(r["ok"])
        self.assertIn("waveguide", r["error"].lower())

        r = resolve(cpw(), path="coax", settings=coax_settings())
        self.assertFalse(r["ok"])
        self.assertIn("cpw", r["error"].lower())

    def test_coaxial(self):
        for path, settings in (
            ("driven", driven_settings()),
            ("planar", planar_settings()),
            ("fixture", {}),
        ):
            r = resolve(coaxial(), path=path, settings=settings)
            self.assertFalse(r["ok"], path)
            self.assertIn("coaxial", r["error"].lower())

    def test_coax_missing_accept(self):
        for settings in ({}, coax_settings(accept_coaxial_tem=False)):
            r = resolve(coaxial(), path="coax", settings=settings)
            self.assertFalse(r["ok"])
            self.assertIn("accept_coaxial_tem", r["error"])

    def test_coax_rejects_lumped(self):
        r = resolve(lumped(), path="coax", settings=coax_settings())
        self.assertFalse(r["ok"])

    def test_coax_port_group(self):
        port = coaxial(group={"connection": "parallel", "members": [
            {"start": [0, 0, 0], "stop": [0, 0, 1], "direction": "z", "polarity": "+"},
        ]})
        r = resolve(port, path="coax", settings=coax_settings())
        self.assertFalse(r["ok"])
        self.assertIn("group", r["error"].lower())

    def test_port_group(self):
        port = lumped(group={"connection": "parallel", "members": [
            {"start": [0, 0, 0], "stop": [0, 0, 1], "direction": "z", "polarity": "+"},
        ]})
        r = resolve(port, path="driven", settings=driven_settings())
        self.assertFalse(r["ok"])
        self.assertIn("group", r["error"].lower())

    def test_driven_microstrip(self):
        r = resolve(microstrip(), path="driven", settings=driven_settings())
        self.assertFalse(r["ok"])
        self.assertIn("microstrip", r["error"].lower())

    def test_planar_lumped_missing_accept(self):
        r = resolve(lumped(), path="planar", settings=planar_settings())
        self.assertFalse(r["ok"])
        self.assertIsNone(r["mapped_bc"])
        self.assertIn("finite-feed", r["error"])

    def test_planar_lumped_accept_false(self):
        r = resolve(lumped(), path="planar", settings=dict(accept_finite_feed=False))
        self.assertFalse(r["ok"])
        self.assertIn("finite-feed", r["error"])

    def test_driven_waveguide(self):
        r = resolve(waveguide(), path="driven", settings=driven_settings())
        self.assertFalse(r["ok"])
        self.assertIn("waveguide", r["error"].lower())

    def test_planar_waveguide(self):
        r = resolve(waveguide(), path="planar", settings=planar_settings())
        self.assertFalse(r["ok"])
        self.assertIn("waveguide", r["error"].lower())

    def test_tm_waveguide_on_fixture(self):
        r = resolve(waveguide(mode="TM11"), path="fixture", settings={})
        self.assertFalse(r["ok"])
        self.assertIn("TM", r["error"])

    def test_tm_via_mode_type(self):
        r = resolve(waveguide(mode_type="TM"), path="driven", settings=driven_settings())
        self.assertFalse(r["ok"])
        self.assertIn("TM", r["error"])

    def test_fixture_non_waveguide(self):
        r = resolve(lumped(), path="fixture", settings={})
        self.assertFalse(r["ok"])


class Isolation(unittest.TestCase):
    def test_module_has_no_forbidden_imports(self):
        src = Path(__file__).resolve().parents[1] / "fairbeam" / "emerge_port_map.py"
        tree = ast.parse(src.read_text(encoding="utf-8"))
        forbidden = {"emerge", "numpy", "gmsh", "emsutil"}
        found = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in forbidden:
                        found.add(root)
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", 1)[0]
                if root in forbidden:
                    found.add(root)
        self.assertEqual(found, set())


if __name__ == "__main__":
    unittest.main()
