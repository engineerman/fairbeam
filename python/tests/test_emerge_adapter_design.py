"""EMerge Design adapter contracts; EMerge is never installed, imported or run in this suite."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fairbeam_emerge as fem
from test_emerge_fixture import fake_venv

NATIVE = "exp(+i omega t)"


def sample_case(**overrides):
    """Minimal admitted design case (metres); synthetic, not from a live admit call."""
    case = {
        "kind": "design",
        "boxes": [{"lo": [0.0, 0.0, 0.0], "hi": [0.04, 0.04, 0.0016],
                   "eps_r": 3.38, "mu_r": 1.0, "tan_d": 0.0027}],
        "sheets": [
            {"lo": [0.005, 0.005, 0.0016], "hi": [0.035, 0.035, 0.0016], "normal_axis": 2},
            {"lo": [0.0, 0.0, 0.0], "hi": [0.04, 0.04, 0.0], "normal_axis": 2},
        ],
        "port": {"lo": [0.0195, 0.02, 0.0], "hi": [0.0205, 0.02, 0.0016],
                 "direction_axis": 2, "sign": 1, "width": 0.001, "height": 0.0016, "z0": 50.0},
        "air": {"lo": [-0.04, -0.04, -0.04], "hi": [0.08, 0.08, 0.0416]},
        "frequencies_hz": [2.0e9, 2.5e9, 3.0e9],
        "resolution": 0.25,
        "resolution_name": "coarse",
        "phasor_convention_out": NATIVE,
        "limitations": ["Finite rectangular feed replaces ideal line only in this FEM run."],
        "pec_approximations": [],
    }
    case.update(overrides)
    return case


def synthetic_raw(case=None, *, s11=0.1, convention=NATIVE, frequencies=None):
    case = case or sample_case()
    frequencies = list(frequencies if frequencies is not None else case["frequencies_hz"])
    n = len(frequencies)
    return {"kind": "design", "emerge_version": "3.0.0b12", "frequency_hz": frequencies,
            "s11_re": [s11] * n, "s11_im": [0.0] * n, "z_ref": case["port"]["z0"],
            "phasor_convention": convention, "native_phasor_convention": convention,
            "elapsed_seconds": 2.5,
            "mesh": {"nodes": 100, "tetrahedra": 400},
            "limitations": list(case["limitations"]),
            "pec_approximations": list(case["pec_approximations"])}


class DesignCaseOk(unittest.TestCase):
    def test_accepts_sample_case(self):
        self.assertTrue(fem.design_case_ok(sample_case()))

    def test_rejects_wrong_kind_and_convention(self):
        with self.assertRaisesRegex(ValueError, "kind"):
            fem.design_case_ok(sample_case(kind="fixture"))
        with self.assertRaisesRegex(ValueError, "phasor_convention_out"):
            fem.design_case_ok(sample_case(phasor_convention_out="exp(-i omega t)"))


class AssessDesign(unittest.TestCase):
    def test_exports_results_without_validating(self):
        case = sample_case()
        result = fem.assess_design(synthetic_raw(case), case)
        self.assertEqual(result["schema"], fem.DESIGN_RESULT_SCHEMA)
        self.assertEqual(result["status"], "results_exported")
        self.assertFalse(result["precision_converged"])
        self.assertFalse(result["gain_qualified"])
        self.assertEqual(result["phasor_convention"], NATIVE)
        self.assertEqual(result["native_phasor_convention"], NATIVE)
        self.assertEqual(result["z_ref"], 50.0)
        self.assertEqual(result["mesh"], {"nodes": 100, "tetrahedra": 400})
        self.assertEqual(result["settings"]["resolution"], 0.25)

    def test_rejects_wrong_frequencies(self):
        case = sample_case()
        with self.assertRaisesRegex(ValueError, "frequencies"):
            fem.assess_design(synthetic_raw(case, frequencies=[2e9, 2.1e9, 3e9]), case)

    def test_rejects_non_finite(self):
        case = sample_case()
        raw = synthetic_raw(case)
        raw["s11_re"][1] = float("nan")
        with self.assertRaisesRegex(ValueError, "s11_re"):
            fem.assess_design(raw, case)

    def test_rejects_s11_above_bound(self):
        case = sample_case()
        with self.assertRaisesRegex(ValueError, r"\|S11\|"):
            fem.assess_design(synthetic_raw(case, s11=1.02), case)

    def test_rejects_wrong_convention(self):
        case = sample_case()
        with self.assertRaisesRegex(ValueError, "phasor_convention"):
            fem.assess_design(synthetic_raw(case, convention="exp(-i omega t)"), case)

    def test_accepts_s11_at_elmer_bound(self):
        case = sample_case()
        result = fem.assess_design(synthetic_raw(case, s11=1.01), case)
        self.assertEqual(result["status"], "results_exported")
        self.assertAlmostEqual(abs(complex(result["s11_re"][0], result["s11_im"][0])), 1.01)


class RunDesign(unittest.TestCase):
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
                return fem.run_design(self.root / "run", self.case, **kwargs), launch
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
                fem.run_design(self.root / "run", self.case, root=self.root / "venv")
            discover.assert_not_called()
        self.assertFalse((self.root / "run").exists())

    def test_existing_output_directory_is_not_overwritten(self):
        (self.root / "run").mkdir()
        with self.assertRaises(FileExistsError):
            fem.run_design(self.root / "run", self.case, root=self.root / "venv", experimental=True)

    def test_non_zero_exit_keeps_log_and_failed_manifest(self):
        process = subprocess.CompletedProcess([], 3, "worker said no")
        with self.assertRaisesRegex(RuntimeError, "worker.log"):
            self.run_with(process)
        self.assertEqual(self.manifest()["status"], "failed")
        self.assertEqual(self.manifest()["worker_exit_code"], 3)
        self.assertEqual((self.root / "run" / "worker.log").read_text(), "worker said no")

    def test_timeout_keeps_partial_log(self):
        timeout = subprocess.TimeoutExpired([], fem.DESIGN_WORKER_TIMEOUT_S, output=b"partial native output")
        with self.assertRaisesRegex(RuntimeError, "1800 second"):
            self.run_with(side_effect=timeout)
        self.assertEqual((self.root / "run" / "worker.log").read_text(), "partial native output")
        self.assertEqual(self.manifest()["status"], "failed")

    def test_launch_uses_design_timeout_and_isolation(self):
        with self.assertRaises(RuntimeError):
            self.run_with(subprocess.CompletedProcess([], 1, ""))
        args, kwargs = self.launch.call_args
        self.assertEqual(args[0], [str(self.exe.resolve()), "-I", "-X", "utf8",
                                   "fairbeam_emerge_worker.py", "case.json"])
        self.assertEqual(kwargs["timeout"], 1800)
        env = kwargs["env"]
        nthreads = str(self.case.get("nthreads") or fem.default_nthreads())
        for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMBA_NUM_THREADS"):
            self.assertEqual(env[name], nthreads)
        self.assertNotIn("PYTHONPATH", env)
        self.assertEqual(self.manifest()["threads"], int(nthreads))

    def test_success_writes_exported_result(self):
        result, _ = self.run_with(side_effect=self.worker_writes(synthetic_raw(self.case)))
        self.assertEqual(result["status"], "results_exported")
        run = self.root / "run"
        written = json.loads((run / "case.json").read_text(encoding="utf-8"))
        self.assertEqual(written["kind"], "design")
        self.assertEqual(json.loads((run / "result.json").read_text())["status"], "results_exported")
        manifest = self.manifest()
        self.assertEqual(manifest["schema"], fem.DESIGN_MANIFEST_SCHEMA)
        self.assertEqual(manifest["status"], "results_exported")
        self.assertEqual((run / "worker.log").read_text(), "worker log")

    def test_malformed_raw_marks_failed(self):
        raw = synthetic_raw(self.case, s11=1.5)
        with self.assertRaises(ValueError):
            self.run_with(side_effect=self.worker_writes(raw))
        self.assertEqual(self.manifest()["status"], "failed")
        self.assertTrue((self.root / "run" / "raw.json").exists())


class DesignWorkerContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util
        path = Path(fem.__file__).with_name("fairbeam_emerge_worker.py")
        spec = importlib.util.spec_from_file_location("fairbeam_emerge_worker", path)
        cls.worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.worker)

    def test_load_case_accepts_design(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.json"
            path.write_text(json.dumps(sample_case()), encoding="utf-8")
            case = self.worker.load_case(path)
        self.assertEqual(case["kind"], "design")
        self.assertEqual(len(case["frequencies_hz"]), 3)

    def test_load_case_rejects_bad_design(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "case.json"
            bad = sample_case(frequencies_hz=[3e9, 2e9])
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                self.worker.load_case(path)

    def test_build_design_raw_round_trips(self):
        case = sample_case()
        s11 = [0.1 + 0.2j, 0.05, -0.01 + 0.03j]
        raw = self.worker.build_design_raw(case, "3.0.0b12", case["frequencies_hz"], s11,
                                           {"nodes": 10, "tetrahedra": 5}, 1.25)
        json.dumps(raw, allow_nan=False)
        result = fem.assess_design(raw, case)
        self.assertEqual(result["status"], "results_exported")
        self.assertEqual(result["mesh"], {"nodes": 10, "tetrahedra": 5})
        self.assertEqual(self.worker.ABC_ORDER, 2)
        self.assertEqual(self.worker.ABC_TYPE, "B")


if __name__ == "__main__":
    unittest.main()
