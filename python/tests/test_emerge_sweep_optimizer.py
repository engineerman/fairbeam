"""EMerge parameter sweep and optimizer admission. EMerge is never installed or run here."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from fairbeam import research
from fairbeam.design import blank_design

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


if __name__ == "__main__":
    unittest.main()
