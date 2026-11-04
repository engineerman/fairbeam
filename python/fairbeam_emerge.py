"""Opt-in external EMerge research adapter (WR-90 fixture and admitted Designs); stdlib only.

This adapter never imports EMerge. It finds an external EMerge Python environment, writes
``case.json`` and starts ``fairbeam_emerge_worker.py`` in that environment as a separate process.
Only the worker imports EMerge. Fixture raw S-parameters are checked against the analytic
straight-waveguide reference; Design raw S11 is checked against the driven-result schema only
(``results_exported``, never validated).
"""
import argparse
import cmath
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

C0 = 299792458.0
A_M = 0.02286      # WR-90 broad wall (x)
B_M = 0.01016      # WR-90 narrow wall (y)
L_M = 0.05         # length (z); ports on the z = 0 and z = L faces
FREQUENCIES_HZ = (8e9, 9e9, 10e9, 11e9, 12e9)
# Mesh resolution is EMerge's wavelength fraction (``Simulation.set_resolution``: lower is finer; the
# default is 0.33 and EMerge warns above 0.334). PROVISIONAL until the Planner freezes them after
# Task 5; ``fine`` is exactly 2x finer than ``coarse``.
RESOLUTIONS = {"coarse": 0.25, "fine": 0.125}
SUPPORTED_EMERGE = ("2.8.9",)
PHASOR = "exp(+i omega t)"
NATIVE_PHASORS = ("exp(+i omega t)", "exp(-i omega t)")
# Acceptance criteria owned by the Planner (docs/agent/plans/2026-11-04-emerge-level-a-fixture.md),
# frozen from the recorded EMerge 2.8.9 coarse/fine runs.
CRITERIA = {"s11_max": 0.02, "s21_min": 0.995, "phase_error_deg_max": 2.0, "passivity_max": 1.005}
RESULT_SCHEMA = "fairbeam.emerge-fixture-result/1"
MANIFEST_SCHEMA = "fairbeam-emerge-fixture-1"
DESIGN_RESULT_SCHEMA = "fairbeam.emerge-driven-result/1"
DESIGN_MANIFEST_SCHEMA = "fairbeam-emerge-design-1"
S11_ABS_MAX = 1.01  # same bound as Elmer driven
WORKER = Path(__file__).resolve().with_name("fairbeam_emerge_worker.py")
WORKER_TIMEOUT_S = 600
DESIGN_WORKER_TIMEOUT_S = 1800  # Design sweep timeout (frozen Task 5; Level A waveguide stays 600 s)
LIMITATIONS = [
    "Fixed WR-90 straight air-filled waveguide fixture only; no user design is translated.",
    "Reference planes are the port faces; ideal PEC walls, lossless fill, single-mode band.",
    "No mesh convergence study; precision_converged is always false.",
    "Not qualified for driven antenna results.",
]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def discover(root=None):
    """Locate an external EMerge Python environment without executing anything.

    ``root`` (or ``FAIRBEAM_EMERGE_PYTHON``) is a virtual environment folder or a Python executable.
    There is no PATH lookup. Returns ``(python_path, site_packages)``.
    """
    root = root or os.environ.get("FAIRBEAM_EMERGE_PYTHON")
    if not root:
        raise FileNotFoundError("Set FAIRBEAM_EMERGE_PYTHON or --root to an external EMerge Python environment")
    path = Path(root).expanduser()
    if path.is_dir():
        directory = path.resolve()
        python = next((p for p in (directory / "Scripts" / "python.exe", directory / "bin" / "python",
                                   directory / "bin" / "python3") if p.is_file()), None)
        if python is None:
            raise FileNotFoundError(f"No Python executable found in the EMerge environment folder: {directory}")
    elif path.is_file():
        python = path.parent.resolve() / path.name  # keep the venv launcher; do not follow symlinks
    else:
        raise FileNotFoundError(f"EMerge Python environment not found: {path}")
    if os.name != "nt" and not os.access(python, os.X_OK):
        raise FileNotFoundError(f"Python executable is not executable: {python}")
    base = python.parent.parent if python.parent.name.lower() in ("scripts", "bin") else python.parent
    candidates = [base / "Lib" / "site-packages"]
    candidates += sorted((base / "lib").glob("python3.*/site-packages")) if (base / "lib").is_dir() else []
    site = next((c for c in candidates if c.is_dir()), None)
    if site is None:
        raise FileNotFoundError(f"No site-packages folder found next to {python}")
    return python, site


def emerge_version(site_packages):
    """Read the installed EMerge version from its dist-info METADATA (no execution), or ``None``."""
    for info in sorted(Path(site_packages).glob("emerge-*.dist-info")):
        try:
            text = (info / "METADATA").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if line.startswith("Version:"):
                return line.split(":", 1)[1].strip() or None
    return None


def capabilities(root=None):
    result = {"backend": "emerge-experimental", "platform": platform.system(),
              "machine": platform.machine(), "physics": ["wr90_waveguide_fixture"],
              "driven_ports": False, "design_translation": False, "radiation": False,
              "supported_emerge": list(SUPPORTED_EMERGE),
              "probe_executes_solver": False, "probe_executes_interpreter": False}
    try:
        python, site = discover(root)
        version = emerge_version(site)
        if version is None:
            raise FileNotFoundError(f"EMerge is not installed in this environment: {site}")
        result.update(available=True, python=str(python), emerge_version=version,
                      version_supported=version in SUPPORTED_EMERGE, python_sha256=digest(python))
    except (OSError, ValueError) as exc:
        result.update(available=False, reason=str(exc))
    return result


def validate_case(resolution):
    if not isinstance(resolution, str) or resolution not in RESOLUTIONS:
        raise ValueError(f"resolution must be one of {tuple(RESOLUTIONS)}")
    if RESOLUTIONS[resolution] is None:
        raise ValueError("fixture resolutions not yet frozen")


def case(resolution):
    """The JSON document handed to the worker: the fixed fixture and nothing else."""
    validate_case(resolution)
    return {"schema": "fairbeam-emerge-fixture-case/1", "physics": "wr90_waveguide_fixture",
            "geometry": {"a_m": A_M, "b_m": B_M, "length_m": L_M, "walls": "PEC",
                         "fill": {"eps_r": 1.0, "mu_r": 1.0}},
            "frequency_hz": list(FREQUENCIES_HZ),
            "ports": [{"name": "port1", "face_z_m": 0.0, "mode": "TE10"},
                      {"name": "port2", "face_z_m": L_M, "mode": "TE10"}],
            "resolution": {"name": resolution, "value": RESOLUTIONS[resolution]},
            "phasor_convention_out": PHASOR}


def analytic(frequency_hz):
    """Analytic S21 of the straight guide, ``exp(+i omega t)``, reference planes at the port faces."""
    k0 = 2 * math.pi * frequency_hz / C0
    cutoff = (math.pi / A_M) ** 2
    if k0 * k0 <= cutoff:
        raise ValueError("Frequency is below the TE10 cutoff")
    return cmath.exp(-1j * math.sqrt(k0 * k0 - cutoff) * L_M)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _series(raw, key):
    values = raw.get(key)
    if not isinstance(values, list) or len(values) != len(FREQUENCIES_HZ) or not all(map(_number, values)):
        raise ValueError(f"{key} must be {len(FREQUENCIES_HZ)} finite numbers")
    return [float(v) for v in values]


def assess(raw):
    """Check the worker's raw S-parameters against the analytic reference and the criteria."""
    if not isinstance(raw, dict):
        raise ValueError("Raw result must be an object")
    frequencies = raw.get("frequency_hz")
    if (not isinstance(frequencies, list) or not all(map(_number, frequencies))
            or [float(f) for f in frequencies] != list(FREQUENCIES_HZ)):
        raise ValueError("Raw frequencies must equal the fixture frequency list")
    native = raw.get("phasor_convention")
    if native not in NATIVE_PHASORS:
        raise ValueError(f"phasor_convention must be one of {NATIVE_PHASORS}")
    s11 = [complex(r, i) for r, i in zip(_series(raw, "s11_re"), _series(raw, "s11_im"))]
    s21 = [complex(r, i) for r, i in zip(_series(raw, "s21_re"), _series(raw, "s21_im"))]
    if native != PHASOR:  # convert once, here
        s11, s21 = [v.conjugate() for v in s11], [v.conjugate() for v in s21]
    context = {}
    if "emerge_version" in raw:
        if not isinstance(raw["emerge_version"], str):
            raise ValueError("emerge_version must be a string")
        context["emerge_version"] = raw["emerge_version"]
    if "elapsed_seconds" in raw:
        if not _number(raw["elapsed_seconds"]) or raw["elapsed_seconds"] < 0:
            raise ValueError("elapsed_seconds must be a finite non-negative number")
        context["elapsed_seconds"] = float(raw["elapsed_seconds"])
    if "mesh" in raw:
        mesh = raw["mesh"]
        if (not isinstance(mesh, dict) or set(mesh) != {"nodes", "tetrahedra"}
                or any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in mesh.values())):
            raise ValueError("mesh must hold non-negative integer nodes and tetrahedra")
        context["mesh"] = {"nodes": mesh["nodes"], "tetrahedra": mesh["tetrahedra"]}
    reference = [analytic(f) for f in FREQUENCIES_HZ]
    phase_error = [180.0 if v == 0 else abs(math.degrees(cmath.phase(v * ref.conjugate())))
                   for v, ref in zip(s21, reference)]
    passivity = [abs(a) ** 2 + abs(b) ** 2 for a, b in zip(s11, s21)]
    metrics = {"s11_max": max(abs(v) for v in s11), "s21_min": min(abs(v) for v in s21),
               "phase_error_deg_max": max(phase_error), "passivity_max": max(passivity),
               "s11_abs": [abs(v) for v in s11], "s21_abs": [abs(v) for v in s21],
               "phase_error_deg": phase_error, "passivity": passivity}
    passed = (metrics["s11_max"] <= CRITERIA["s11_max"] and metrics["s21_min"] >= CRITERIA["s21_min"]
              and metrics["phase_error_deg_max"] <= CRITERIA["phase_error_deg_max"]
              and metrics["passivity_max"] <= CRITERIA["passivity_max"])
    return {"schema": RESULT_SCHEMA, "status": "results_validated" if passed else "validation_failed",
            "frequency_hz": list(FREQUENCIES_HZ),
            "s11_re": [v.real for v in s11], "s11_im": [v.imag for v in s11],
            "s21_re": [v.real for v in s21], "s21_im": [v.imag for v in s21],
            "analytic_s21_re": [v.real for v in reference], "analytic_s21_im": [v.imag for v in reference],
            "metrics": metrics, "criteria": dict(CRITERIA), "phasor_convention": PHASOR,
            "native_phasor_convention": native, **context,
            "precision_converged": False, "qualifies_driven_antenna": False,
            "limitations": list(LIMITATIONS)}


def _text(value):
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return value or ""


def design_case_ok(case):
    """Structural check of an admitted design case; raises ``ValueError`` if unusable."""
    if not isinstance(case, dict) or case.get("kind") != "design":
        raise ValueError("Design case must have kind 'design'")
    if case.get("phasor_convention_out") != PHASOR:
        raise ValueError("phasor_convention_out must be exp(+i omega t)")
    if not _number(case.get("resolution")) or not 0 < case["resolution"] <= 0.5:
        raise ValueError("resolution must be a wavelength fraction in (0, 0.5]")
    frequencies = case.get("frequencies_hz")
    if (not isinstance(frequencies, list) or len(frequencies) < 3
            or not all(map(_number, frequencies)) or any(f <= 0 for f in frequencies)):
        raise ValueError("frequencies_hz must be at least three positive finite numbers")
    if list(frequencies) != sorted(frequencies):
        raise ValueError("frequencies_hz must be ascending")
    boxes, sheets, port, air = case.get("boxes"), case.get("sheets"), case.get("port"), case.get("air")
    if not isinstance(boxes, list) or not boxes or not isinstance(sheets, list) or not sheets:
        raise ValueError("Design case needs dielectric boxes and PEC sheets")
    if not isinstance(port, dict) or not isinstance(air, dict):
        raise ValueError("Design case needs port and air objects")
    if not _number(port.get("z0")) or port["z0"] <= 0:
        raise ValueError("port.z0 must be a positive finite number")
    for key in ("width", "height"):
        if not _number(port.get(key)) or port[key] <= 0:
            raise ValueError(f"port.{key} must be a positive finite number")
    if port.get("direction_axis") not in (0, 1, 2) or port.get("sign") not in (1, -1):
        raise ValueError("port.direction_axis and port.sign are invalid")
    if not isinstance(case.get("limitations"), list) or not isinstance(case.get("pec_approximations"), list):
        raise ValueError("limitations and pec_approximations must be lists")
    return True


def assess_design(raw, case):
    """Check design raw S11 against the Level B schema rules; always ``results_exported`` if ok."""
    design_case_ok(case)
    if not isinstance(raw, dict):
        raise ValueError("Raw result must be an object")
    expected = [float(f) for f in case["frequencies_hz"]]
    frequencies = raw.get("frequency_hz")
    if (not isinstance(frequencies, list) or not all(map(_number, frequencies))
            or [float(f) for f in frequencies] != expected):
        raise ValueError("Raw frequencies must equal the case frequency list")
    native = raw.get("phasor_convention")
    if native != PHASOR:
        raise ValueError(f"phasor_convention must be {PHASOR}")
    if "native_phasor_convention" in raw and raw["native_phasor_convention"] != PHASOR:
        raise ValueError(f"native_phasor_convention must be {PHASOR}")
    count = len(expected)

    def series(key):
        values = raw.get(key)
        if not isinstance(values, list) or len(values) != count or not all(map(_number, values)):
            raise ValueError(f"{key} must be {count} finite numbers")
        return [float(v) for v in values]

    s11 = [complex(r, i) for r, i in zip(series("s11_re"), series("s11_im"))]
    if any(abs(v) > S11_ABS_MAX for v in s11):
        raise ValueError(f"|S11| exceeds {S11_ABS_MAX}")
    z_ref = raw.get("z_ref", case["port"]["z0"])
    if not _number(z_ref) or z_ref <= 0:
        raise ValueError("z_ref must be a positive finite number")
    context = {"z_ref": float(z_ref)}
    if "emerge_version" in raw:
        if not isinstance(raw["emerge_version"], str):
            raise ValueError("emerge_version must be a string")
        context["emerge_version"] = raw["emerge_version"]
    if "elapsed_seconds" in raw:
        if not _number(raw["elapsed_seconds"]) or raw["elapsed_seconds"] < 0:
            raise ValueError("elapsed_seconds must be a finite non-negative number")
        context["elapsed_seconds"] = float(raw["elapsed_seconds"])
    if "mesh" in raw:
        mesh = raw["mesh"]
        if (not isinstance(mesh, dict) or set(mesh) != {"nodes", "tetrahedra"}
                or any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in mesh.values())):
            raise ValueError("mesh must hold non-negative integer nodes and tetrahedra")
        context["mesh"] = {"nodes": mesh["nodes"], "tetrahedra": mesh["tetrahedra"]}
    settings = {"resolution": case["resolution"], "frequencies_hz": expected}
    if "resolution_name" in case:
        settings["resolution_name"] = case["resolution_name"]
    limitations = list(case["limitations"])
    if isinstance(raw.get("limitations"), list):
        limitations = list(raw["limitations"])
    pec = list(case["pec_approximations"])
    if isinstance(raw.get("pec_approximations"), list):
        pec = list(raw["pec_approximations"])
    return {"schema": DESIGN_RESULT_SCHEMA, "status": "results_exported",
            "frequency_hz": expected,
            "s11_re": [v.real for v in s11], "s11_im": [v.imag for v in s11],
            "settings": settings, "phasor_convention": PHASOR,
            "native_phasor_convention": native, **context,
            "precision_converged": False, "gain_qualified": False,
            "limitations": limitations, "pec_approximations": pec}


def run_fixture(out, *, root=None, resolution="coarse", experimental=False):
    if not experimental:
        raise ValueError("Explicit --experimental opt-in is required")
    validate_case(resolution)
    python, site = discover(root)
    if not WORKER.is_file():
        raise FileNotFoundError(f"EMerge worker script not found: {WORKER}")
    directory = Path(out).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {"schema": MANIFEST_SCHEMA, "backend": "emerge-experimental",
                "physics": "wr90_waveguide_fixture", "resolution": resolution,
                "resolution_value": RESOLUTIONS[resolution], "threads": 1, "status": "inputs_generated",
                "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "input_provenance": "fixed WR-90 fixture constants; analytic straight-guide reference",
                "phasor_convention": PHASOR, "python": str(python), "python_sha256": digest(python),
                "emerge_version": emerge_version(site), "generator_sha256": digest(__file__)}

    def save():
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    (directory / "case.json").write_text(json.dumps(case(resolution), indent=2, allow_nan=False) + "\n",
                                         encoding="utf-8")
    shutil.copyfile(WORKER, directory / WORKER.name)
    manifest["worker_sha256"] = digest(directory / WORKER.name)
    manifest["case_sha256"] = digest(directory / "case.json")
    save()
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env.update(OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", NUMBA_NUM_THREADS="1",
               MPLBACKEND="Agg", PYVISTA_OFF_SCREEN="true")
    try:
        manifest["status"] = "solver_started"
        save()
        start = time.monotonic()
        try:
            # -X utf8: EMerge's numba first-compile banner prints U+26A0; -I ignores PYTHONUTF8.
            process = subprocess.run([str(python), "-I", "-X", "utf8", WORKER.name, "case.json"],
                                     cwd=directory, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                     timeout=WORKER_TIMEOUT_S,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except subprocess.TimeoutExpired as exc:
            (directory / "worker.log").write_text(_text(exc.stdout), encoding="utf-8")
            raise RuntimeError(f"worker exceeded {WORKER_TIMEOUT_S} second limit") from exc
        (directory / "worker.log").write_text(_text(process.stdout), encoding="utf-8")
        manifest["worker_seconds"] = time.monotonic() - start
        manifest["worker_exit_code"] = process.returncode
        if process.returncode:
            raise RuntimeError(f"worker failed (exit {process.returncode}); inspect worker.log")
        if not (directory / "raw.json").is_file():
            raise RuntimeError("worker exited 0 but wrote no raw.json; inspect worker.log")
        manifest["status"] = "solver_returned"
        save()
        raw = json.loads((directory / "raw.json").read_text(encoding="utf-8"))
        result = assess(raw)
        result["raw_sha256"] = {"raw.json": digest(directory / "raw.json")}
        (directory / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                                               encoding="utf-8")
        manifest["status"] = result["status"]
        save()
        if result["status"] != "results_validated":
            raise ValueError("Fixture reference criteria failed; raw output retained")
        return result
    except BaseException as exc:
        if manifest["status"] != "validation_failed":
            manifest["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        manifest["error"] = str(exc)
        save()
        raise


def run_design(out, case, *, root=None, experimental=False):
    """Run an admitted Design case through the EMerge worker (opt-in; fresh ``out`` directory)."""
    if not experimental:
        raise ValueError("Explicit --experimental opt-in is required")
    design_case_ok(case)
    python, site = discover(root)
    if not WORKER.is_file():
        raise FileNotFoundError(f"EMerge worker script not found: {WORKER}")
    directory = Path(out).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {"schema": DESIGN_MANIFEST_SCHEMA, "backend": "emerge-experimental",
                "physics": "design_driven", "kind": "design",
                "resolution": case.get("resolution_name", case["resolution"]),
                "resolution_value": case["resolution"], "threads": 1, "status": "inputs_generated",
                "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "input_provenance": "admitted Design case from emerge_design.admit",
                "phasor_convention": PHASOR, "python": str(python), "python_sha256": digest(python),
                "emerge_version": emerge_version(site), "generator_sha256": digest(__file__)}

    def save():
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    (directory / "case.json").write_text(json.dumps(case, indent=2, allow_nan=False) + "\n",
                                         encoding="utf-8")
    shutil.copyfile(WORKER, directory / WORKER.name)
    manifest["worker_sha256"] = digest(directory / WORKER.name)
    manifest["case_sha256"] = digest(directory / "case.json")
    save()
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    env.update(OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", NUMBA_NUM_THREADS="1",
               MPLBACKEND="Agg", PYVISTA_OFF_SCREEN="true")
    try:
        manifest["status"] = "solver_started"
        save()
        start = time.monotonic()
        try:
            process = subprocess.run([str(python), "-I", "-X", "utf8", WORKER.name, "case.json"],
                                     cwd=directory, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                     timeout=DESIGN_WORKER_TIMEOUT_S,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except subprocess.TimeoutExpired as exc:
            (directory / "worker.log").write_text(_text(exc.stdout), encoding="utf-8")
            raise RuntimeError(f"worker exceeded {DESIGN_WORKER_TIMEOUT_S} second limit") from exc
        (directory / "worker.log").write_text(_text(process.stdout), encoding="utf-8")
        manifest["worker_seconds"] = time.monotonic() - start
        manifest["worker_exit_code"] = process.returncode
        if process.returncode:
            raise RuntimeError(f"worker failed (exit {process.returncode}); inspect worker.log")
        if not (directory / "raw.json").is_file():
            raise RuntimeError("worker exited 0 but wrote no raw.json; inspect worker.log")
        manifest["status"] = "solver_returned"
        save()
        raw = json.loads((directory / "raw.json").read_text(encoding="utf-8"))
        result = assess_design(raw, case)
        result["raw_sha256"] = {"raw.json": digest(directory / "raw.json")}
        (directory / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                                               encoding="utf-8")
        manifest["status"] = result["status"]
        save()
        if result["status"] != "results_exported":
            raise ValueError("Design result was not exported; raw output retained")
        return result
    except BaseException as exc:
        if manifest["status"] != "results_exported":
            manifest["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        manifest["error"] = str(exc)
        save()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="external EMerge environment folder or python executable "
                                       "(or FAIRBEAM_EMERGE_PYTHON)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities", help="discover the environment without running anything")
    waveguide = commands.add_parser("waveguide", help="run the fixed WR-90 waveguide fixture")
    waveguide.add_argument("--experimental", action="store_true", help="explicitly opt into research execution")
    waveguide.add_argument("--out", type=Path, required=True, help="fresh output directory")
    waveguide.add_argument("--resolution", choices=tuple(RESOLUTIONS), default="coarse")
    design = commands.add_parser("design", help="run an admitted Design case through EMerge")
    design.add_argument("--experimental", action="store_true", help="explicitly opt into research execution")
    design.add_argument("--case", type=Path, required=True, help="admitted design case JSON")
    design.add_argument("--out", type=Path, required=True, help="fresh output directory")
    args = parser.parse_args(argv)
    try:
        if args.command == "capabilities":
            result = capabilities(args.root)
        elif args.command == "waveguide":
            result = run_fixture(args.out, root=args.root, resolution=args.resolution,
                                 experimental=args.experimental)
        else:
            case = json.loads(Path(args.case).read_text(encoding="utf-8"))
            result = run_design(args.out, case, root=args.root, experimental=args.experimental)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"fairbeam-emerge: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
