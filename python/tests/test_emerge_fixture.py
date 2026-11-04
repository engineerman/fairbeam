"""EMerge fixture adapter contracts; EMerge is never installed, imported or run in this test suite."""
import ast
import cmath
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fairbeam_emerge as fem

FROZEN = {"coarse": 0.012, "fine": 0.006}  # test-only stand-ins until Task 4 freezes the real values
NATIVE_PLUS = "exp(+i omega t)"
NATIVE_MINUS = "exp(-i omega t)"


def fake_venv(root, version="2.8.9", posix=False):
    """Create a minimal venv-shaped folder; nothing in it is executable."""
    root = Path(root)
    if posix:
        exe = root / "bin" / "python"
        site = root / "lib" / "python3.13" / "site-packages"
    else:
        exe = root / "Scripts" / "python.exe"
        site = root / "Lib" / "site-packages"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"not a real interpreter")
    site.mkdir(parents=True)
    if version:
        info = site / f"emerge-{version}.dist-info"
        info.mkdir()
        (info / "METADATA").write_text(f"Metadata-Version: 2.4\nName: emerge\nVersion: {version}\n", encoding="utf-8")
    # An unrelated distribution whose name starts like ours must never be read as EMerge.
    other = site / "emsutil-0.8.3.dist-info"
    other.mkdir()
    (other / "METADATA").write_text("Name: emsutil\nVersion: 0.8.3\n", encoding="utf-8")
    return exe, site


def synthetic_raw(convention=NATIVE_PLUS, s11=0.0, flip=False):
    """Raw worker output built from the analytic reference (synthetic, not a solver result)."""
    s21 = [fem.analytic(f) for f in fem.FREQUENCIES_HZ]
    if flip:
        s21 = [v.conjugate() for v in s21]
    if convention == NATIVE_MINUS:
        s21 = [v.conjugate() for v in s21]
    return {"emerge_version": "2.8.9", "frequency_hz": list(fem.FREQUENCIES_HZ),
            "s11_re": [s11] * 5, "s11_im": [0.0] * 5,
            "s21_re": [v.real for v in s21], "s21_im": [v.imag for v in s21],
            "phasor_convention": convention, "elapsed_seconds": 1.5}


class Discovery(unittest.TestCase):
    def test_discover_venv_folder_windows_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, site = fake_venv(directory)
            python, found = fem.discover(directory)
            self.assertEqual(python, exe.resolve())
            self.assertEqual(found, site.resolve())

    def test_discover_venv_folder_posix_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, site = fake_venv(directory, posix=True)
            python, found = fem.discover(directory)
            self.assertEqual(python, exe.resolve())
            self.assertEqual(found, site.resolve())

    def test_discover_python_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, site = fake_venv(directory)
            python, found = fem.discover(exe)
            self.assertEqual((python, found), (exe.resolve(), site.resolve()))

    def test_discover_env_variable(self):
        with tempfile.TemporaryDirectory() as directory:
            exe, _ = fake_venv(directory)
            with patch.dict(os.environ, {"FAIRBEAM_EMERGE_PYTHON": directory}):
                self.assertEqual(fem.discover()[0], exe.resolve())

    def test_discover_without_root_does_not_search_path(self):
        env = {k: v for k, v in os.environ.items() if k != "FAIRBEAM_EMERGE_PYTHON"}
        with patch.dict(os.environ, env, clear=True), patch.object(fem.subprocess, "run") as launch:
            with self.assertRaisesRegex(FileNotFoundError, "FAIRBEAM_EMERGE_PYTHON"):
                fem.discover()
            launch.assert_not_called()

    def test_discover_missing_python_and_site_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                fem.discover(directory)
            exe, site = fake_venv(Path(directory) / "v")
            shutil.rmtree(site)
            with self.assertRaisesRegex(FileNotFoundError, "site-packages"):
                fem.discover(Path(directory) / "v")

    def test_emerge_version_parses_metadata_only(self):
        with tempfile.TemporaryDirectory() as directory:
            _, site = fake_venv(directory)
            with patch.object(fem.subprocess, "run") as launch:
                self.assertEqual(fem.emerge_version(site), "2.8.9")
                launch.assert_not_called()

    def test_emerge_version_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            _, site = fake_venv(directory, version=None)
            self.assertIsNone(fem.emerge_version(site))

    def test_capabilities_available_has_hash_and_no_execution(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(fem.subprocess, "run") as launch:
            exe, _ = fake_venv(directory)
            caps = fem.capabilities(directory)
            launch.assert_not_called()
        self.assertTrue(caps["available"])
        self.assertEqual(caps["backend"], "emerge-experimental")
        self.assertEqual(caps["physics"], ["wr90_waveguide_fixture"])
        self.assertEqual(caps["emerge_version"], "2.8.9")
        self.assertTrue(caps["version_supported"])
        self.assertEqual(caps["python"], str(exe.resolve()))
        self.assertEqual(len(caps["python_sha256"]), 64)
        for key in ("driven_ports", "design_translation", "probe_executes_solver", "probe_executes_interpreter"):
            self.assertIs(caps[key], False)

    def test_capabilities_unsupported_version(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_venv(directory, version="2.8.8")
            caps = fem.capabilities(directory)
        self.assertTrue(caps["available"])
        self.assertFalse(caps["version_supported"])

    def test_capabilities_unavailable_gives_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            caps = fem.capabilities(directory)
            self.assertFalse(caps["available"])
            self.assertTrue(caps["reason"])
            fake_venv(Path(directory) / "v", version=None)
            caps = fem.capabilities(Path(directory) / "v")
            self.assertFalse(caps["available"])
            self.assertIn("EMerge", caps["reason"])


class Fixture(unittest.TestCase):
    def test_constants_match_plan(self):
        self.assertEqual((fem.A_M, fem.B_M, fem.L_M), (0.02286, 0.01016, 0.05))
        self.assertEqual(fem.FREQUENCIES_HZ, (8e9, 9e9, 10e9, 11e9, 12e9))
        self.assertEqual(fem.SUPPORTED_EMERGE, ("2.8.9",))
        self.assertEqual(set(fem.RESOLUTIONS), {"coarse", "fine"})
        self.assertEqual(fem.CRITERIA, {"s11_max": 0.02, "s21_min": 0.995,
                                        "phase_error_deg_max": 2.0, "passivity_max": 1.005})

    def test_validate_case_accepts_only_known_resolutions(self):
        with patch.dict(fem.RESOLUTIONS, FROZEN):
            fem.validate_case("coarse")
            fem.validate_case("fine")
            for bad in ("medium", "", None, 0.01, ["coarse"]):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    fem.validate_case(bad)

    def test_validate_case_rejects_unfrozen_resolution(self):
        with patch.dict(fem.RESOLUTIONS, {"coarse": None, "fine": None}):
            with self.assertRaisesRegex(ValueError, "not yet frozen"):
                fem.validate_case("coarse")

    def test_case_dict_is_the_fixed_fixture(self):
        with patch.dict(fem.RESOLUTIONS, FROZEN):
            case = fem.case("fine")
        self.assertEqual(case["resolution"], {"name": "fine", "value": 0.006})
        self.assertEqual(case["frequency_hz"], list(fem.FREQUENCIES_HZ))
        self.assertEqual(case["geometry"]["a_m"], fem.A_M)
        self.assertEqual(case["geometry"]["b_m"], fem.B_M)
        self.assertEqual(case["geometry"]["length_m"], fem.L_M)
        self.assertEqual([p["face_z_m"] for p in case["ports"]], [0.0, fem.L_M])
        self.assertEqual(case["phasor_convention_out"], NATIVE_PLUS)
        json.dumps(case, allow_nan=False)

    def test_analytic_reference(self):
        c0 = 299792458.0
        for f in fem.FREQUENCIES_HZ:
            k0 = 2 * math.pi * f / c0
            beta = math.sqrt(k0 ** 2 - (math.pi / fem.A_M) ** 2)
            expected = cmath.exp(-1j * beta * fem.L_M)
            self.assertAlmostEqual(abs(fem.analytic(f) - expected), 0.0, places=12)
            self.assertAlmostEqual(abs(fem.analytic(f)), 1.0, places=12)
        # TE10 cutoff is 6.557 GHz; below it there is no propagating mode.
        with self.assertRaises(ValueError):
            fem.analytic(6e9)


class Assess(unittest.TestCase):
    def test_passes_on_analytic_reference(self):
        result = fem.assess(synthetic_raw())
        self.assertEqual(result["schema"], "fairbeam.emerge-fixture-result/1")
        self.assertEqual(result["status"], "results_validated")
        self.assertEqual(result["frequency_hz"], list(fem.FREQUENCIES_HZ))
        self.assertEqual(result["criteria"], fem.CRITERIA)
        self.assertEqual(result["phasor_convention"], NATIVE_PLUS)
        self.assertEqual(result["native_phasor_convention"], NATIVE_PLUS)
        self.assertIs(result["precision_converged"], False)
        self.assertIs(result["qualifies_driven_antenna"], False)
        self.assertTrue(result["limitations"])
        self.assertEqual(len(result["analytic_s21_re"]), 5)
        metrics = result["metrics"]
        self.assertAlmostEqual(metrics["s11_max"], 0.0)
        self.assertAlmostEqual(metrics["s21_min"], 1.0)
        self.assertAlmostEqual(metrics["phase_error_deg_max"], 0.0, places=6)
        self.assertAlmostEqual(metrics["passivity_max"], 1.0)
        json.dumps(result, allow_nan=False)

    def test_fails_on_reflection(self):
        result = fem.assess(synthetic_raw(s11=0.3))
        self.assertEqual(result["status"], "validation_failed")
        self.assertAlmostEqual(result["metrics"]["s11_max"], 0.3)

    def test_fails_on_low_transmission(self):
        raw = synthetic_raw()
        raw["s21_re"] = [v * 0.9 for v in raw["s21_re"]]
        raw["s21_im"] = [v * 0.9 for v in raw["s21_im"]]
        self.assertEqual(fem.assess(raw)["status"], "validation_failed")

    def test_fails_on_passivity(self):
        raw = synthetic_raw(s11=0.015)  # |S11|^2 + |S21|^2 = 1.000225 -> still passive
        self.assertEqual(fem.assess(raw)["status"], "results_validated")
        raw["s21_re"] = [v * 1.1 for v in raw["s21_re"]]
        raw["s21_im"] = [v * 1.1 for v in raw["s21_im"]]
        self.assertEqual(fem.assess(raw)["status"], "validation_failed")

    def test_phase_sign_flip_fails_under_declared_convention(self):
        result = fem.assess(synthetic_raw(flip=True))
        self.assertEqual(result["status"], "validation_failed")
        self.assertGreater(result["metrics"]["phase_error_deg_max"], fem.CRITERIA["phase_error_deg_max"])

    def test_native_minus_convention_is_conjugated_once(self):
        result = fem.assess(synthetic_raw(convention=NATIVE_MINUS))
        self.assertEqual(result["status"], "results_validated")
        self.assertEqual(result["native_phasor_convention"], NATIVE_MINUS)
        self.assertEqual(result["phasor_convention"], NATIVE_PLUS)
        analytic = [fem.analytic(f) for f in fem.FREQUENCIES_HZ]
        for got_re, got_im, want in zip(result["s21_re"], result["s21_im"], analytic):
            self.assertAlmostEqual(complex(got_re, got_im), want, places=9)

    def test_phase_error_is_wrapped(self):
        raw = synthetic_raw()
        turn = cmath.exp(1j * math.radians(358))  # -2 degrees, not 358
        s21 = [complex(r, i) * turn for r, i in zip(raw["s21_re"], raw["s21_im"])]
        raw["s21_re"], raw["s21_im"] = [v.real for v in s21], [v.imag for v in s21]
        result = fem.assess(raw)
        self.assertAlmostEqual(result["metrics"]["phase_error_deg_max"], 2.0, places=6)
        self.assertEqual(result["status"], "results_validated")

    def test_rejects_bad_raw(self):
        def mutate(change):
            raw = synthetic_raw()
            change(raw)
            return raw
        cases = {
            "nan": mutate(lambda r: r["s21_re"].__setitem__(2, math.nan)),
            "inf": mutate(lambda r: r["s11_im"].__setitem__(0, math.inf)),
            "string": mutate(lambda r: r["s21_im"].__setitem__(0, "0.5")),
            "bool": mutate(lambda r: r["s21_im"].__setitem__(0, True)),
            "wrong frequencies": mutate(lambda r: r.update(frequency_hz=[8e9, 9e9, 10e9, 11e9, 13e9])),
            "reordered frequencies": mutate(lambda r: r.update(frequency_hz=list(reversed(fem.FREQUENCIES_HZ)))),
            "short frequencies": mutate(lambda r: r.update(frequency_hz=[8e9])),
            "unequal lengths": mutate(lambda r: r.update(s11_re=[0.0] * 4)),
            "unknown convention": mutate(lambda r: r.update(phasor_convention="exp(jwt)")),
            "missing convention": mutate(lambda r: r.pop("phasor_convention")),
            "missing key": mutate(lambda r: r.pop("s21_im")),
            "not a dict": [],
        }
        for name, raw in cases.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                fem.assess(raw)

    def test_carries_solver_context_when_present(self):
        raw = synthetic_raw()
        raw["mesh"] = {"nodes": 100, "tetrahedra": 400}
        result = fem.assess(raw)
        self.assertEqual(result["emerge_version"], "2.8.9")
        self.assertEqual(result["mesh"], {"nodes": 100, "tetrahedra": 400})
        self.assertEqual(result["elapsed_seconds"], 1.5)


class RunFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.exe, _ = fake_venv(self.root / "venv")
        self.worker = self.root / "fairbeam_emerge_worker.py"
        self.worker.write_text("# stand-in worker\n", encoding="utf-8")
        for p in (patch.dict(fem.RESOLUTIONS, FROZEN), patch.object(fem, "WORKER", self.worker)):
            p.start()
            self.addCleanup(p.stop)

    def run_with(self, process=None, side_effect=None, **kwargs):
        kwargs.setdefault("root", self.root / "venv")
        kwargs.setdefault("experimental", True)
        with patch.object(fem.subprocess, "run", return_value=process, side_effect=side_effect) as launch:
            try:
                return fem.run_fixture(self.root / "run", **kwargs), launch
            finally:
                self.launch = launch

    def manifest(self):
        return json.loads((self.root / "run" / "manifest.json").read_text(encoding="utf-8"))

    def test_requires_opt_in_before_discovery_or_output(self):
        with patch.object(fem, "discover") as discover:
            with self.assertRaisesRegex(ValueError, "opt-in"):
                fem.run_fixture(self.root / "run", root=self.root / "venv")
            discover.assert_not_called()
        self.assertFalse((self.root / "run").exists())

    def test_unknown_resolution_creates_nothing(self):
        with self.assertRaises(ValueError):
            fem.run_fixture(self.root / "run", root=self.root / "venv", resolution="medium", experimental=True)
        self.assertFalse((self.root / "run").exists())

    def test_existing_output_directory_is_not_overwritten(self):
        (self.root / "run").mkdir()
        with self.assertRaises(FileExistsError):
            fem.run_fixture(self.root / "run", root=self.root / "venv", experimental=True)

    def test_missing_environment_creates_nothing(self):
        with self.assertRaises(FileNotFoundError):
            fem.run_fixture(self.root / "run", root=self.root / "nowhere", experimental=True)
        self.assertFalse((self.root / "run").exists())

    def test_non_zero_exit_keeps_log_and_failed_manifest(self):
        process = subprocess.CompletedProcess([], 3, "worker said no")
        with self.assertRaisesRegex(RuntimeError, "worker.log"):
            self.run_with(process)
        self.assertEqual(self.manifest()["status"], "failed")
        self.assertEqual(self.manifest()["worker_exit_code"], 3)
        self.assertEqual((self.root / "run" / "worker.log").read_text(), "worker said no")

    def test_timeout_keeps_partial_log(self):
        timeout = subprocess.TimeoutExpired([], fem.WORKER_TIMEOUT_S, output=b"partial native output")
        with self.assertRaisesRegex(RuntimeError, "600 second"):
            self.run_with(side_effect=timeout)
        self.assertEqual((self.root / "run" / "worker.log").read_text(), "partial native output")
        self.assertEqual(self.manifest()["status"], "failed")

    def test_zero_exit_without_raw_json_fails(self):
        with self.assertRaisesRegex(RuntimeError, "raw.json"):
            self.run_with(subprocess.CompletedProcess([], 0, "ok"))
        self.assertEqual(self.manifest()["status"], "failed")
        self.assertEqual((self.root / "run" / "worker.log").read_text(), "ok")

    def test_launch_is_isolated_and_single_threaded(self):
        with self.assertRaises(RuntimeError):
            self.run_with(subprocess.CompletedProcess([], 1, ""))
        args, kwargs = self.launch.call_args
        self.assertEqual(args[0], [str(self.exe.resolve()), "-I", "-X", "utf8",
                                   "fairbeam_emerge_worker.py", "case.json"])
        self.assertEqual(Path(kwargs["cwd"]), (self.root / "run").resolve())
        self.assertEqual(kwargs["timeout"], 600)
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        env = kwargs["env"]
        for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMBA_NUM_THREADS"):
            self.assertEqual(env[name], "1")
        self.assertEqual(env["MPLBACKEND"], "Agg")
        self.assertEqual(env["PYVISTA_OFF_SCREEN"], "true")
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("PYTHONHOME", env)

    def test_launch_strips_inherited_python_variables(self):
        with patch.dict(os.environ, {"PYTHONPATH": "x", "PYTHONHOME": "y"}):
            with self.assertRaises(RuntimeError):
                self.run_with(subprocess.CompletedProcess([], 1, ""))
        env = self.launch.call_args.kwargs["env"]
        self.assertNotIn("PYTHONPATH", env)
        self.assertNotIn("PYTHONHOME", env)

    def worker_writes(self, raw):
        def fake(*args, **kwargs):
            Path(kwargs["cwd"], "raw.json").write_text(json.dumps(raw), encoding="utf-8")
            return subprocess.CompletedProcess(args[0], 0, "worker log")
        return fake

    def test_success_writes_result_manifest_and_provenance(self):
        result, _ = self.run_with(side_effect=self.worker_writes(synthetic_raw()))
        self.assertEqual(result["status"], "results_validated")
        run = self.root / "run"
        self.assertEqual(json.loads((run / "result.json").read_text())["status"], "results_validated")
        self.assertEqual((run / "fairbeam_emerge_worker.py").read_text(), "# stand-in worker\n")
        self.assertEqual(json.loads((run / "case.json").read_text())["resolution"]["name"], "coarse")
        manifest = self.manifest()
        self.assertEqual(manifest["schema"], "fairbeam-emerge-fixture-1")
        self.assertEqual(manifest["status"], "results_validated")
        self.assertEqual(manifest["emerge_version"], "2.8.9")
        for key in ("worker_sha256", "case_sha256", "python_sha256", "generator_sha256"):
            self.assertEqual(len(manifest[key]), 64, key)
        self.assertEqual(manifest["worker_exit_code"], 0)
        self.assertEqual((run / "worker.log").read_text(), "worker log")

    def test_failed_validation_keeps_raw_and_raises(self):
        with self.assertRaisesRegex(ValueError, "criteria"):
            self.run_with(side_effect=self.worker_writes(synthetic_raw(s11=0.4)))
        run = self.root / "run"
        self.assertTrue((run / "raw.json").exists())
        self.assertEqual(json.loads((run / "result.json").read_text())["status"], "validation_failed")
        self.assertEqual(self.manifest()["status"], "validation_failed")

    def test_malformed_raw_marks_failed(self):
        raw = synthetic_raw()
        raw["s21_re"][0] = "x"
        with self.assertRaises(ValueError):
            self.run_with(side_effect=self.worker_writes(raw))
        self.assertEqual(self.manifest()["status"], "failed")
        self.assertTrue((self.root / "run" / "raw.json").exists())

    def test_keyboard_interrupt_marks_interrupted(self):
        with self.assertRaises(KeyboardInterrupt):
            self.run_with(side_effect=KeyboardInterrupt())
        self.assertEqual(self.manifest()["status"], "interrupted")

    def test_status_progression_is_saved(self):
        seen = []
        original = fem.json.dumps

        def spy(obj, *a, **k):
            if isinstance(obj, dict) and obj.get("schema") == "fairbeam-emerge-fixture-1":
                seen.append(obj["status"])
            return original(obj, *a, **k)
        with patch.object(fem.json, "dumps", spy):
            self.run_with(side_effect=self.worker_writes(synthetic_raw()))
        self.assertEqual(seen, ["inputs_generated", "solver_started", "solver_returned", "results_validated"])


class Cli(unittest.TestCase):
    def test_capabilities_command(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_venv(directory)
            with patch("builtins.print") as out:
                self.assertEqual(fem.main(["--root", directory, "capabilities"]), 0)
            self.assertTrue(json.loads(out.call_args.args[0])["available"])

    def test_waveguide_requires_experimental_and_exits_2(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(SystemExit) as raised:
            with patch("sys.stderr"):
                fem.main(["waveguide", "--out", str(Path(directory) / "run")])
        self.assertEqual(raised.exception.code, 2)

    def test_waveguide_rejects_unknown_resolution(self):
        with self.assertRaises(SystemExit), patch("sys.stderr"):
            fem.main(["waveguide", "--experimental", "--out", "x", "--resolution", "medium"])


class Isolation(unittest.TestCase):
    FORBIDDEN = {"fairbeam", "emerge", "emsutil", "numpy", "scipy", "gmsh", "numba", "CSXCAD", "openEMS"}

    def test_adapter_imports_stdlib_only(self):
        source = Path(fem.__file__).read_text(encoding="utf-8")
        found = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "relative imports would reach into fairbeam")
                found.add((node.module or "").split(".")[0])
        self.assertFalse(found & self.FORBIDDEN, found & self.FORBIDDEN)
        self.assertTrue(found <= set(sys.stdlib_module_names), found - set(sys.stdlib_module_names))

    def test_import_loads_no_solver_modules(self):
        script = ("import sys; import fairbeam_emerge; "
                  "assert not {'fairbeam','openEMS','CSXCAD','emerge','numpy','gmsh'} & set(sys.modules)")
        subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1], check=True)


WORKER_PATH = Path(fem.__file__).with_name("fairbeam_emerge_worker.py")


class WorkerIsolation(unittest.TestCase):
    """The worker is the only file that may import EMerge, and only inside the EMerge environment."""

    @staticmethod
    def imports(tree):
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.extend((alias.name.split(".")[0], node) for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0, "relative imports would reach into fairbeam"
                found.append(((node.module or "").split(".")[0], node))
        return found

    def test_worker_does_not_import_fairbeam(self):
        tree = ast.parse(WORKER_PATH.read_text(encoding="utf-8"))
        names = {name for name, _ in self.imports(tree)}
        self.assertNotIn("fairbeam", names)
        self.assertNotIn("fairbeam_emerge", names)
        self.assertTrue(names <= set(sys.stdlib_module_names) | {"numpy", "emerge"}, names)

    def test_emerge_and_numpy_are_imported_only_inside_functions(self):
        tree = ast.parse(WORKER_PATH.read_text(encoding="utf-8"))
        top_level = {name for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
                     for name, _ in self.imports(node)}
        self.assertFalse(top_level & {"numpy", "emerge"}, top_level)

    def test_importing_the_worker_loads_no_solver_modules(self):
        script = ("import sys; import fairbeam_emerge_worker; "
                  "assert not {'fairbeam','emerge','numpy','gmsh'} & set(sys.modules)")
        subprocess.run([sys.executable, "-c", script], cwd=WORKER_PATH.parent, check=True)


class WorkerContract(unittest.TestCase):
    """Pure helpers of the worker; the EMerge API calls are exercised in Task 5."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        spec = importlib.util.spec_from_file_location("fairbeam_emerge_worker", WORKER_PATH)
        cls.worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.worker)

    def case_path(self, directory, mutate=None):
        case = fem.case("coarse")
        if mutate:
            mutate(case)
        path = Path(directory) / "case.json"
        path.write_text(json.dumps(case), encoding="utf-8")
        return path

    def test_worker_accepts_the_adapter_case(self):
        with tempfile.TemporaryDirectory() as directory:
            case = self.worker.load_case(self.case_path(directory))
        self.assertEqual(case["frequency_hz"], list(fem.FREQUENCIES_HZ))
        self.assertEqual(case["resolution"]["value"], fem.RESOLUTIONS["coarse"])

    def test_both_frozen_resolutions_are_valid_and_fine_is_twice_as_fine(self):
        self.assertAlmostEqual(fem.RESOLUTIONS["coarse"] / fem.RESOLUTIONS["fine"], 2.0)
        for name in fem.RESOLUTIONS:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "case.json"
                path.write_text(json.dumps(fem.case(name)), encoding="utf-8")
                self.worker.load_case(path)

    def test_worker_rejects_changed_cases(self):
        changes = {
            "schema": lambda c: c.update(schema="other"),
            "fill": lambda c: c["geometry"]["fill"].update(eps_r=2.0),
            "walls": lambda c: c["geometry"].update(walls="PMC"),
            "unsorted frequencies": lambda c: c.update(frequency_hz=[9e9, 8e9]),
            "non-finite frequency": lambda c: c.update(frequency_hz=[8e9, float("inf")]),
            "one port": lambda c: c.update(ports=c["ports"][:1]),
            "port mode": lambda c: c["ports"][0].update(mode="TE20"),
            "port plane": lambda c: c["ports"][1].update(face_z_m=0.01),
            "resolution too coarse": lambda c: c["resolution"].update(value=0.9),
            "convention": lambda c: c.update(phasor_convention_out="exp(-i omega t)"),
        }
        for name, mutate in changes.items():
            with self.subTest(name), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    self.worker.load_case(self.case_path(directory, mutate))

    def test_match_frequencies_is_strict_and_returns_case_values(self):
        expected = list(fem.FREQUENCIES_HZ)
        nudged = [f * (1 + 1e-12) for f in expected]
        self.assertEqual(self.worker.match_frequencies(expected, nudged), expected)
        with self.assertRaises(ValueError):
            self.worker.match_frequencies(expected, [f * (1 + 1e-6) for f in expected])
        with self.assertRaises(ValueError):
            self.worker.match_frequencies(expected, expected[:-1])
        with self.assertRaises(ValueError):
            self.worker.match_frequencies(expected, expected[:-1] + [float("nan")])

    def synthetic(self):
        s21 = [fem.analytic(f) for f in fem.FREQUENCIES_HZ]
        return list(fem.FREQUENCIES_HZ), [0j] * 5, s21

    def test_build_raw_round_trips_through_the_adapter_assessment(self):
        frequencies, s11, s21 = self.synthetic()  # synthetic data, not a solver result
        with tempfile.TemporaryDirectory() as directory:
            case = self.worker.load_case(self.case_path(directory))
        raw = self.worker.build_raw(case, "2.8.9", [f * (1 + 1e-12) for f in frequencies], s11, s21,
                                    {"nodes": 10, "tetrahedra": 5}, 1.5)
        json.dumps(raw, allow_nan=False)
        self.assertEqual(raw["phasor_convention"], NATIVE_PLUS)
        self.assertEqual(raw["frequency_hz"], list(fem.FREQUENCIES_HZ))
        result = fem.assess(raw)
        self.assertEqual(result["status"], "results_validated")
        self.assertEqual(result["mesh"], {"nodes": 10, "tetrahedra": 5})

    def test_build_raw_rejects_non_finite_and_short_series(self):
        frequencies, s11, s21 = self.synthetic()
        with tempfile.TemporaryDirectory() as directory:
            case = self.worker.load_case(self.case_path(directory))
        with self.assertRaises(ValueError):
            self.worker.build_raw(case, "2.8.9", frequencies, s11, s21[:-1] + [complex("nan")], None, 1.0)
        with self.assertRaises(ValueError):
            self.worker.build_raw(case, "2.8.9", frequencies, s11[:-1], s21, None, 1.0)


if __name__ == "__main__":
    unittest.main()
