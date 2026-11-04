"""EMerge research admission and result contracts; EMerge is never installed or run here."""
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fairbeam_emerge as fem
from fairbeam import research
from fairbeam.jobs import JobManager
from fairbeam.server import App, make_server

from test_emerge_fixture import fake_venv, synthetic_raw


def emerge_result(status="results_validated", **overrides):
    """Synthetic validated fixture result (not a solver run)."""
    assessed = fem.assess(synthetic_raw())
    value = {**assessed, "backend": "emerge", "research_schema": "fairbeam-research-result-1"}
    value["status"] = status
    value.update(overrides)
    return value


class EmergeResearchAdmission(unittest.TestCase):
    def test_prepare_refuses_design_extra_settings_and_unknown_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_venv(directory)
            base = {"backend": "emerge", "path": directory, "settings": {"resolution": "coarse"}}
            with self.assertRaisesRegex(ValueError, "fixed waveguide fixture"):
                research.prepare({**base, "design": {"solids": []}})
            with self.assertRaisesRegex(ValueError, "exactly"):
                research.prepare({**base, "settings": {"resolution": "coarse", "mesh_size": 0.1}})
            with self.assertRaisesRegex(ValueError, "exactly"):
                research.prepare({**base, "settings": {}})
            with self.assertRaisesRegex(ValueError, "resolution"):
                research.prepare({**base, "settings": {"resolution": "ultra"}})

    def test_prepare_refuses_unsupported_version_and_admits_fake_venv(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_venv(directory, version="9.9.9")
            with self.assertRaisesRegex(ValueError, "unsupported EMerge version"):
                research.prepare({"backend": "emerge", "path": directory,
                                  "settings": {"resolution": "coarse"}})
        with tempfile.TemporaryDirectory() as directory:
            exe, site = fake_venv(directory)
            record = site / "emerge-2.8.9.dist-info" / "RECORD"
            record.write_text("emerge/__init__.py,sha256=abc,10\n", encoding="utf-8")
            spec = research.prepare({"backend": "emerge", "path": directory,
                                     "settings": {"resolution": "coarse"}})
            self.assertEqual(spec["backend"], "emerge")
            self.assertEqual(spec["normalized"], {"resolution": "coarse"})
            self.assertEqual(spec["path"], str(exe.resolve()))
            self.assertIn(str(exe.resolve()), spec["binary_sha256"])
            self.assertIn(str(fem.WORKER.resolve()), spec["binary_sha256"])
            self.assertIn(str(record.resolve()), spec["binary_sha256"])

    def test_probe_reports_fake_venv(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_venv(directory)
            result = research.probe({"backend": "emerge", "path": directory})
            self.assertTrue(result["available"])
            self.assertEqual(result["backend"], "emerge")
            self.assertEqual(result["emerge_version"], "2.8.9")
            self.assertTrue(result["version_supported"])
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(research.probe({"backend": "emerge", "path": directory})["available"])


class EmergeResearchValidation(unittest.TestCase):
    def test_validate_result_accepts_synthetic_validated(self):
        value = research.validate_result(emerge_result(), "emerge")
        self.assertEqual(value["status"], "results_validated")
        self.assertTrue(research.completed_result(value))

    def test_validate_result_rejects_contradiction_schema_and_backend(self):
        bad = emerge_result()
        bad["metrics"] = {**bad["metrics"], "s11_max": 0.5}
        with self.assertRaisesRegex(ValueError, "contradicts"):
            research.validate_result(bad, "emerge")
        wrong_schema = emerge_result(schema="fairbeam.elmer-cavity-result/1")
        with self.assertRaisesRegex(ValueError, "unsupported emerge"):
            research.validate_result(wrong_schema, "emerge")
        with self.assertRaises(ValueError):
            research.validate_result(emerge_result(), "elmer")
        incomplete = emerge_result()
        incomplete["s11_re"] = incomplete["s11_re"][:-1]
        with self.assertRaisesRegex(ValueError, "incomplete"):
            research.validate_result(incomplete, "emerge")
        converged = emerge_result(precision_converged=True)
        with self.assertRaisesRegex(ValueError, "convergence"):
            research.validate_result(converged, "emerge")
        wrong_freq = emerge_result(frequency_hz=[8e9, 9e9, 10e9, 11e9, 12.1e9])
        with self.assertRaisesRegex(ValueError, "fixture list"):
            research.validate_result(wrong_freq, "emerge")

    def test_completed_result_requires_fixture_schema(self):
        value = emerge_result(status="validation_failed")
        self.assertFalse(research.completed_result(value))
        value = emerge_result(schema="other")
        self.assertFalse(research.completed_result(value))


class EmergeResearchHttp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "models").mkdir()
        (self.root / "projects").mkdir()
        # autostart=False: admission is tested without launching the EMerge worker.
        self.manager = JobManager(self.root / "jobs", self.root / "projects", autostart=False)
        with mock.patch("fairbeam.server._versions", return_value={}), \
                mock.patch("fairbeam.server.detect_engines", return_value=["cpu"]):
            self.app = App(models_dir=self.root / "models", projects_dir=self.root / "projects",
                           jobs_dir=self.root / "jobs", manager=self.manager, python=sys.executable)
        self.server = make_server(self.app, "127.0.0.1", 0, quiet=True)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05},
                                       daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.stopping = True
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.app.close()
        self.tmp.cleanup()

    def request(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=15)
        headers, data = {}, None
        if body is not None:
            data = json.dumps(body)
            headers["Content-Type"] = "application/json"
        conn.request(method, path, data, headers)
        response = conn.getresponse()
        payload = json.loads(response.read())
        conn.close()
        return response.status, payload

    def test_health_and_runtime_routes(self):
        code, health = self.request("GET", "/api/health")
        self.assertEqual(code, 200)
        self.assertEqual(health["emerge"], 1)
        with mock.patch("fairbeam.emerge_runtime.status", return_value={"supported": True, "installed": False}):
            code, status = self.request("GET", "/api/research/emerge/runtime")
        self.assertEqual(code, 200)
        self.assertFalse(status["installed"])
        with mock.patch("fairbeam.emerge_runtime.start_install", return_value={"state": "creating"}):
            code, started = self.request("POST", "/api/research/emerge/install", {})
        self.assertEqual(code, 202)
        self.assertEqual(started["state"], "creating")

    def test_post_admits_emerge_run_against_fake_venv(self):
        with tempfile.TemporaryDirectory() as directory:
            fake_venv(directory)
            (Path(directory) / "Lib" / "site-packages" / "emerge-2.8.9.dist-info" / "RECORD").write_text(
                "emerge/__init__.py,sha256=abc,10\n", encoding="utf-8")
            code, doc = self.request("POST", "/api/research/runs",
                                     {"backend": "emerge", "path": directory,
                                      "settings": {"resolution": "coarse"}})
            self.assertEqual(code, 201)
            job = self.app.manager.get(doc["id"])
            self.assertEqual(job.research["backend"], "emerge")
            snapshot = json.loads((job.dir / "input" / "research.json").read_text(encoding="utf-8"))
            self.assertEqual(snapshot["normalized"], {"resolution": "coarse"})
            self.assertIsNone(snapshot["design"])
            self.assertEqual(job.status, "queued")


if __name__ == "__main__":
    unittest.main()
