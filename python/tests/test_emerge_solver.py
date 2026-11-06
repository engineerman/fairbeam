"""Unified emerge_solver.admit classifier; no EMerge install required."""
import tempfile
import unittest

from fairbeam.design import blank_design
from fairbeam.emerge_limits import N_MAX
from fairbeam.emerge_solver import (
    ANALYSIS, GEOMETRY_DRIVEN, GEOMETRY_PLANAR, admit, admit_geometry,
)

from test_emerge_design import three_lumped_ports
from test_emerge_planar import hairpin, one_microstrip_port, simple_n_port_board, settings as planar_settings


def nport_driven_settings(**over):
    s = dict(analysis=ANALYSIS, accept_finite_feed=True, feed_width_mm=1., padding_mm=40.,
             resolution="coarse", f_min_hz=2e9, f_max_hz=3e9, points=3)
    s.update(over)
    return s


def nport_planar_settings(**over):
    base = planar_settings(approximate_metals=True)
    base["analysis"] = ANALYSIS
    base.update(over)
    return base


class EmergeSolverAdmit(unittest.TestCase):
    def test_classifies_patch_as_driven_lumped(self):
        case = admit(blank_design("p", "Patch"), nport_driven_settings())
        self.assertEqual(case["kind"], "design")
        self.assertEqual(case["analysis"], ANALYSIS)
        self.assertEqual(case["geometry_kind"], GEOMETRY_DRIVEN)
        self.assertEqual(len(case["ports"]), 1)

    def test_classifies_hairpin_as_planar_microstrip(self):
        case = admit(hairpin(), nport_planar_settings())
        self.assertEqual(case["kind"], "planar")
        self.assertEqual(case["analysis"], ANALYSIS)
        self.assertEqual(case["geometry_kind"], GEOMETRY_PLANAR)
        self.assertEqual(len(case["terminals"]), 2)

    def test_legacy_driven_analysis_rejected(self):
        with self.assertRaisesRegex(ValueError, "emerge_nport"):
            admit(blank_design("p", "Patch"), nport_driven_settings(analysis="driven"))

    def test_legacy_planar_analysis_rejected(self):
        with self.assertRaisesRegex(ValueError, "emerge_nport"):
            admit(hairpin(), nport_planar_settings(analysis="planar_two_port"))

    def test_mixed_port_types_reject(self):
        design = hairpin()
        design["ports"][1]["type"] = "lumped"
        with self.assertRaisesRegex(ValueError, "Mixed port types"):
            admit(design, nport_planar_settings())

    def test_neither_geometry_lists_failed_classes_without_product_names(self):
        design = blank_design("p", "Patch")
        # Probe feed + no enclosure fields → planar fails; omit feed accept → driven fails.
        settings = dict(
            analysis=ANALYSIS, enclosure="shielded", air_height_mm=6.4,
            resolution="coarse", f_min_hz=2e9, f_max_hz=3e9, points=3,
            accept_lumped_terminals=True)
        with self.assertRaises(ValueError) as ctx:
            admit(design, settings)
        message = str(ctx.exception)
        self.assertIn("planar_microstrip:", message)
        self.assertIn("driven_lumped:", message)
        self.assertNotRegex(message, r"(?i)antenna")
        self.assertNotRegex(message, r"(?i)pick the other")

    def test_admit_geometry_forces_kind(self):
        case = admit_geometry(blank_design("p", "Patch"), nport_driven_settings(), GEOMETRY_DRIVEN)
        self.assertEqual(case["geometry_kind"], GEOMETRY_DRIVEN)
        planar = admit_geometry(hairpin(), nport_planar_settings(), GEOMETRY_PLANAR)
        self.assertEqual(planar["geometry_kind"], GEOMETRY_PLANAR)

    def test_nport_admits_three_lumped_driven_and_three_microstrip_planar(self):
        patch = blank_design("p", "Patch")
        three_lumped_ports(patch)
        driven = admit(patch, nport_driven_settings())
        self.assertEqual(driven["geometry_kind"], GEOMETRY_DRIVEN)
        self.assertEqual(len(driven["ports"]), 3)

        board = simple_n_port_board(3)
        planar = admit(board, nport_planar_settings())
        self.assertEqual(planar["geometry_kind"], GEOMETRY_PLANAR)
        self.assertEqual(len(planar["terminals"]), 3)

    def test_one_microstrip_planar_still_admits(self):
        design = one_microstrip_port(hairpin())
        case = admit(design, nport_planar_settings())
        self.assertEqual(case["geometry_kind"], GEOMETRY_PLANAR)
        self.assertEqual(len(case["terminals"]), 1)

    def test_n_max_plus_one_rejects(self):
        board = simple_n_port_board(N_MAX + 1)
        with self.assertRaisesRegex(ValueError, str(N_MAX)):
            admit(board, nport_planar_settings())

    def test_unified_payload_strips_shielded_padding_then_classifies(self):
        # Run UI may send driven padding with shielded enclosure; planar child must
        # not reject solely for that before geometry classify / driven fallback.
        patch = blank_design("p", "Patch")
        case = admit(patch, dict(
            analysis=ANALYSIS, accept_finite_feed=True,
            feed_width_mm=1., padding_mm=40.,
            enclosure="shielded", air_height_mm=6.4,
            refine_conductor_edges=True,
            resolution="coarse", f_min_hz=2e9, f_max_hz=3e9, points=3,
            approximate_metals=False))
        self.assertEqual(case["geometry_kind"], GEOMETRY_DRIVEN)

        hair = admit(hairpin(), dict(
            analysis=ANALYSIS, accept_lumped_terminals=True,
            feed_width_mm=1., padding_mm=40.,
            enclosure="shielded", air_height_mm=6.4,
            refine_conductor_edges=True, approximate_metals=True,
            resolution="coarse", f_min_hz=0.75e9, f_max_hz=1.25e9, points=5))
        self.assertEqual(hair["geometry_kind"], GEOMETRY_PLANAR)


class EmergeSolverResearchPrepare(unittest.TestCase):
    def test_prepare_emerge_nport_patch_and_hairpin(self):
        from fairbeam import research
        from test_emerge_fixture import fake_venv

        with tempfile.TemporaryDirectory() as directory:
            exe, site = fake_venv(directory)
            record = site / "emerge-3.0.0b12.dist-info" / "RECORD"
            record.write_text("emerge/__init__.py,sha256=abc,10\n", encoding="utf-8")
            patch = research.prepare({
                "backend": "emerge", "path": directory,
                "design": blank_design("p", "Patch"),
                "settings": nport_driven_settings()})
            self.assertEqual(patch["normalized"]["geometry_kind"], GEOMETRY_DRIVEN)
            self.assertEqual(patch["normalized"]["analysis"], ANALYSIS)
            self.assertEqual(patch["settings"]["analysis"], ANALYSIS)

            hair = research.prepare({
                "backend": "emerge", "path": directory,
                "design": hairpin(),
                "settings": nport_planar_settings()})
            self.assertEqual(hair["normalized"]["geometry_kind"], GEOMETRY_PLANAR)
            self.assertEqual(hair["normalized"]["kind"], "planar")
            self.assertEqual(str(exe.resolve()), hair["path"])


if __name__ == "__main__":
    unittest.main()
