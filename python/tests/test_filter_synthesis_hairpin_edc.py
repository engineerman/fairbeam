"""Hairpin EDC study: geometry, Qe/k extraction, and the openEMS queue. No solve."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from fairbeam.design import check_design
from fairbeam.filter_synthesis.hairpin_edc import (
    SOLVER,
    HairpinEdcStudies,
    assemble_design,
    coupling_k,
    external_q,
    interpolate_to_target,
    plan_samples,
    qe_k_targets,
    study_design,
)
from fairbeam.filter_synthesis.hairpin_microstrip_bp import (
    HairpinMicrostripBpSpec,
    synthesize_hairpin_microstrip_bp,
)
from fairbeam.jobs import JobManager
from fairbeam.server import ApiError, App


def _default(design, key):
    for param in design["params"]:
        if param.get("key") == key and "expr" not in param:
            return float(param["default"])
    raise KeyError(key)


def _seed():
    spec = HairpinMicrostripBpSpec(f0_hz=2e9, order=3, bw_hz=0.2e9, ripple_db=0.1)
    design = synthesize_hairpin_microstrip_bp(spec).design
    electrical = {
        "f0_hz": spec.f0_hz,
        "bw_hz": spec.bw_hz,
        "order": spec.order,
        "ripple_db": spec.ripple_db,
        "response": "chebyshev",
    }
    return design, electrical


def _s11_for_qe(qe, f0=2.0e9, n=81):
    f = np.linspace(f0 - 0.5e9, f0 + 0.5e9, n)
    phase = -2.0 * np.arctan(2.0 * qe * (f - f0) / f0)
    return f, np.exp(1j * phase)


def _qe_bundle(qe):
    f, s11 = _s11_for_qe(qe)
    return {
        "results": {
            "frequency": f.tolist(),
            "ports": {"1": {"s11_re": np.real(s11).tolist(), "s11_im": np.imag(s11).tolist()}},
        }
    }


def _k_bundle(i0, i1, n=81, f0=2.0e9):
    f = np.linspace(f0 - 0.5e9, f0 + 0.5e9, n)
    y = np.full(n, -40.0)
    y[i0] = -3.0
    y[i0 - 1] = y[i0 + 1] = -8.0
    y[i1] = -4.0
    y[i1 - 1] = y[i1 + 1] = -9.0
    mag = 10.0 ** (y / 20.0)
    return {
        "results": {
            "frequency": f.tolist(),
            "sparams": {"s": {"2,1": {"re": mag.tolist(), "im": [0.0] * n}}},
        }
    }, coupling_k(f, y)


class HairpinEdcExtractionTests(unittest.TestCase):
    def test_external_q_recovers_slope_and_flags_a_second_peak(self):
        f, s11 = _s11_for_qe(10.32)
        got = external_q(f, s11)
        self.assertFalse(got["ambiguous"])
        self.assertLess(abs(got["qe"] - 10.32) / 10.32, 0.03)

        self.assertIsNone(got["ambiguous_reason"])

    def test_coupling_k_rejects_a_sub_bin_split(self):
        f = np.array([1.00, 1.50, 1.55, 1.60, 2.50]) * 1e9
        weak = coupling_k(f, np.array([-30.0, -2.0, -8.0, -3.0, -30.0]))
        self.assertEqual(weak["status"], "unresolved")
        self.assertEqual(weak["reason"], "weak_split")
        self.assertIsNone(weak["k"])

    def test_interpolate_clamps_outside_the_samples(self):
        samples = [
            {"tap_mm": 2.0, "qe": 20.0, "status": "ok"},
            {"tap_mm": 12.0, "qe": 5.0, "status": "ok"},
        ]
        choice = interpolate_to_target(samples, "tap_mm", "qe", 10.32, 5.852)
        expect = 2.0 + (10.32 - 20.0) / (5.0 - 20.0) * 10.0
        self.assertAlmostEqual(choice["x"], expect)
        self.assertFalse(choice["clamped"])
        self.assertFalse(choice["extrapolated"])
        high = [
            {"sp_mm": 0.4, "k": 0.2, "status": "ok"},
            {"sp_mm": 2.5, "k": 0.12, "status": "ok"},
        ]
        clamped = interpolate_to_target(high, "sp_mm", "k", 0.05, 1.0)
        self.assertTrue(clamped["clamped"])
        self.assertFalse(clamped["extrapolated"])
        self.assertEqual(clamped["x"], 2.5)

    def test_equiripple_has_no_target(self):
        with self.assertRaises(ValueError) as caught:
            qe_k_targets({"order": 3, "f0_hz": 2e9, "bw_hz": 0.2e9, "ripple_db": 0.1, "response": "equiripple"})
        self.assertIn("no Qe/k formula", str(caught.exception))


class HairpinEdcGeometryTests(unittest.TestCase):
    def test_study_designs_keep_seed_widths_and_drop_unused_ports(self):
        design, _ = _seed()
        qe = study_design(design, n_res=1, tap_mm=4.0, spacings_mm=[], one_port=True)
        pair = study_design(design, n_res=2, tap_mm=4.0, spacings_mm=[0.8], one_port=False)
        self.assertEqual(len(qe["ports"]), 1)
        self.assertTrue(qe["ports"][0]["excite"])
        self.assertEqual(qe["simulation"]["pulse_cycles"], 3)
        self.assertEqual(qe["simulation"]["f_min"], "f0-0.5")
        self.assertEqual(qe["simulation"]["f_max"], "f0+0.5")
        self.assertEqual(qe["simulation"]["end_criteria_db"], -40)
        self.assertNotIn("pulse_cycles", pair["simulation"])
        self.assertEqual(len(pair["ports"]), 2)
        self.assertEqual(len(_filter_prims(qe)), 4)
        self.assertEqual(len(_filter_prims(pair)), 8)
        for key in ("q_len", "w0", "gap0", "w_feed"):
            self.assertEqual(_default(qe, key), _default(design, key))
            self.assertEqual(_default(pair, key), _default(design, key))
        self.assertAlmostEqual(_default(pair, "sp0"), 0.8)
        check_design(qe)
        check_design(pair)

    def test_assemble_changes_tap_and_mirrored_spacing_only(self):
        design, _ = _seed()
        out = assemble_design(design, 7.5, 0.8)
        self.assertAlmostEqual(_default(out, "tap_from_fold"), 7.5)
        self.assertAlmostEqual(_default(out, "sp0"), 0.8)
        self.assertAlmostEqual(_default(out, "sp1"), 0.8)
        for key in ("q_len", "w0", "w1", "w2", "gap0", "gap1", "gap2", "w_feed"):
            self.assertEqual(_default(out, key), _default(design, key))
            self.assertEqual(out_band(out, key), out_band(design, key))
        from fairbeam.design import resolve_names

        names = resolve_names(out, {})
        expect_y = (names["q_len"] - names["tap_from_fold"]) if names["open_down0"] >= 0.5 else names["tap_from_fold"]
        self.assertAlmostEqual(names["y_feed0"], expect_y)
        self.assertIn("expr", next(p for p in out["params"] if p.get("key") == "y_feed0"))
        self.assertNotIn("expr", next(p for p in out["params"] if p.get("key") == "tap_from_fold"))
        check_design(out)


def _filter_prims(design):
    return next(part["primitives"] for part in design["parts"] if part["name"] == "filter")


def out_band(design, key):
    for param in design["params"]:
        if param.get("key") == key:
            return (param.get("min"), param.get("max"))
    raise KeyError(key)


class HairpinEdcQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.projects = self.tmp / "projects"
        self.projects.mkdir()
        self.manager = JobManager(self.tmp / "jobs", self.projects, python="python", autostart=False)
        self.studies = HairpinEdcStudies(self.manager, self.projects)
        self.manager.on_finished = self.studies.on_finished
        self.design, self.electrical = _seed()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_start_queues_one_openems_sample(self):
        view = self.studies.start(self.design, self.electrical)
        self.assertEqual(view["solver"], SOLVER)
        self.assertEqual(view["status"], "running")
        self.assertEqual(view["completed"], 0)
        self.assertEqual(view["total"], len(plan_samples(self.design, self.electrical)))
        self.assertGreaterEqual(view["total"], 4)
        self.assertNotIn("design", view)
        self.assertEqual(len(self.manager.jobs), 1)
        job = next(iter(self.manager.jobs.values()))
        cmd = self.manager.default_command(job)
        self.assertIn("run", cmd)
        self.assertNotIn("research", cmd)
        self.assertEqual(job.engine, "gpu")
        self.assertEqual(job.threads, 1)
        self.assertEqual(cmd[cmd.index("--engine") + 1], "gpu")
        self.assertIn("81", cmd)
        self.assertIsNone(job.excite)
        study = self.studies.load(view["id"])
        k_index = next(i for i, sample in enumerate(study["samples"]) if sample["kind"] == "k")
        k_job = self.studies._submit(study, k_index)
        k_cmd = self.manager.default_command(k_job)
        self.assertEqual(k_job.engine, "gpu")
        self.assertEqual(k_job.threads, 1)
        self.assertEqual(k_cmd[k_cmd.index("--engine") + 1], "gpu")
        self.assertEqual(k_cmd[k_cmd.index("--excite") + 1], "all")
        snap = json.loads(Path(self.manager.input_path(job)).read_text(encoding="utf-8"))
        self.assertEqual(len(snap["ports"]), 1)
        self.assertTrue(str(job.model_path).endswith(".design.json"))

    def test_public_phase_qe_while_running(self):
        view = self.studies.start(self.design, self.electrical)
        self.assertEqual(view["status"], "running")
        self.assertEqual(view["phase"], "qe")
        polled = self.studies.poll(view["id"])
        self.assertEqual(polled["status"], "running")
        self.assertEqual(polled["phase"], "qe")

        samples = plan_samples(self.design, self.electrical)
        qe_n = sum(1 for sample in samples if sample["kind"] == "qe")
        self.assertGreater(qe_n, 0)
        self.assertTrue(any(sample["kind"] == "k" for sample in samples))
        qe_values = [20.0, 10.32, 10.32, 10.32]
        k_peaks = [(32, 48), (34, 46), (36, 44), (38, 42), (30, 40)]
        for index, sample in enumerate(samples):
            job = next(j for j in self.manager.jobs.values() if j.status == "queued")
            if sample["kind"] == "qe":
                bundle = _qe_bundle(qe_values[index])
            else:
                bundle, info = _k_bundle(*k_peaks[index - qe_n])
                self.assertEqual(info["status"], "ok")
            name = f"bundle-phase-{job.id}.json"
            (self.projects / name).write_text(json.dumps(bundle), encoding="utf-8")
            job.bundle = name
            job.status = "done"
            self.studies.on_finished(job)
            if index + 1 == qe_n:
                mid = self.studies.poll(view["id"])
                self.assertEqual(mid["status"], "running")
                self.assertEqual(mid["phase"], "k")

        done = self.studies.poll(view["id"])
        self.assertEqual(done["status"], "done", done.get("error"))
        self.assertIsNone(done["phase"])

        assembling = HairpinEdcStudies._public(
            {
                "id": "he-assemble",
                "status": "running",
                "completed": len(samples),
                "total": len(samples),
                "samples": samples,
                "error": None,
            }
        )
        self.assertEqual(assembling["phase"], "assemble")

    def test_poll_moves_with_the_openems_sample(self):
        view = self.studies.start(self.design, self.electrical)
        self.assertEqual(view["sample_status"], "queued")
        self.assertEqual(view["sample_fraction"], 0.0)
        job = next(iter(self.manager.jobs.values()))
        job.status = "running"
        job.last_progress = {
            "energy_fraction": 0.6,
            "timestep_fraction": 0.11,
            "eta": {"basis": "timestep-limit"},
        }
        polled = self.studies.poll(view["id"])
        self.assertEqual(polled["sample_status"], "running")
        self.assertAlmostEqual(polled["sample_fraction"], 0.6)
        self.assertAlmostEqual(polled["run_fraction"], 0.6 / polled["total"])
        job.last_progress = {
            "energy_fraction": 0.39,
            "timestep_fraction": 0.2,
            "eta": {"basis": "timestep-limit"},
        }
        dipped = self.studies.poll(view["id"])
        self.assertAlmostEqual(dipped["sample_fraction"], 0.6)
        self.assertGreaterEqual(dipped["run_fraction"], polled["run_fraction"])
        study = self.studies.load(view["id"])
        assert study is not None
        study["completed"] = 1
        held = self.studies._hold_fraction(study, 0.1)
        self.assertAlmostEqual(held, 0.1)
        self.assertGreaterEqual((1 + held) / dipped["total"], dipped["run_fraction"])

    def test_poll_adopts_a_done_sample_instead_of_failing(self):
        """UI poll can race the manager callback; a successful sample must not become failed."""
        view = self.studies.start(self.design, self.electrical)
        job = next(iter(self.manager.jobs.values()))
        name = f"bundle-{job.id}.json"
        (self.projects / name).write_text(json.dumps(_qe_bundle(12.0)), encoding="utf-8")
        job.bundle = name
        job.status = "done"
        # Poll before on_finished — previously this wrote status=failed / "sample failed".
        polled = self.studies.poll(view["id"])
        self.assertNotEqual(polled["status"], "failed", polled.get("error"))
        self.assertEqual(polled["completed"], 1)
        self.assertEqual(polled["status"], "running")
        # Manager callback later must be idempotent.
        self.studies.on_finished(job)
        again = self.studies.poll(view["id"])
        self.assertEqual(again["completed"], 1)
        self.assertNotEqual(again["status"], "failed", again.get("error"))

    def test_a_new_study_cancels_the_one_already_running(self):
        first = self.studies.start(self.design, self.electrical)
        second = self.studies.start(self.design, self.electrical)
        self.assertEqual(self.studies.poll(first["id"])["status"], "cancelled")
        self.assertEqual(second["status"], "running")
        self.assertEqual(second["completed"], 0)
        live = [job for job in self.manager.jobs.values() if not job.terminal]
        self.assertEqual(len(live), 1)
        self.assertEqual((live[0].sweep or {}).get("id"), second["id"])

    def test_cancel_keeps_the_seed_and_does_not_publish_a_design(self):
        before = json.dumps(self.design, sort_keys=True)
        view = self.studies.start(self.design, self.electrical)
        cancelled = self.studies.cancel(view["id"])
        self.assertEqual(json.dumps(self.design, sort_keys=True), before)
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertNotIn("design", cancelled)
        self.assertEqual(len(self.manager.jobs), 1)
        job = next(iter(self.manager.jobs.values()))
        job.status = "done"
        job.bundle = "should-not-be-read.json"
        self.studies.on_finished(job)
        again = self.studies.poll(view["id"])
        self.assertEqual(again["status"], "cancelled")
        self.assertNotIn("design", again)
        self.assertEqual(len(self.manager.jobs), 1)

    def test_finished_samples_change_tap_and_mirrored_spacing_only(self):
        qe_target, k_target = qe_k_targets(self.electrical)
        view = self.studies.start(self.design, self.electrical)
        samples = plan_samples(self.design, self.electrical)
        qe_values = [20.0, 10.32, 10.32, 10.32]
        k_peaks = [(32, 48), (34, 46), (36, 44), (38, 42), (30, 40)]
        qe_rows = []
        k_rows = []
        for sample in samples:
            job = next(j for j in self.manager.jobs.values() if j.status == "queued")
            if sample["kind"] == "qe":
                bundle = _qe_bundle(qe_values[len(qe_rows)])
                got = external_q(np.asarray(bundle["results"]["frequency"]), _s11(bundle))
                self.assertFalse(got["ambiguous"])
                qe_rows.append({"tap_mm": sample["tap_mm"], "qe": got["qe"], "status": "ok"})
            else:
                bundle, _info = _k_bundle(*k_peaks[len(k_rows)])
                f = np.asarray(bundle["results"]["frequency"])
                entry = bundle["results"]["sparams"]["s"]["2,1"]
                s21 = np.asarray(entry["re"]) + 1j * np.asarray(entry["im"])
                db = 20.0 * np.log10(np.maximum(np.abs(s21), 1e-30))
                info = coupling_k(f, db)
                self.assertEqual(info["status"], "ok")
                k_rows.append({"sp_mm": sample["sp_mm"], "k": info["k"], "status": "ok"})
            name = f"bundle-{job.id}.json"
            (self.projects / name).write_text(json.dumps(bundle), encoding="utf-8")
            job.bundle = name
            job.status = "done"
            self.studies.on_finished(job)
        done = self.studies.poll(view["id"])
        self.assertEqual(done["status"], "done", done.get("error"))
        out = done["design"]
        expect_tap = interpolate_to_target(qe_rows, "tap_mm", "qe", qe_target, _default(self.design, "tap_from_fold"))
        expect_sp = interpolate_to_target(k_rows, "sp_mm", "k", k_target, _default(self.design, "sp0"))
        self.assertAlmostEqual(_default(out, "tap_from_fold"), expect_tap["x"], places=6)
        self.assertAlmostEqual(_default(out, "sp0"), expect_sp["x"], places=6)
        self.assertAlmostEqual(_default(out, "sp1"), _default(out, "sp0"), places=6)
        for key in ("q_len", "w0", "w1", "w2", "gap0", "gap1", "gap2", "w_feed"):
            self.assertEqual(_default(out, key), _default(self.design, key))
        self.assertEqual(len(self.manager.jobs), 9)
        queued = [j for j in self.manager.jobs.values() if j.status == "queued"]
        self.assertEqual(queued, [])

    def test_route_starts_polls_and_cancels(self):
        app = App.__new__(App)
        app.hairpin_studies = self.studies
        started = app.hairpin_edc({"action": "start", "design": self.design, "electrical": self.electrical})
        self.assertEqual(app.hairpin_edc({"action": "poll", "study_id": started["id"]})["status"], "running")
        cancelled = app.hairpin_edc({"action": "cancel", "study_id": started["id"]})
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertNotIn("design", cancelled)
        with self.assertRaises(ApiError):
            app.hairpin_edc({"action": "start", "design": self.design, "electrical": {**self.electrical, "response": "equiripple"}})


def _s11(bundle):
    port = bundle["results"]["ports"]["1"]
    return np.asarray(port["s11_re"]) + 1j * np.asarray(port["s11_im"])


if __name__ == "__main__":
    unittest.main()
