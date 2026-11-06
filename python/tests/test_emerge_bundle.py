"""EMerge N-port shared Results bundles; EMerge is never imported or run here."""
import ast
import base64
import copy
import json
import unittest
from pathlib import Path

import fairbeam_emerge as fem
from fairbeam.design import blank_design
from fairbeam.emerge_bundle import (
    _pack_nport_sparams, export_emerge_bundle, nport_result_bundle,
)
from fairbeam.emerge_field_cut import FIELD_CUT_NOTE, to_field_plane
from test_emerge_design import three_lumped_ports
from test_emerge_planar import one_microstrip_port

NATIVE = "exp(+i omega t)"
HAIRPIN = Path(__file__).resolve().parent / "fixtures" / "emerge_hairpin.design.json"


def settings(**over):
    s = dict(analysis="emerge_nport", accept_finite_feed=True, feed_width_mm=1., padding_mm=40.,
             resolution="coarse", f_min_hz=2e9, f_max_hz=3e9, points=3)
    s.update(over)
    return s


def planar_settings(**over):
    s = dict(analysis="emerge_nport", accept_lumped_terminals=True, enclosure="shielded",
             air_height_mm=6.4, resolution="coarse", f_min_hz=0.75e9, f_max_hz=1.25e9, points=3,
             approximate_metals=True)
    s.update(over)
    return s


def _s_block(n_ports, n_freq, diag_re=0.2, off_re=0.5, off_im=0.1):
    s = {}
    for i in range(1, n_ports + 1):
        for j in range(1, n_ports + 1):
            if i == j:
                s[f"{i},{j}"] = {"re": [diag_re] * n_freq, "im": [0.0] * n_freq}
            else:
                s[f"{i},{j}"] = {"re": [off_re] * n_freq, "im": [off_im] * n_freq}
    return s


def synthetic_nport_result(n_ports=1, geometry_kind="driven_lumped", **over):
    n_freq = 3
    if geometry_kind == "planar_microstrip":
        base_settings = planar_settings()
        freqs = [0.75e9, 1.0e9, 1.25e9]
        extra = {"enclosure": "shielded", "pec_approximations": ["copper"]}
    else:
        base_settings = settings()
        freqs = [2e9, 2.5e9, 3e9]
        extra = {"pec_approximations": []}
    value = dict(
        schema=fem.NPORT_RESULT_SCHEMA, status="results_exported",
        geometry_kind=geometry_kind,
        precision_converged=False, gain_qualified=False, settings=base_settings,
        limitations=["Experimental"],
        frequency_hz=freqs,
        s=_s_block(n_ports, n_freq, diag_re=0.2, off_re=0.1, off_im=0.0),
        z_ref=[50.] * n_ports,
        phasor_convention=NATIVE, native_phasor_convention=NATIVE,
        elapsed_seconds=12.5, mesh={"nodes": 100, "tetrahedra": 400},
        **extra)
    if geometry_kind == "planar_microstrip" and n_ports == 2:
        # Distinct S22 used by existing Zin assertions.
        value["s"]["2,2"] = {"re": [0.1] * n_freq, "im": [0.0] * n_freq}
        value["s"]["2,1"] = {"re": [0.5] * n_freq, "im": [0.1] * n_freq}
        value["s"]["1,2"] = {"re": [0.5] * n_freq, "im": [0.1] * n_freq}
    if geometry_kind == "driven_lumped" and n_ports == 1:
        value["s"]["1,1"] = {"re": [0., .2, 0.], "im": [.1, 0., -.1]}
    value.update(over)
    return value


def synthetic_field_cut(**over):
    """Tiny complex E cut (nv=2, nu=3) with finite samples for Magnitude + phasor/Play."""
    cut = dict(
        schema="fairbeam.emerge-field-cut/1",
        quantity="E", component="abs", normal="z", axis=2,
        position_m=0.0008, freq_hz=1.0e9, freq_choice="max_abs_s21", port=1,
        u_m=[-0.01, 0.01], v_m=[-0.005, 0.005], nu=3, nv=2,
        ex_re=[[1.0, 0.5, 0.0], [0.0, 0.0, 0.0]],
        ex_im=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
        ey_re=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
        ey_im=[[0.0, 0.0, 0.0], [2.0, 1.0, 0.0]],
        ez_re=[[0.0, 0.0, 0.0], [0.5, 0.25, 0.0]],
        ez_im=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
    )
    cut.update(over)
    return cut


class EmergeNportBundle(unittest.TestCase):
    def test_preserves_design_solver_time_no_conjugation_zin_and_empty_farfield(self):
        design = blank_design("p", "Patch")
        original = copy.deepcopy(design)
        result = synthetic_nport_result(1)
        bundle = nport_result_bundle(design, result)
        self.assertEqual(design, original)
        self.assertEqual(bundle["model"]["id"], "p")
        self.assertEqual(bundle["run"]["solver_time_s"], 12.5)
        self.assertEqual(bundle["run"]["wall_time_s"], 12.5)
        self.assertEqual(bundle["solver"]["engine"], "EMerge")
        self.assertEqual(bundle["solver"]["boundaries"]["x+"], "Second-order absorbing")
        self.assertNotIn("preview", bundle)
        self.assertEqual(bundle["results"]["farfield"], [])
        self.assertEqual(bundle["results"]["ports"]["1"]["s11_im"], [.1, 0., -.1])
        self.assertEqual(bundle["results"]["ports"]["1"]["s11_re"], [0., .2, 0.])
        self.assertAlmostEqual(bundle["results"]["ports"]["1"]["zin_re"][1], 75.)
        self.assertEqual(bundle["ports"][0]["stop"][0] - bundle["ports"][0]["start"][0], 1.)
        self.assertIn("not conjugated", bundle["experimental"]["phasor_convention"])
        self.assertFalse(bundle["experimental"]["precision_converged"])
        self.assertEqual(bundle["experimental"]["geometry_kind"], "driven_lumped")

    def test_experimental_carries_port_map_provenance(self):
        design = blank_design("p", "Patch")
        port_map = [{
            "design_port_type": "lumped", "mapped_bc": "LumpedPort",
            "approximations": ["finite-width lumped feed plate"],
            "accept_used": ["accept_finite_feed"],
        }]
        bundle = nport_result_bundle(design, synthetic_nport_result(1, port_map=port_map))
        self.assertEqual(bundle["experimental"]["port_map"], port_map)

    def test_missing_elapsed_keeps_run_none(self):
        design = blank_design("p", "Patch")
        result = synthetic_nport_result(1)
        del result["elapsed_seconds"]
        bundle = nport_result_bundle(design, result)
        self.assertIsNone(bundle["run"])

    def test_singular_impedance_is_rejected(self):
        design = blank_design("p", "Patch")
        with self.assertRaisesRegex(ValueError, "singular"):
            nport_result_bundle(design, synthetic_nport_result(
                1, s={"1,1": {"re": [1., 1., 1.], "im": [0., 0., 0.]}}))

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

    def test_sparams_complete_two_port_zin_and_empty_farfield(self):
        design = json.loads(HAIRPIN.read_text(encoding="utf-8"))
        original = copy.deepcopy(design)
        result = synthetic_nport_result(2, geometry_kind="planar_microstrip")
        bundle = nport_result_bundle(design, result)
        self.assertEqual(design, original)
        self.assertGreater(bundle["run"]["solver_time_s"], 0)
        self.assertEqual(bundle["run"]["solver_time_s"], 12.5)
        self.assertEqual(bundle["solver"]["engine"], "EMerge")
        self.assertEqual(bundle["solver"]["boundaries"]["z-"], "PEC")
        self.assertEqual(bundle["solver"]["boundaries"]["x+"], "PEC")
        self.assertEqual(bundle["solver"]["enclosure"], "shielded")
        self.assertEqual(bundle["results"]["farfield"], [])
        sp = bundle["results"]["sparams"]
        self.assertEqual(sp["ports"], [1, 2])
        self.assertEqual(sp["excited"], [1, 2])
        self.assertTrue(sp["complete"])
        self.assertEqual(sp["method"], "FEM driven, all ports")
        self.assertEqual(sp["s"]["2,1"], result["s"]["2,1"])
        self.assertEqual(sp["s"]["1,2"]["im"], [0.1, 0.1, 0.1])
        self.assertAlmostEqual(bundle["results"]["ports"]["1"]["zin_re"][0], 75.)
        self.assertEqual(bundle["results"]["ports"]["1"]["s11_re"], [0.2, 0.2, 0.2])
        self.assertEqual(bundle["results"]["ports"]["2"]["s11_re"], [0.1, 0.1, 0.1])
        self.assertIn("not conjugated", bundle["experimental"]["phasor_convention"])

    def test_open_enclosure_uses_absorbing_sides(self):
        design = json.loads(HAIRPIN.read_text(encoding="utf-8"))
        result = synthetic_nport_result(
            2, geometry_kind="planar_microstrip",
            settings=planar_settings(enclosure="open", padding_mm=10.),
            enclosure="open")
        bundle = nport_result_bundle(design, result)
        self.assertEqual(bundle["solver"]["boundaries"]["z-"], "PEC")
        self.assertEqual(bundle["solver"]["boundaries"]["x+"], "Second-order absorbing")
        self.assertEqual(bundle["solver"]["boundaries"]["z+"], "Second-order absorbing")
        self.assertEqual(bundle["solver"]["enclosure"], "open")

    def test_field_cut_maps_to_field_planes_with_phasor(self):
        design = json.loads(HAIRPIN.read_text(encoding="utf-8"))
        cut = synthetic_field_cut()
        bundle = nport_result_bundle(
            design, synthetic_nport_result(2, geometry_kind="planar_microstrip", field_cut=cut))
        planes = bundle["field_planes"]
        self.assertEqual(len(planes), 1)
        plane = planes[0]
        self.assertEqual(plane["quantity"], "E")
        self.assertEqual(plane["normal"], "z")
        self.assertEqual(plane["f"], 1.0e9)
        self.assertEqual(plane["nu"], 3)
        self.assertEqual(plane["nv"], 2)
        self.assertAlmostEqual(plane["position_mm"], 0.8)
        self.assertGreater(plane["max"], 0)
        self.assertIn("phasor", plane)
        self.assertEqual(plane["phasor"]["components"], ["x", "y", "z"])
        self.assertGreater(plane["phasor"]["peak"], 0)
        raw = base64.b64decode(plane["phasor"]["data"])
        self.assertEqual(len(raw), 2 * 3 * 3 * 2)
        self.assertTrue(bundle["experimental"]["field_cut"]["has_phasor"])
        self.assertIn(FIELD_CUT_NOTE, bundle["experimental"]["limitations"])

    def test_pack_driven_n1_and_n3(self):
        design = blank_design("p", "Patch")
        bundle = nport_result_bundle(design, synthetic_nport_result(1))
        sp = bundle["results"]["sparams"]
        self.assertEqual(sp["ports"], [1])
        self.assertEqual(sp["excited"], [1])
        self.assertTrue(sp["complete"])
        self.assertEqual(set(sp["s"]), {"1,1"})
        self.assertAlmostEqual(bundle["results"]["ports"]["1"]["zin_re"][1], 75.)
        self.assertEqual(bundle["experimental"]["geometry_kind"], "driven_lumped")
        self.assertEqual(bundle["results"]["farfield"], [])

        three = blank_design("p3", "Patch")
        three_lumped_ports(three)
        bundle3 = nport_result_bundle(three, synthetic_nport_result(3))
        sp3 = bundle3["results"]["sparams"]
        self.assertEqual(sp3["ports"], [1, 2, 3])
        self.assertEqual(len(sp3["s"]), 9)
        self.assertIn("3,1", sp3["s"])
        self.assertEqual(sp3["s"]["2,3"]["re"], [0.1, 0.1, 0.1])

    def test_pack_planar_n1_and_hairpin_n2(self):
        one = one_microstrip_port(json.loads(HAIRPIN.read_text(encoding="utf-8")))
        bundle = nport_result_bundle(
            one, synthetic_nport_result(1, geometry_kind="planar_microstrip"))
        self.assertEqual(bundle["results"]["sparams"]["ports"], [1])
        self.assertEqual(bundle["solver"]["enclosure"], "shielded")
        self.assertEqual(bundle["experimental"]["geometry_kind"], "planar_microstrip")

        hairpin = json.loads(HAIRPIN.read_text(encoding="utf-8"))
        bundle2 = nport_result_bundle(
            hairpin, synthetic_nport_result(2, geometry_kind="planar_microstrip"))
        sp = bundle2["results"]["sparams"]
        self.assertEqual(sp["ports"], [1, 2])
        self.assertTrue(sp["complete"])
        self.assertEqual(len(sp["s"]), 4)
        self.assertAlmostEqual(bundle2["results"]["ports"]["1"]["zin_re"][0], 75.)

    def test_pack_n3_sparams_shape(self):
        """N=3 packing without a preview-capable 3-port planar Design fixture."""
        ports, sp = _pack_nport_sparams(
            _s_block(3, 3, diag_re=0.2, off_re=0.1, off_im=0.0), [50., 50., 50.])
        self.assertEqual(sp["ports"], [1, 2, 3])
        self.assertEqual(sp["excited"], [1, 2, 3])
        self.assertTrue(sp["complete"])
        self.assertEqual(len(sp["s"]), 9)
        self.assertEqual(set(ports), {"1", "2", "3"})
        self.assertAlmostEqual(ports["2"]["zin_re"][0], 75.)

    def test_export_dispatch_only_nport(self):
        design = json.loads(HAIRPIN.read_text(encoding="utf-8"))
        result = synthetic_nport_result(2, geometry_kind="planar_microstrip")
        via_dispatch = export_emerge_bundle(design, result)
        self.assertEqual(via_dispatch["results"]["sparams"]["ports"], [1, 2])
        with self.assertRaisesRegex(ValueError, "unsupported EMerge result schema"):
            export_emerge_bundle(design, {**result, "schema": "fairbeam.emerge-planar-result/1"})


class EmergeFieldCut(unittest.TestCase):
    def test_to_field_plane_rejects_bad_schema(self):
        with self.assertRaisesRegex(ValueError, "schema"):
            to_field_plane(synthetic_field_cut(schema="other"))

    def test_to_field_plane_preserves_complex_samples(self):
        plane = to_field_plane(synthetic_field_cut())
        self.assertAlmostEqual(plane["magnitude"][1][0], 2.06, places=2)


if __name__ == "__main__":
    unittest.main()
