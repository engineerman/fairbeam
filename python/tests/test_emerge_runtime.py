"""The managed EMerge environment: pinned venv + hash-locked install (no network, no EMerge)."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fairbeam import emerge_runtime

METADATA = "Metadata-Version: 2.4\nName: emerge\nVersion: {version}\n\nbody\n"


class FakeSubprocess:
    """Stands in for subprocess.run: the venv step makes Scripts/python.exe, the pip step the dist-info."""

    def __init__(self, test, pip_fails=False, pip_version=None):
        self.test = test
        self.pip_fails = pip_fails
        self.pip_version = pip_version or emerge_runtime.PIN["version"]
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((list(args), kwargs))
        self.test.assertIs(kwargs.get("stdin"), subprocess.DEVNULL)
        env = kwargs.get("env") or {}
        self.test.assertNotIn("PYTHONPATH", env)
        self.test.assertNotIn("PYTHONHOME", env)
        if list(args[1:3]) == ["-m", "venv"]:
            target = Path(args[3])
            (target / "Scripts").mkdir(parents=True)
            (target / "Scripts" / "python.exe").write_bytes(b"python")
            (target / "Lib" / "site-packages").mkdir(parents=True)
            return subprocess.CompletedProcess(args, 0)
        self.test.assertEqual(Path(args[0]), emerge_runtime.python())
        kwargs["stdout"].write(b"Collecting emerge\n")
        if self.pip_fails:
            kwargs["stdout"].write(b"ERROR: THESE PACKAGES DO NOT MATCH THE HASHES\n")
            kwargs["stdout"].flush()
            raise subprocess.CalledProcessError(1, args)
        dist = emerge_runtime.home() / "Lib" / "site-packages" / f"emerge-{emerge_runtime.PIN['version']}.dist-info"
        dist.mkdir(parents=True)
        (dist / "METADATA").write_text(METADATA.format(version=self.pip_version), encoding="utf-8")
        return subprocess.CompletedProcess(args, 0)


class ManagedEmerge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "state"
        env = mock.patch.dict(os.environ, {"FAIRBEAM_STATE_DIR": str(self.state)})
        env.start()
        self.addCleanup(env.stop)
        emerge_runtime._progress.update(state="idle", error="")
        # run on any host: pretend to be the pinned platform and Python
        self.pin = mock.patch.dict(emerge_runtime.PIN, {"platform": sys.platform, "python": sys.version_info[:2]})
        self.pin.start()
        self.addCleanup(self.pin.stop)

    def run_install(self, **fake_options):
        fake = FakeSubprocess(self, **fake_options)
        with mock.patch("subprocess.run", fake):
            return fake, emerge_runtime.install()

    def test_committed_lock_matches_the_pin(self):
        digest = hashlib.sha256(emerge_runtime.lock_path().read_bytes()).hexdigest()
        self.assertEqual(digest, emerge_runtime.PIN["lock_sha256"])
        self.assertIn("emerge==3.0.0b12 ", emerge_runtime.lock_path().read_text(encoding="utf-8"))

    def test_installs_into_the_state_folder_and_writes_the_marker_last(self):
        self.assertFalse(emerge_runtime.installed())
        fake, status = self.run_install()
        home = emerge_runtime.home()
        self.assertEqual(home, self.state / "emerge" / emerge_runtime.PIN["version"])
        self.assertEqual(emerge_runtime.python(), home / "Scripts" / "python.exe")
        self.assertTrue(status["installed"])
        self.assertEqual(status["state"], "done")
        marker = json.loads((home / "fairbeam-emerge.json").read_text(encoding="utf-8"))
        self.assertEqual(marker, {"version": "3.0.0b12", "lock_sha256": emerge_runtime.PIN["lock_sha256"]})
        venv_args, pip_args = fake.calls[0][0], fake.calls[1][0]
        self.assertEqual(venv_args[:3], [sys.executable, "-m", "venv"])
        for flag in ("-I", "--no-deps", "--require-hashes", "--only-binary=:all:", "--no-input"):
            self.assertIn(flag, pip_args)
        self.assertEqual(Path(pip_args[pip_args.index("-r") + 1]), emerge_runtime.lock_path())
        self.assertEqual(fake.calls[1][1]["timeout"], 1800)
        self.assertIn(b"Collecting emerge", (home / "install.log").read_bytes())

    def test_second_install_is_a_no_op(self):
        self.run_install()
        fake, status = self.run_install()
        self.assertEqual(fake.calls, [])
        self.assertTrue(status["installed"])
        self.assertEqual(status["state"], "done")

    def test_pip_failure_leaves_nothing_behind(self):
        fake = FakeSubprocess(self, pip_fails=True)
        with mock.patch("subprocess.run", fake):
            with self.assertRaises(subprocess.CalledProcessError):
                emerge_runtime.install()
        self.assertFalse(emerge_runtime.home().exists())
        self.assertFalse(emerge_runtime.installed())
        status = emerge_runtime.status()
        self.assertEqual(status["state"], "failed")
        self.assertIn("DO NOT MATCH THE HASHES", status["error"], "the pip log tail is kept in the error")

    def test_wrong_package_version_is_not_accepted(self):
        fake = FakeSubprocess(self, pip_version="2.8.8")
        with mock.patch("subprocess.run", fake):
            with self.assertRaisesRegex(ValueError, "does not hold emerge 3.0.0b12"):
                emerge_runtime.install()
        self.assertFalse(emerge_runtime.home().exists())

    def test_wrong_python_minor_is_refused(self):
        with mock.patch.dict(emerge_runtime.PIN, {"python": (3, 99)}), \
                mock.patch("subprocess.run") as run:
            with self.assertRaisesRegex(OSError, "Python 3.99"):
                emerge_runtime.install()
        run.assert_not_called()
        self.assertFalse(emerge_runtime.home().exists())

    def test_lock_hash_mismatch_is_refused(self):
        with mock.patch.dict(emerge_runtime.PIN, {"lock_sha256": "0" * 64}), \
                mock.patch("subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                emerge_runtime.install()
        run.assert_not_called()

    def test_other_platforms_are_told_to_install_emerge_themselves(self):
        with mock.patch.dict(emerge_runtime.PIN, {"platform": "not-this-platform"}), \
                mock.patch("subprocess.run") as run:
            with self.assertRaisesRegex(OSError, "Windows x64 only"):
                emerge_runtime.install()
            with self.assertRaises(OSError):
                emerge_runtime.start_install()
            self.assertFalse(emerge_runtime.status()["supported"])
        run.assert_not_called()

    def test_folder_without_marker_is_not_installed_and_is_replaced(self):
        home = emerge_runtime.home()
        (home / "Scripts").mkdir(parents=True)
        (home / "Scripts" / "python.exe").write_bytes(b"stale")
        (home / "stale.txt").write_text("partial earlier attempt", encoding="utf-8")
        self.assertFalse(emerge_runtime.installed())
        self.run_install()
        self.assertFalse((home / "stale.txt").exists())
        self.assertTrue(emerge_runtime.installed())

    def test_marker_for_another_lock_is_not_installed(self):
        self.run_install()
        marker = emerge_runtime.home() / "fairbeam-emerge.json"
        marker.write_text(json.dumps({"version": "3.0.0b12", "lock_sha256": "0" * 64}), encoding="utf-8")
        self.assertFalse(emerge_runtime.installed())
        marker.write_text("not json", encoding="utf-8")
        self.assertFalse(emerge_runtime.installed())

    def test_start_install_while_busy_does_not_start_a_second_thread(self):
        for state in emerge_runtime.BUSY:
            emerge_runtime._progress.update(state=state)
            with mock.patch("threading.Thread") as thread:
                self.assertEqual(emerge_runtime.start_install()["state"], state)
            thread.assert_not_called()

    def test_start_install_starts_one_thread_when_idle(self):
        with mock.patch("threading.Thread") as thread:
            status = emerge_runtime.start_install()
        thread.assert_called_once()
        thread.return_value.start.assert_called_once()
        self.assertEqual(status["state"], "creating")
        with mock.patch("threading.Thread") as thread:
            emerge_runtime.start_install()  # now busy
        thread.assert_not_called()

    def test_status_shape(self):
        status = emerge_runtime.status()
        for key in ("supported", "installed", "path", "version", "license", "source", "state", "error",
                    "estimated_bytes"):
            self.assertIn(key, status)
        self.assertEqual(status["estimated_bytes"], emerge_runtime.ESTIMATED_BYTES)
        self.assertEqual(status["version"], "3.0.0b12")
        self.assertFalse(status["installed"])


if __name__ == "__main__":
    unittest.main()
