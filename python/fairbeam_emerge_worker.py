"""EMerge worker for the fixed WR-90 waveguide fixture.

Runs INSIDE the external EMerge environment (``fairbeam_emerge.py`` starts it as a separate
process with that environment's interpreter). This is the only Fairbeam file that imports EMerge;
it imports nothing from ``fairbeam``. Usage: ``python fairbeam_emerge_worker.py case.json``.

It builds exactly the fixture described by ``case.json``, solves it in this process (no worker
threads or processes of EMerge's own), and writes ``raw.json`` next to the case. The adapter checks
the raw S-parameters against the analytic reference; nothing here adjusts a result.
"""
import json
import math
import os
from pathlib import Path
import sys
import time

CASE_SCHEMA = "fairbeam-emerge-fixture-case/1"
NATIVE_PHASOR = "exp(+i omega t)"
FREQUENCY_RTOL = 1e-9
THREAD_VARIABLES = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMBA_NUM_THREADS",
                    "VECLIB_NUM_THREADS", "NUMEXPR_NUM_THREADS")


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load_case(path):
    """Read and structurally check ``case.json``; the adapter owns the fixture values."""
    case = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(case, dict) or case.get("schema") != CASE_SCHEMA:
        raise ValueError(f"case.json must have schema {CASE_SCHEMA}")
    if case.get("physics") != "wr90_waveguide_fixture":
        raise ValueError("case.json physics must be wr90_waveguide_fixture")
    geometry = case.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("walls") != "PEC":
        raise ValueError("geometry must describe PEC walls")
    for key in ("a_m", "b_m", "length_m"):
        if not _number(geometry.get(key)) or geometry[key] <= 0:
            raise ValueError(f"geometry.{key} must be a positive finite number")
    fill = geometry.get("fill")
    if not isinstance(fill, dict) or fill.get("eps_r") != 1.0 or fill.get("mu_r") != 1.0:
        raise ValueError("Only an air fill (eps_r = mu_r = 1) is supported")
    frequencies = case.get("frequency_hz")
    if (not isinstance(frequencies, list) or not frequencies or not all(map(_number, frequencies))
            or any(f <= 0 for f in frequencies) or frequencies != sorted(set(frequencies))):
        raise ValueError("frequency_hz must be strictly ascending positive finite numbers")
    ports = case.get("ports")
    if (not isinstance(ports, list) or len(ports) != 2
            or [p.get("mode") if isinstance(p, dict) else None for p in ports] != ["TE10", "TE10"]
            or [p.get("face_z_m") for p in ports] != [0.0, geometry["length_m"]]):
        raise ValueError("ports must be two TE10 ports on the z = 0 and z = length faces")
    resolution = case.get("resolution")
    if (not isinstance(resolution, dict) or not _number(resolution.get("value"))
            or not 0 < resolution["value"] <= 0.5):
        raise ValueError("resolution.value must be a wavelength fraction in (0, 0.5]")
    if case.get("phasor_convention_out") != "exp(+i omega t)":
        raise ValueError("phasor_convention_out must be exp(+i omega t)")
    return case


def match_frequencies(expected, computed):
    """Check EMerge's frequency axis against the case values (relative 1e-9); return the case values."""
    computed = [float(f) for f in computed]
    if len(computed) != len(expected):
        raise ValueError(f"EMerge returned {len(computed)} frequencies, expected {len(expected)}")
    for want, got in zip(expected, computed):
        if not math.isfinite(got) or abs(got - want) > FREQUENCY_RTOL * abs(want):
            raise ValueError(f"EMerge frequency {got!r} differs from the case value {want!r}")
    return [float(f) for f in expected]


def _series(values, name, count):
    flat = [complex(v) for v in values]
    if len(flat) != count:
        raise ValueError(f"{name} has {len(flat)} points, expected {count}")
    if not all(math.isfinite(v.real) and math.isfinite(v.imag) for v in flat):
        raise ValueError(f"{name} contains a non-finite value")
    return flat


def build_raw(case, emerge_version, frequencies, s11, s21, mesh, elapsed_seconds):
    """Assemble ``raw.json`` content. S-parameters are EMerge's, unmodified."""
    expected = case["frequency_hz"]
    frequencies = match_frequencies(expected, frequencies)
    s11 = _series(s11, "S11", len(frequencies))
    s21 = _series(s21, "S21", len(frequencies))
    raw = {"emerge_version": str(emerge_version), "frequency_hz": frequencies,
           "s11_re": [v.real for v in s11], "s11_im": [v.imag for v in s11],
           "s21_re": [v.real for v in s21], "s21_im": [v.imag for v in s21],
           "phasor_convention": NATIVE_PHASOR,
           "elapsed_seconds": float(elapsed_seconds),
           "solver_setup": {"resolution": case["resolution"], "parallel": False, "multi_processing": False,
                            "port_mode_alignment": "E field along +y at both ports",
                            "sparam_cap_single": False, "sparam_cap_column": False,
                            "sparam_enforce_reciprocity": False}}
    if mesh:
        raw["mesh"] = {"nodes": int(mesh["nodes"]), "tetrahedra": int(mesh["tetrahedra"])}
    return raw


def solve(case):
    """Build and solve the fixture with EMerge. Imports EMerge, so call it only in the EMerge environment."""
    for name in THREAD_VARIABLES:  # EMerge's import only uses setdefault (OMP 1, MKL 4, NUMBA 4); force 1
        os.environ[name] = "1"
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")
    os.environ["EMERGE_BASE_PATH"] = str(Path.cwd())  # keep any EMerge output inside the case folder

    import numpy as np
    import emerge as em

    started = time.monotonic()
    geometry = case["geometry"]
    sim = em.Simulation("fairbeam_emerge_fixture", loglevel="INFO", save_file=False, write_log=False)
    # EMerge post-processes S-parameters by default (caps |S| at 1 and power-normalizes columns). That
    # would hide a passivity violation the fixture is meant to detect, so the raw values are kept.
    sim.settings.mw_cap_sp_single = False
    sim.settings.mw_cap_sp_col = False
    sim.settings.mw_recip_sp = False

    box = em.geo.Box(geometry["a_m"], geometry["b_m"], geometry["length_m"], position=(0, 0, 0))
    sim.set_resolution(case["resolution"]["value"])  # set before the frequencies: it scales the mesh size
    sim.mw.set_frequency(list(case["frequency_hz"]))  # explicit list: the exact five fixture points
    sim.commit_geometry()  # selections made earlier are rejected by EMerge as pre-fragment

    for face in ("left", "right", "front", "back"):
        sim.mw.bc.PEC(box.face(face))
    ports = [sim.mw.bc.RectangularWaveguide(box.face(face), number, mode=(1, 0), mode_type="TE", er=1.0)
             for number, face in ((1, "bottom"), (2, "top"))]  # bottom is -Z (z = 0), top is +Z (z = L)
    for port in ports:
        port.align_modes(em.YAX)  # same positive E direction at both ports; no phase or sign trimming
        width, height = port.dims
        if (abs(width - geometry["a_m"]) > 1e-6 * geometry["a_m"]
                or abs(height - geometry["b_m"]) > 1e-6 * geometry["b_m"]):
            raise ValueError(f"port {port.port_number} face is {width} x {height} m, not the fixture cross-section")

    sim.generate_mesh()
    mesh = {"nodes": int(sim.mesh.n_nodes), "tetrahedra": int(sim.mesh.n_tets)}
    data = sim.mw.run_sweep(parallel=False, multi_processing=False)  # solved in this process

    grid = data.scalar.grid
    frequencies = np.asarray(data.scalar.axis("freq"), dtype=float).reshape(-1)
    s11 = np.asarray(grid.S(1, 1)).reshape(-1)
    s21 = np.asarray(grid.S(2, 1)).reshape(-1)  # S(i, j): response at port i to a drive at port j
    return build_raw(case, em.__version__, frequencies.tolist(), s11.tolist(), s21.tolist(), mesh,
                     time.monotonic() - started)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: fairbeam_emerge_worker.py case.json", file=sys.stderr)
        return 2
    case = load_case(argv[0])
    raw = solve(case)
    target = Path.cwd() / "raw.json"
    temporary = target.with_name("raw.json.tmp")
    temporary.write_text(json.dumps(raw, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
