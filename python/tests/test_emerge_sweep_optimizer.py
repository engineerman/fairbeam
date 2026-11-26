"""EMerge parameter sweep and optimizer admission. EMerge is never installed or run here."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from fairbeam import research
from fairbeam.design import blank_design
from fairbeam.jobs import JobManager
from fairbeam.server import ApiError, App

from test_emerge_fixture import fake_venv
from test_emerge_research import HAIRPIN, design_settings, emerge_nport_result, planar_settings


def _default(design, key):
    return next(p["default"] for p in design["params"] if p["key"] == key)


def _box_heights(spec):
    return [box["hi"][2] - box["lo"][2] for box in spec["normalized"]["boxes"]]


class EmergeParamOverrides(unittest.TestCase):
    def _venv(self, directory):
        exe, site = fake_venv(directory)
        record = site / "emerge-3.0.0b12.dist-info" / "RECORD"
        record.write_text("emerge/__init__.py,sha256=abc,10\n", encoding="utf-8")
        return exe

    def test_prepare_without_overrides_matches_fixture_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            self._venv(directory)
            design = json.loads(HAIRPIN.read_text(encoding="utf-8"))
            spec = research.prepare({
                "backend": "emerge", "path": directory, "design": design,
                "settings": planar_settings()})
            self.assertEqual(spec["backend"], "emerge")
            self.assertEqual(spec["normalized"]["kind"], "planar")
            self.assertEqual(len(spec["normalized"]["terminals"]), 2)
            self.assertEqual(spec["normalized"]["enclosure"], "shielded")
            self.assertNotIn("param_overrides", spec)
            self.assertEqual(_default(spec["design"], "sub_h"), 1.6)
            empty = research.prepare({
                "backend": "emerge", "path": directory, "design": design,
                "settings": planar_settings(), "param_overrides": {}})
            self.assertEqual(empty["normalized"], spec["normalized"])
            self.assertEqual(empty["design"], spec["design"])
            self.assertNotIn("param_overrides", empty)

    def test_prepare_bakes_override_into_geometry_and_keeps_saved_design(self):
        with tempfile.TemporaryDirectory() as directory:
            self._venv(directory)
            design = blank_design("p", "Patch")
            saved_h = _default(design, "h")
            spec = research.prepare({
                "backend": "emerge", "path": directory, "design": design,
                "settings": design_settings(), "param_overrides": {"h": 2.4}})
            self.assertEqual(_default(design, "h"), saved_h)
            self.assertEqual(_default(spec["design"], "h"), saved_h)
            self.assertEqual(spec["param_overrides"], {"h": 2.4})
            self.assertIn(2.4e-3, [round(h, 12) for h in _box_heights(spec)])
            baseline = research.prepare({
                "backend": "emerge", "path": directory, "design": design,
                "settings": design_settings()})
            self.assertNotIn(2.4e-3, [round(h, 12) for h in _box_heights(baseline)])

    def test_execute_exports_the_overridden_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            self._venv(directory)
            design = blank_design("p", "Patch")
            spec = research.prepare({
                "backend": "emerge", "path": directory, "design": design,
                "settings": design_settings(), "param_overrides": {"h": 2.4}})
            raw = research.encode(spec)
            root = Path(directory)
            snapshot = root / "research.json"
            snapshot.write_bytes(raw)
            outdir = root / "out"
            outdir.mkdir()
            synthetic = emerge_nport_result(1, geometry_kind="driven_lumped")
            with mock.patch("fairbeam_emerge.run_design", return_value=synthetic):
                research.execute(snapshot, outdir, hashlib.sha256(raw).hexdigest())
            saved = json.loads(snapshot.read_text(encoding="utf-8"))
            self.assertEqual(_default(saved["design"], "h"), _default(design, "h"))
            bundle = json.loads((outdir / "bundle.json").read_text(encoding="utf-8"))
            self.assertAlmostEqual(bundle["domain"]["max"][2], spec["normalized"]["air"]["hi"][2] * 1000)
            self.assertNotAlmostEqual(
                bundle["domain"]["max"][2],
                research.prepare({
                    "backend": "emerge", "path": directory, "design": design,
                    "settings": design_settings()})["normalized"]["air"]["hi"][2] * 1000)


class EmergeSweepQueue(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.m = JobManager(self.root / "jobs", self.root / "projects", autostart=False)
        self.design = blank_design("p", "Patch")
        self.design_path = self.root / "p.design.json"
        self.design_path.write_text(json.dumps(self.design), encoding="utf-8")
        self.app = object.__new__(App)
        self.app.manager = self.m
        registry = {"kind": "design", "key": "p", "model": {"id": "p", "name": "Patch"},
                    "path": str(self.design_path), "params": []}
        self.app._model = lambda body: registry
        self.app._design_checks = lambda d: []
        self.app._settings = lambda body, errors: dict(
            threads=1, engine="cpu", end_criteria_db=None, label=None, points=None, name=None)
        self.app._refuse_by_preflight = lambda body, st: None

    def tearDown(self):
        self.m.shutdown()
        self.tmp.cleanup()

    def _sweep(self, **extra):
        return self.app.submit_sweep({
            "model": "p", "sweep": [{"key": "h", "values": [2.0, 3.0]}], **extra})

    def test_sweep_without_emerge_queues_openems_runs(self):
        result = self._sweep()
        self.assertEqual(len(result["runs"]), 2)
        self.assertTrue(all(run["kind"] == "run" for run in result["runs"]))
        self.assertEqual(len({run["sweep"]["id"] for run in result["runs"]}), 1)

    def test_emerge_sweep_queues_one_research_job_per_point(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_venv(directory)
            (Path(directory) / "Lib" / "site-packages" / "emerge-3.0.0b12.dist-info" / "RECORD").write_text(
                "emerge/__init__.py,sha256=abc,10\n", encoding="utf-8")
            result = self._sweep(emerge={"path": directory, "settings": design_settings()})
        runs = result["runs"]
        self.assertEqual(len(runs), 2)
        self.assertTrue(all(run["kind"] == "research" for run in runs))
        sweep_ids = {run["sweep"]["id"] for run in runs}
        self.assertEqual(len(sweep_ids), 1)
        saved_h = _default(self.design, "h")
        for run in runs:
            self.assertEqual(
                set(run["sweep"]),
                {"id", "name", "index", "total", "values", "axes", "sequence_index", "sequence_name"})
            job = self.m.get(run["id"])
            spec = json.loads((job.dir / "input" / "research.json").read_text(encoding="utf-8"))
            point = run["sweep"]["values"]
            self.assertEqual(spec["param_overrides"], point)
            self.assertEqual(_default(spec["design"], "h"), saved_h)
            self.assertIn(point["h"] * 1e-3, [round(height, 12) for height in _box_heights(spec)])

    def test_emerge_sweep_does_not_coerce_unsupported_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_venv(directory)
            with self.assertRaises(ApiError) as caught:
                self._sweep(emerge={"path": directory, "settings": {"resolution": "coarse"}})
        self.assertIn("emerge_nport", str(caught.exception))
        self.assertEqual(self.m.list(), [])


class EmergeOptimizeQueue(unittest.TestCase):
    def setUp(self):
        EmergeSweepQueue.setUp(self)
        self.app.projects_dir = self.m.projects_dir

    def tearDown(self):
        EmergeSweepQueue.tearDown(self)

    def _optimize(self, kind, *, target=-20, at=2.5, settings=None):
        return self.app.submit_optimization({
            "model": "p",
            "vary": [{"key": "h", "min": 1.0, "max": 3.0, "start": 1.5}],
            "goals": [{"kind": kind, "target": target, "at": at}],
            "max_evals": 2,
            "emerge": {"path": "emerge-python", "settings": settings or design_settings()},
        })

    def test_radiation_goals_are_rejected_because_the_far_field_is_empty(self):
        for kind, target in (("realized_gain_min", 5), ("dmax_min", 5), ("efficiency_min", 90)):
            with self.subTest(kind=kind):
                with self.assertRaises(ApiError) as caught:
                    self._optimize(kind, target=target)
                message = str(caught.exception)
                self.assertIn("far field is empty", message)
                self.assertIn(kind, message)
                self.assertNotIn("score is zero", message.lower())
                self.assertEqual(self.m.list(), [])

    def test_s11_goal_is_accepted_and_command_is_not_openems_optimize(self):
        job = self._optimize("s11_max")
        self.assertEqual(job["kind"], "optimize")
        cmd = self.m.default_command(self.m.get(job["id"]))
        self.assertNotIn("-m fairbeam optimize", " ".join(cmd))
        self.assertEqual(cmd[1:3], ["-m", "fairbeam.emerge_optimize"])

    def test_openems_gpu_engine_is_not_kept_on_an_emerge_search(self):
        self.app._settings = lambda body, errors: dict(
            threads=1, engine="gpu", end_criteria_db=None, label=None, points=None, name=None)
        job = self._optimize("s11_max")
        self.assertIsNone(job["engine"])
        cmd = self.m.default_command(self.m.get(job["id"]))
        self.assertEqual(cmd[1:3], ["-m", "fairbeam.emerge_optimize"])
        self.assertNotIn("--engine", cmd)

    def test_goal_frequency_outside_the_emerge_band_is_rejected(self):
        with self.assertRaises(ApiError) as caught:
            self._optimize("s11_max", at=9.0)
        self.assertIn("outside the EMerge band", str(caught.exception))
        self.assertEqual(self.m.list(), [])

    def test_admit_rejection_fails_that_evaluation_and_the_search_continues(self):
        from fairbeam.emerge_optimize import run_emerge_optimization
        from fairbeam.optimize import Vary, make_goal
        design = blank_design("p", "Patch")
        design["ports"] = []
        with tempfile.TemporaryDirectory() as directory:
            fake_venv(directory)
            with mock.patch("fairbeam_emerge.run_design", side_effect=AssertionError("FEM solve")):
                doc = run_emerge_optimization(
                    design, {"path": directory, "settings": design_settings()},
                    [Vary("h", 1.0, 3.0, start=1.5)],
                    [make_goal("s11_max", -20, at=2.5)],
                    out=Path(directory), name="opt", max_evals=2, method="nelder-mead")
        self.assertEqual(len(doc["evaluations"]), 2)
        for row in doc["evaluations"]:
            self.assertIn("ports", row["error"])
            self.assertFalse(row["error"].startswith("ValueError"))
        self.assertEqual(_default(design, "h"), 1.524)


if __name__ == "__main__":
    unittest.main()
