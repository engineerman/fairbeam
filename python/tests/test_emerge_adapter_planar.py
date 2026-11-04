"""EMerge planar two-port adapter contracts; EMerge is never installed, imported or run here."""
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
from test_emerge_fixture import fake_venv

NATIVE = "exp(+i omega t)"


def sample_case(**overrides):
    """Minimal admitted planar case (metres); synthetic, not from a live admit call."""
    case = {
        "kind": "planar",
        "substrate": {"lo": [-0.025, -0.029, 0.0], "hi": [0.025, 0.029, 0.0016],
                      "eps_r": 4.34, "mu_r": 1.0, "tan_d": 0.0026},
        "traces": [
            {"xy": [[-0.015, -0.029], [-0.013, -0.029], [-0.013, -0.01], [-0.015, -0.01]],
             "z": 0.0016},
            {"xy": [[0.013, -0.029], [0.015, -0.029], [0.015, -0.01], [0.013, -0.01]],
             "z": 0.0016},
        ],
        "ground_z": 0.0,
        "terminals": [
            {"number": 1, "lo": [-0.015, -0.029, 0.0], "hi": [-0.013, -0.029, 0.0016],
             "width": 0.002, "height": 0.0016, "z0": 50.0},
            {"number": 2, "lo": [0.013, -0.029, 0.0], "hi": [0.015, -0.029, 0.0016],
             "width": 0.002, "height": 0.0016, "z0": 50.0},
        ],
        "air": {"lo": [-0.025, -0.030, 0.0], "hi": [0.025, 0.029, 0.008]},
        "enclosure": "shielded",
        "frequencies_hz": [0.9e9, 1.0e9, 1.1e9],
        "resolution": 0.25,
        "resolution_name": "coarse",
        "metal_edge_m": 0.0004,
        "phasor_convention_out": NATIVE,
        "limitations": ["Each microstrip port becomes a lumped strip-to-ground terminal."],
        "pec_approximations": ["copper"],
    }
    case.update(overrides)
    return case


def synthetic_raw(case=None, *, s21=0.5, s11=0.1, s12=None, s22=0.1,
                  convention=NATIVE, frequencies=None):
    case = case or sample_case()
    frequencies = list(frequencies if frequencies is not None else case["frequencies_hz"])
    n = len(frequencies)
    if s12 is None:
        s12 = s21
    return {"kind": "planar", "emerge_version": "2.8.9", "frequency_hz": frequencies,
            "s": {
                "1,1": {"re": [s11] * n, "im": [0.0] * n},
                "2,1": {"re": [s21] * n, "im": [0.0] * n},
                "1,2": {"re": [s12] * n, "im": [0.0] * n},
                "2,2": {"re": [s22] * n, "im": [0.0] * n},
            },
            "z_ref": [50.0, 50.0], "enclosure": case["enclosure"],
            "phasor_convention": convention, "native_phasor_convention": convention,
            "elapsed_seconds": 2.5, "trace_count": len(case["traces"]),
            "mesh": {"nodes": 100, "tetrahedra": 400},
            "limitations": list(case["limitations"]),
            "pec_approximations": list(case["pec_approximations"])}


class PlanarCaseOk(unittest.TestCase):
    def test_accepts_sample_case(self):
        self.assertTrue(fem.planar_case_ok(sample_case()))

    def test_rejects_wrong_kind_and_convention(self):
        with self.assertRaisesRegex(ValueError, "kind"):
            fem.planar_case_ok(sample_case(kind="design"))
        with self.assertRaisesRegex(ValueError, "phasor_convention_out"):
            fem.planar_case_ok(sample_case(phasor_convention_out="exp(-i omega t)"))


class AssessPlanar(unittest.TestCase):
    def test_exports_results_without_validating(self):
        case = sample_case()
        result = fem.assess_planar(synthetic_raw(case), case)
        self.assertEqual(result["schema"], fem.PLANAR_RESULT_SCHEMA)
        self.assertEqual(result["status"], "results_exported")
        self.assertFalse(result["precision_converged"])
        self.assertFalse(result["gain_qualified"])
        self.assertEqual(result["phasor_convention"], NATIVE)
        self.assertEqual(result["native_phasor_convention"], NATIVE)
        self.assertEqual(result["z_ref"], [50.0, 50.0])
        self.assertEqual(result["enclosure"], "shielded")
        self.assertEqual(result["mesh"], {"nodes": 100, "tetrahedra": 400})
        self.assertEqual(result["settings"]["resolution"], 0.25)
        self.assertEqual(result["s"]["2,1"]["re"][0], 0.5)

    def test_rejects_wrong_frequencies(self):
        case = sample_case()
        with self.assertRaisesRegex(ValueError, "frequencies"):
            fem.assess_planar(synthetic_raw(case, frequencies=[0.9e9, 0.95e9, 1.1e9]), case)

    def test_rejects_non_finite(self):
        case = sample_case()
        raw = synthetic_raw(case)
        raw["s"]["2,1"]["re"][1] = float("nan")
        with self.assertRaisesRegex(ValueError, r"s\[2,1\]"):
            fem.assess_planar(raw, case)

    def test_rejects_s21_above_bound(self):
        case = sample_case()
        with self.assertRaisesRegex(ValueError, r"\|S2,1\|"):
            fem.assess_planar(synthetic_raw(case, s21=1.02, s12=1.02, s11=0.0, s22=0.0), case)

    def test_rejects_column_power(self):
        case = sample_case()
        # |S11|^2 + |S21|^2 = 0.5^2 + 0.9^2 = 1.06 > 1.02
        with self.assertRaisesRegex(ValueError, "column 1 power"):
            fem.assess_planar(synthetic_raw(case, s11=0.5, s21=0.9, s12=0.9, s22=0.1), case)

    def test_rejects_reciprocity(self):
        case = sample_case()
        with self.assertRaisesRegex(ValueError, r"S21"):
            fem.assess_planar(synthetic_raw(case, s21=0.5, s12=0.55), case)

    def test_rejects_wrong_convention(self):
        case = sample_case()
        with self.assertRaisesRegex(ValueError, "phasor_convention"):
            fem.assess_planar(synthetic_raw(case, convention="exp(-i omega t)"), case)

    def test_accepts_at_bounds(self):
        case = sample_case()
        # |S| just under the abs bound; column power exactly at the Shared-facts limit
        edge = math.sqrt(1.02)
        result = fem.assess_planar(
            synthetic_raw(case, s11=0.0, s21=edge, s12=edge, s22=0.0), case)
        self.assertEqual(result["status"], "results_exported")
        self.assertAlmostEqual(abs(complex(result["s"]["2,1"]["re"][0],
                                           result["s"]["2,1"]["im"][0])), edge)


class RunPlanar(unittest.TestCase):
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
                return fem.run_planar(self.root / "run", self.case, **kwargs), launch
            finally:
                self.launch = launch

    def manifest(self):
        return json.loads((self.root / "run" / "manifest.json").read_text(encoding="utf-8"))

    def worker_writes(self, raw):
        def fake(*args, **kwargs):
            Path(kwargs["cwd"], "raw.json").write_text(json.dumps(raw), encoding="utf-8")
            return subprocess.CompletedProcess(args[0], 0, "worker log")
        return fake

    def test_requires_opt_in_before_discovery_or_output(self):
        with patch.object(fem, "discover") as discover:
            with self.assertRaisesRegex(ValueError, "opt-in"):
                fem.run_planar(self.root / "run", self.case, root=self.root / "venv")
            discover.assert_not_called()
        self.assertFalse((self.root / "run").exists())

    def test_existing_output_directory_is_not_overwritten(self):
        (self.root / "run").mkdir()
        with self.assertRaises(FileExistsError):
            fem.run_planar(self.root / "run", self.case, root=self.root / "venv", experimental=True)

    def test_non_zero_exit_keeps_log_and_failed_manifest(self):
        process = subprocess.CompletedProcess([], 3, "worker said no")
        with self.assertRaisesRegex(RuntimeError, "worker.log"):
            self.run_with(process)
        self.assertEqual(self.manifest()["status"], "failed")
        self.assertEqual(self.manifest()["worker_exit_code"], 3)
        self.assertEqual((self.root / "run" / "worker.log").read_text(), "worker said no")

    def test_timeout_keeps_partial_log(self):
        timeout = subprocess.TimeoutExpired([], fem.PLANAR_WORKER_TIMEOUT_S, output=b"partial native output")
        with self.assertRaisesRegex(RuntimeError, "3600 second"):
            self.run_with(side_effect=timeout)
        self.assertEqual((self.root / "run" / "worker.log").read_text(), "partial native output")
        self.assertEqual(self.manifest()["status"], "failed")

    def test_launch_uses_planar_timeout_and_isolation(self):
        with self.assertRaises(RuntimeError):
            self.run_with(subprocess.CompletedProcess([], 1, ""))
        args, kwargs = self.launch.call_args
        self.assertEqual(args[0], [str(self.exe.resolve()), "-I", "-X", "utf8",
                                   "fairbeam_emerge_worker.py", "case.json"])
        self.assertEqual(kwargs["timeout"], 3600)
        env = kwargs["env"]
        for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMBA_NUM_THREADS"):
            self.assertEqual(env[name], "1")
        self.assertNotIn("PYTHONPATH", env)

    def test_success_writes_exported_result(self):
        result, _ = self.run_with(side_effect=self.worker_writes(synthetic_raw(self.case)))
        self.assertEqual(result["status"], "results_exported")
        run = self.root / "run"
        written = json.loads((run / "case.json").read_text(encoding="utf-8"))
        self.assertEqual(written["kind"], "planar")
        self.assertEqual(json.loads((run / "result.json").read_text())["status"], "results_exported")
        manifest = self.manifest()
        self.assertEqual(manifest["schema"], fem.PLANAR_MANIFEST_SCHEMA)
        self.assertEqual(manifest["status"], "results_exported")
        self.assertEqual(manifest["enclosure"], "shielded")
        self.assertEqual((run / "worker.log").read_text(), "worker log")

    def test_malformed_raw_marks_failed(self):
        raw = synthetic_raw(self.case, s21=1.5, s12=1.5, s11=0.0, s22=0.0)
        with self.assertRaises(ValueError):
            self.run_with(side_effect=self.worker_writes(raw))
        self.assertEqual(self.manifest()["status"], "failed")
        self.assertTrue((self.root / "run" / "raw.json").exists())


class PlanarWorkerContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util
        path = Path(fem.__file__).with_name("fairbeam_emerge_worker.py")
        spec = importlib.util.spec_from_file_location("fairbeam_emerge_worker", path)
        cls.worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.worker)

    def test_load_case_accepts_planar(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.json"
            path.write_text(json.dumps(sample_case()), encoding="utf-8")
            case = self.worker.load_case(path)
        self.assertEqual(case["kind"], "planar")
        self.assertEqual(len(case["frequencies_hz"]), 3)
        self.assertEqual(len(case["traces"]), 2)

    def test_load_case_rejects_bad_planar(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.json"
            bad = sample_case(frequencies_hz=[1.1e9, 1.0e9, 0.9e9])
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                self.worker.load_case(path)

    def test_build_planar_raw_round_trips_and_keeps_trace_count(self):
        case = sample_case()
        s_params = {
            "1,1": [0.1 + 0.0j, 0.05, -0.01 + 0.03j],
            "2,1": [0.5, 0.4 + 0.1j, 0.3],
            "1,2": [0.5, 0.4 + 0.1j, 0.3],
            "2,2": [0.1, 0.05, 0.02],
        }
        raw = self.worker.build_planar_raw(case, "2.8.9", case["frequencies_hz"], s_params,
                                           {"nodes": 10, "tetrahedra": 5}, 1.25)
        json.dumps(raw, allow_nan=False)
        self.assertEqual(raw["trace_count"], len(case["traces"]))
        result = fem.assess_planar(raw, case)
        self.assertEqual(result["status"], "results_exported")
        self.assertEqual(result["mesh"], {"nodes": 10, "tetrahedra": 5})
        self.assertEqual(result["s"]["2,1"]["re"][0], 0.5)
        self.assertEqual(self.worker.ABC_ORDER, 2)
        self.assertEqual(self.worker.ABC_TYPE, "B")


if __name__ == "__main__":
    unittest.main()
