"""emerge_coax.admit unit tests; no EMerge install required."""
import unittest

from fairbeam.emerge_coax import admit
from fairbeam.emerge_port_map import APPROX_COAX_TEM, MAPPED_COAX
from fairbeam.emerge_solver import ANALYSIS, GEOMETRY_COAX


def coax_design(**over):
    design = dict(
        schema="fairbeam.design/1",
        model=dict(id="coax_air", name="Coax air"),
        params=[],
        materials=[dict(name="PEC", kind="metal")],
        parts=[],
        ports=[dict(
            number=1, type="coaxial", mode="TEM", direction="z",
            start=[0, 0, -30], stop=[0, 0, 0],
            r_i=1, r_o=3, r_os=3.5, conductor="PEC", dielectric=None,
            feed_shift=10, measurement_shift=20, termination="open", excite=True,
        )],
        simulation=dict(f_min=1, f_max=2, boundaries=["PEC"] * 4 + ["PML_8"] * 2),
        mesh=dict(mode="manual", lines={
            "x": [v * 0.25 for v in range(-16, 17)],
            "y": [v * 0.25 for v in range(-16, 17)],
            "z": list(range(-30, 31)),
        }),
        far_field=dict(enabled=False),
    )
    design.update(over)
    return design


def coax_settings(**over):
    s = dict(
        analysis=ANALYSIS, accept_coaxial_tem=True, padding_mm=10.0,
        resolution="coarse", f_min_hz=1e9, f_max_hz=2e9, points=5,
    )
    s.update(over)
    return s


class EmergeCoaxAdmit(unittest.TestCase):
    def test_admits_one_port_air_coax(self):
        case = admit(coax_design(), coax_settings())
        self.assertEqual(case["kind"], "coax")
        self.assertEqual(len(case["ports"]), 1)
        port = case["ports"][0]
        self.assertEqual(port["number"], 1)
        self.assertEqual(port["design_port_type"], "coaxial")
        self.assertEqual(port["mapped_bc"], MAPPED_COAX)
        self.assertEqual(port["accept_used"], ["accept_coaxial_tem"])
        self.assertEqual(port["approximations"], [APPROX_COAX_TEM])
        self.assertEqual(port["direction_axis"], 2)
        self.assertAlmostEqual(port["r_i"], 1e-3)
        self.assertAlmostEqual(port["r_o"], 3e-3)
        self.assertAlmostEqual(port["r_os"], 3.5e-3)
        self.assertAlmostEqual(port["er"], 1.0)
        self.assertEqual(port["start"], [0.0, 0.0, -0.03])
        self.assertEqual(port["stop"], [0.0, 0.0, 0.0])
        self.assertIn("lo", case["air"])
        self.assertIn("hi", case["air"])
        self.assertEqual(len(case["frequencies_hz"]), 5)
        self.assertEqual(case["phasor_convention_out"], "exp(+i omega t)")

    def test_rejects_without_accept(self):
        with self.assertRaisesRegex(ValueError, "accept_coaxial_tem"):
            admit(coax_design(), coax_settings(accept_coaxial_tem=False))
        settings = coax_settings()
        del settings["accept_coaxial_tem"]
        with self.assertRaisesRegex(ValueError, "accept_coaxial_tem"):
            admit(coax_design(), settings)

    def test_rejects_dispersive_fill(self):
        design = coax_design()
        design["materials"].append(dict(
            name="lossy", kind="dielectric", eps_r=2.1,
            dispersion={"type": "debye"},
        ))
        design["ports"][0]["dielectric"] = "lossy"
        with self.assertRaisesRegex(ValueError, "nondispersive|dispersion|dielectric"):
            admit(design, coax_settings())

    def test_rejects_non_coaxial_port(self):
        design = coax_design()
        design["ports"][0]["type"] = "lumped"
        with self.assertRaisesRegex(ValueError, "coaxial|1 to"):
            admit(design, coax_settings())

    def test_rejects_design_parts(self):
        design = coax_design()
        design["parts"] = [dict(
            name="box", material="PEC",
            primitives=[dict(kind="box", start=[-1, -1, -1], stop=[1, 1, 1])],
        )]
        with self.assertRaisesRegex(ValueError, "parts"):
            admit(design, coax_settings())

    def test_ptfe_fill_sets_er(self):
        design = coax_design()
        design["materials"].append(dict(name="PTFE", kind="dielectric", eps_r=2.1))
        design["ports"][0]["dielectric"] = "PTFE"
        case = admit(design, coax_settings())
        self.assertAlmostEqual(case["ports"][0]["er"], 2.1)


class EmergeSolverCoaxClassify(unittest.TestCase):
    def test_classifies_all_coaxial(self):
        from fairbeam.emerge_solver import admit as solver_admit
        case = solver_admit(coax_design(), coax_settings())
        self.assertEqual(case["kind"], "coax")
        self.assertEqual(case["analysis"], ANALYSIS)
        self.assertEqual(case["geometry_kind"], GEOMETRY_COAX)

    def test_mixed_coax_and_lumped_rejects(self):
        from fairbeam.emerge_solver import admit as solver_admit
        design = coax_design()
        design["ports"].append(dict(
            number=2, type="lumped", start=[0, 0, 0], stop=[0, 0, 1],
            direction="z", R=50, excite=True,
        ))
        with self.assertRaisesRegex(ValueError, "Mixed port types"):
            solver_admit(design, coax_settings())

    def test_admit_geometry_forces_coax(self):
        from fairbeam.emerge_solver import admit_geometry
        case = admit_geometry(coax_design(), coax_settings(), GEOMETRY_COAX)
        self.assertEqual(case["geometry_kind"], GEOMETRY_COAX)
        self.assertEqual(case["kind"], "coax")


if __name__ == "__main__":
    unittest.main()
