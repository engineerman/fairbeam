"""EMerge coax N-port adapter contracts; EMerge is never installed, imported or run here."""
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fairbeam_emerge as fem
from fairbeam.emerge_port_map import APPROX_COAX_TEM, MAPPED_COAX
from test_emerge_fixture import fake_venv

NATIVE = "exp(+i omega t)"


def sample_case(**overrides):
    """Minimal admitted coax case (metres); synthetic, not from a live admit call."""
    case = {
        "kind": "coax",
        "ports": [{
            "number": 1,
            "start": [0.0, 0.0, -0.03],
            "stop": [0.0, 0.0, 0.0],
            "direction_axis": 2,
            "r_i": 0.001,
            "r_o": 0.003,
            "r_os": 0.0035,
            "er": 1.0,
            "mu_r": 1.0,
            "tan_d": 0.0,
            "design_port_type": "coaxial",
            "mapped_bc": MAPPED_COAX,
            "approximations": [APPROX_COAX_TEM],
            "accept_used": ["accept_coaxial_tem"],
        }],
        "air": {"lo": [-0.0135, -0.0135, -0.04], "hi": [0.0135, 0.0135, 0.01]},
        "frequencies_hz": [1.0e9, 1.5e9, 2.0e9],
        "resolution": 0.25,
        "resolution_name": "coarse",
        "phasor_convention_out": NATIVE,
        "limitations": [
            "Design coaxial → analytic CoaxPort TEM; constant εr fill; experimental, not openEMS-validated.",
        ],
        "pec_approximations": [],
    }
    case.update(overrides)
    return case


def synthetic_raw(case=None, *, s11=0.1, convention=NATIVE, frequencies=None):
    case = case or sample_case()
    frequencies = list(frequencies if frequencies is not None else case["frequencies_hz"])
    n = len(frequencies)
    ports = sorted(case["ports"], key=lambda p: p["number"])
    n_ports = len(ports)
    s = {}
    for i in range(1, n_ports + 1):
        for j in range(1, n_ports + 1):
            val = s11 if i == j else 0.0
            s[f"{i},{j}"] = {"re": [val] * n, "im": [0.0] * n}
    # Analytic Z0 matching worker (air-filled 1 mm / 3 mm ≈ 65.95 Ω).
    eta0 = 376.730313668
    z_ref = [
        (eta0 / (2.0 * math.pi * math.sqrt(p["er"]))) * math.log(p["r_o"] / p["r_i"])
        for p in ports
    ]
    return {"kind": "coax", "emerge_version": "3.0.0b12", "frequency_hz": frequencies,
            "s": s, "z_ref": z_ref,
            "phasor_convention": convention, "native_phasor_convention": convention,
            "elapsed_seconds": 1.5, "mesh": {"nodes": 80, "tetrahedra": 300},
            "limitations": list(case["limitations"]),
            "pec_approximations": list(case.get("pec_approximations") or []),
            "port_map": [{
                "design_port_type": p["design_port_type"],
                "mapped_bc": p["mapped_bc"],
                "approximations": list(p["approximations"]),
                "accept_used": list(p["accept_used"]),
            } for p in ports]}


class CoaxCaseOk(unittest.TestCase):
    def test_accepts_sample_case(self):
        self.assertTrue(fem.coax_case_ok(sample_case()))

    def test_rejects_wrong_kind_and_convention(self):
        with self.assertRaisesRegex(ValueError, "kind"):
            fem.coax_case_ok(sample_case(kind="planar"))
        with self.assertRaisesRegex(ValueError, "phasor_convention_out"):
            fem.coax_case_ok(sample_case(phasor_convention_out="exp(-i omega t)"))

    def test_rejects_bad_radii(self):
        case = sample_case()
        case["ports"][0]["r_o"] = case["ports"][0]["r_i"]
        with self.assertRaisesRegex(ValueError, "radii"):
            fem.coax_case_ok(case)


class AssessCoax(unittest.TestCase):
    def test_exports_results_without_validating(self):
        case = sample_case()
        result = fem.assess_coax(synthetic_raw(case), case)
        self.assertEqual(result["schema"], fem.NPORT_RESULT_SCHEMA)
        self.assertEqual(result["geometry_kind"], fem.GEOMETRY_COAX)
        self.assertEqual(result["status"], "results_exported")
        self.assertFalse(result["precision_converged"])
        self.assertFalse(result["gain_qualified"])
        self.assertEqual(result["phasor_convention"], NATIVE)
        self.assertEqual(len(result["z_ref"]), 1)
        self.assertEqual(result["port_map"][0]["mapped_bc"], MAPPED_COAX)
        self.assertEqual(result["port_map"][0]["accept_used"], ["accept_coaxial_tem"])
        self.assertEqual(result["s"]["1,1"]["re"][0], 0.1)

    def test_rejects_wrong_frequencies(self):
        case = sample_case()
        with self.assertRaisesRegex(ValueError, "frequencies"):
            fem.assess_coax(synthetic_raw(case, frequencies=[1e9, 1.2e9, 2e9]), case)

    def test_rejects_s_above_bound(self):
        case = sample_case()
        with self.assertRaisesRegex(ValueError, r"\|S1,1\|"):
            fem.assess_coax(synthetic_raw(case, s11=1.02), case)


class RunCoax(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.exe, _ = fake_venv(self.root / "venv")
        self.worker = self.root / "fairbeam_emerge_worker.py"
        self.worker.write_text("# stand-in worker\n", encoding="utf-8")
        self.case = sample_case()
        patcher = patch.object(fem, "WORKER", self.worker)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_with(self, process=None, side_effect=None, **kwargs):
        kwargs.setdefault("root", self.root / "venv")
        kwargs.setdefault("experimental", True)
        with patch.object(fem.subprocess, "run", return_value=process, side_effect=side_effect) as launch:
            try:
                return fem.run_coax(self.root / "run", self.case, **kwargs), launch
            finally:
                self.launch = launch

    def manifest(self):
        return json.loads((self.root / "run" / "manifest.json").read_text(encoding="utf-8"))

    def worker_writes(self, raw):
        def fake(*args, **kwargs):
            Path(kwargs["cwd"], "raw.json").write_text(json.dumps(raw), encoding="utf-8")
            return subprocess.CompletedProcess(args[0], 0, "worker log")
        return fake

    def test_requires_opt_in(self):
        with patch.object(fem, "discover") as discover:
            with self.assertRaisesRegex(ValueError, "opt-in"):
                fem.run_coax(self.root / "run", self.case, root=self.root / "venv")
            discover.assert_not_called()

    def test_success_writes_exported_result(self):
        result, _ = self.run_with(side_effect=self.worker_writes(synthetic_raw(self.case)))
        self.assertEqual(result["status"], "results_exported")
        self.assertEqual(result["geometry_kind"], fem.GEOMETRY_COAX)
        written = json.loads((self.root / "run" / "case.json").read_text(encoding="utf-8"))
        self.assertEqual(written["kind"], "coax")
        manifest = self.manifest()
        self.assertEqual(manifest["schema"], fem.COAX_MANIFEST_SCHEMA)
        self.assertEqual(manifest["status"], "results_exported")
        self.assertEqual(manifest["physics"], "coaxial_tem")


class CoaxWorkerContract(unittest.TestCase):
    """BC construction + raw packing without importing EMerge."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        path = Path(fem.__file__).with_name("fairbeam_emerge_worker.py")
        spec = importlib.util.spec_from_file_location("fairbeam_emerge_worker", path)
        cls.worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.worker)

    def test_coax_placement_and_bc_args(self):
        case = sample_case()
        place = self.worker.coax_placement(case["ports"][0])
        self.assertEqual(place["number"], 1)
        self.assertEqual(place["origin"], [0.0, 0.0, -0.03])
        self.assertEqual(place["axis"], [0.0, 0.0, 1.0])
        self.assertAlmostEqual(place["height"], 0.03)
        self.assertEqual(place["rad_in_out"], (0.001, 0.003))
        self.assertGreater(place["z0"], 50.0)
        self.assertLess(place["z0"], 80.0)
        args = self.worker.coax_port_bc_args(place)
        self.assertEqual(args["port_number"], 1)
        self.assertEqual(args["rad_in_out"], (0.001, 0.003))
        self.assertEqual(args["er"], 1.0)

    def test_placement_rejects_invalid_radii(self):
        port = sample_case()["ports"][0]
        port = {**port, "r_os": port["r_o"]}
        with self.assertRaisesRegex(ValueError, "radii"):
            self.worker.coax_placement(port)

    def test_load_case_accepts_coax(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.json"
            path.write_text(json.dumps(sample_case()), encoding="utf-8")
            case = self.worker.load_case(path)
        self.assertEqual(case["kind"], "coax")
        self.assertEqual(len(case["ports"]), 1)

    def test_load_case_rejects_wrong_mapped_bc(self):
        case = sample_case()
        case["ports"][0]["mapped_bc"] = "LumpedPort"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.json"
            path.write_text(json.dumps(case), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "CoaxPort"):
                self.worker.load_case(path)

    def test_build_coax_raw_round_trips(self):
        case = sample_case()
        freqs = case["frequencies_hz"]
        s_params = {"1,1": [0.1 + 0.0j, 0.05, -0.01 + 0.03j]}
        raw = self.worker.build_coax_raw(
            case, "3.0.0b12", freqs, s_params, {"nodes": 10, "tetrahedra": 5}, 1.25)
        json.dumps(raw, allow_nan=False)
        self.assertEqual(raw["kind"], "coax")
        self.assertEqual(len(raw["z_ref"]), 1)
        result = fem.assess_coax(raw, case)
        self.assertEqual(result["status"], "results_exported")
        self.assertEqual(result["geometry_kind"], fem.GEOMETRY_COAX)
        self.assertEqual(result["port_map"][0]["mapped_bc"], "CoaxPort")
        self.assertEqual(self.worker.ABC_ORDER, 2)

    def test_negative_axis_points_start_to_stop(self):
        port = sample_case()["ports"][0]
        port = {**port, "start": [0.0, 0.0, 0.0], "stop": [0.0, 0.0, -0.02]}
        place = self.worker.coax_placement(port)
        self.assertEqual(place["axis"], [0.0, 0.0, -1.0])
        self.assertAlmostEqual(place["height"], 0.02)


class CoaxManagedSmoke(unittest.TestCase):
    """Optional mesh-only smoke under managed EMerge; skipped when unavailable."""

    def test_mesh_only_under_managed_emerge(self):
        root = Path(r"C:\Users\ee\AppData\Local\org.fairbeam.desktop\emerge\3.0.0b12")
        marker = root / "fairbeam-emerge.json"
        if not marker.is_file():
            self.skipTest("managed EMerge 3.0.0b12 not installed")
        case = sample_case(mesh_only=True, resolution=0.33)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "coax-mesh"
            result = fem.run_coax(out, case, root=root, experimental=True, threads=1)
        self.assertEqual(result["status"], "mesh_exported")
        self.assertEqual(result["kind"], "coax")
        self.assertGreater(result["tetrahedra"], 0)


if __name__ == "__main__":
    unittest.main()
