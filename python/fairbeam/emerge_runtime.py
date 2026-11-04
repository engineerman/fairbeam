"""Managed EMerge runtime: an optional, pinned virtual environment for the experimental EMerge backend.

The environment is created only when the person asks for it. It is built from Fairbeam's own CPython
(``sys.executable -m venv``) in the app's per-user data folder (``appstate.state_dir()/emerge/<version>``)
and filled with the hash-locked wheel set in ``emerge_lock/`` (``pip install --no-deps --require-hashes
--only-binary=:all:``). Nothing from EMerge runs during install, and no Fairbeam process imports EMerge:
the adapter ``fairbeam_emerge`` finds this folder like any other EMerge environment and starts the worker
in a separate process. EMerge is GPL-2.0-or-later (see the installed package's LICENSE); some of its
dependencies carry their own licenses. Source: https://github.com/FennisRobert/EMerge
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from . import appstate

PIN = {
    "version": "2.8.9",
    "platform": "win32",
    "python": (3, 13),
    "lock": "win_amd64-cp313.txt",
    "lock_sha256": "28fce6389021befba3b0aa9f0106143f560bbe870841089a75e2277cf80aace6",
    "source": "https://github.com/FennisRobert/EMerge",
    "license": "GPL-2.0-or-later (see the installed package's LICENSE)",
}
# Total size of the locked wheels (Task 1 evidence log: 52 files). The installed size is larger.
ESTIMATED_BYTES = 461988175
MARKER = "fairbeam-emerge.json"
BUSY = ("creating", "installing", "verifying")
PIP_TIMEOUT_S = 1800
VENV_TIMEOUT_S = 300

_lock = threading.Lock()
_progress = {"state": "idle", "error": ""}


def supported() -> bool:
    return sys.platform == PIN["platform"]


def home() -> Path:
    """Where the managed environment lives once installed."""
    return appstate.state_dir() / "emerge" / PIN["version"]


def python() -> Path:
    return home() / "Scripts" / "python.exe"


def lock_path() -> Path:
    return Path(__file__).resolve().parent / "emerge_lock" / PIN["lock"]


def _lock_sha256() -> str:
    return hashlib.sha256(lock_path().read_bytes()).hexdigest()


def _marker_ok() -> bool:
    try:
        marker = json.loads((home() / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (isinstance(marker, dict) and marker.get("version") == PIN["version"]
            and marker.get("lock_sha256") == PIN["lock_sha256"])


def installed() -> bool:
    return python().is_file() and _marker_ok()


def status() -> dict:
    with _lock:
        progress = dict(_progress)
    return {"supported": supported(), "installed": installed(), "path": str(home()),
            "version": PIN["version"], "license": PIN["license"], "source": PIN["source"],
            "estimated_bytes": ESTIMATED_BYTES, **progress}


def _set(**fields) -> None:
    with _lock:
        _progress.update(fields)


def _clean_env() -> dict:
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME"):
        env.pop(name, None)
    return env


def _run(args, **kwargs):
    return subprocess.run(args, stdin=subprocess.DEVNULL, env=_clean_env(),
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), **kwargs)


def _verify() -> None:
    """Read the installed package's metadata (no execution of EMerge)."""
    name = f"emerge-{PIN['version']}.dist-info"
    metadata = home() / "Lib" / "site-packages" / name / "METADATA"
    try:
        text = metadata.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"the EMerge environment has no {name}/METADATA") from exc
    fields = {}
    for line in text.splitlines():
        if not line.strip():
            break  # headers end at the first blank line
        key, _, value = line.partition(":")
        fields.setdefault(key.strip(), value.strip())
    if fields.get("Name", "").lower() != "emerge" or fields.get("Version") != PIN["version"]:
        raise ValueError(f"the EMerge environment does not hold emerge {PIN['version']}")


def _log_tail(log: Path, lines: int = 8) -> str:
    try:
        return "\n".join(log.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return ""


def install() -> dict:
    """Create the environment and install the locked wheels (blocking). Safe to call again: an
    existing install is kept, and a failed attempt leaves nothing behind."""
    if not supported():
        raise OSError("The managed EMerge environment is available on Windows x64 only; on other systems "
                      "install EMerge yourself into a Python 3.10 to 3.13 environment and enter its folder.")
    wanted = tuple(PIN["python"])
    if tuple(sys.version_info[:2]) != wanted:
        raise OSError(f"The managed EMerge environment needs Fairbeam to run on Python "
                      f"{wanted[0]}.{wanted[1]}; this is Python {sys.version_info[0]}.{sys.version_info[1]}. "
                      "Install EMerge yourself into a Python 3.10 to 3.13 environment and enter its folder.")
    if _lock_sha256() != PIN["lock_sha256"]:
        raise ValueError("the EMerge lock file does not match the pinned SHA-256; nothing was installed")
    if installed():
        _set(state="done", error="")
        return status()
    target = home()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)  # a partial earlier attempt: installed() was False
    try:
        _set(state="creating", error="")  # also when called directly (CLI, tests)
        _run([sys.executable, "-m", "venv", str(target)], check=True, timeout=VENV_TIMEOUT_S,
             capture_output=True)
        _set(state="installing")
        log = target / "install.log"
        with open(log, "wb") as out:
            _run([str(python()), "-I", "-m", "pip", "install", "--no-deps", "--require-hashes",
                  "--only-binary=:all:", "--no-input", "--disable-pip-version-check",
                  "-r", str(lock_path())],
                 check=True, timeout=PIP_TIMEOUT_S, stdout=out, stderr=subprocess.STDOUT)
        _set(state="verifying")
        _verify()
        (target / MARKER).write_text(
            json.dumps({"version": PIN["version"], "lock_sha256": PIN["lock_sha256"]}, indent=2) + "\n",
            encoding="utf-8")  # last: its presence means the install is complete
    except Exception as exc:
        message = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            tail = _log_tail(target / "install.log")
            message = f"{exc}" + (f"\n{tail}" if tail else "")
        elif isinstance(exc, subprocess.TimeoutExpired):
            message = f"the EMerge install timed out after {int(exc.timeout)} s"
        _set(state="failed", error=message)
        shutil.rmtree(target, ignore_errors=True)
        raise
    _set(state="done", error="")
    return status()


def start_install() -> dict:
    """Run install() in the background (one at a time); poll status() for progress."""
    if not supported():
        raise OSError("The managed EMerge environment is available on Windows x64 only.")
    with _lock:
        start = _progress["state"] not in BUSY and not installed()
        if start:
            _progress.update(state="creating", error="")
    if start:
        threading.Thread(target=_safe_install, name="emerge-install", daemon=True).start()
    return status()


def _safe_install() -> None:
    try:
        install()
    except Exception:  # the error is kept in status()
        pass
