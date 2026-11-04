"""EMerge worker for the WR-90 fixture, admitted Designs, and planar two-port cases.

Runs INSIDE the external EMerge environment (``fairbeam_emerge.py`` starts it as a separate
process with that environment's interpreter). This is the only Fairbeam file that imports EMerge;
it imports nothing from ``fairbeam``. Usage: ``python fairbeam_emerge_worker.py case.json``.

It builds exactly the case described by ``case.json``, solves it in this process, and writes
``raw.json`` next to the case. Threading uses EMerge 3 ``run_sweep(nthreads=…)`` or
``run_sweep_distributed`` (thread workers) from ``case["nthreads"]``. The adapter checks the raw
S-parameters; nothing here adjusts a result.
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
# AbsorbingBoundary: constructor default is order=2 / abctype="B"
# (physics/microwave/bcs/boundary_conditions.py:138-160). The docstring claims only first order is
# supported, but assembler.py:668-675 / 1025-1030 / 1268-1273 applies the second-order correction
# when bc.order == 2. Level B therefore runs the default second-order ABC.
ABC_ORDER = 2
ABC_TYPE = "B"


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load_case(path):
    """Read and structurally check ``case.json``; the adapter owns the fixture/design values."""
    case = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(case, dict):
        raise ValueError("case.json must be an object")
    if case.get("kind") == "design":
        return _load_design_case(case)
    if case.get("kind") == "planar":
        return _load_planar_case(case)
    return _load_fixture_case(case)


def _load_fixture_case(case):
    if case.get("schema") != CASE_SCHEMA:
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


def _point3(value, label):
    if (not isinstance(value, list) or len(value) != 3 or not all(map(_number, value))):
        raise ValueError(f"{label} must be three finite numbers")
    return [float(v) for v in value]


def _load_design_case(case):
    if case.get("phasor_convention_out") != NATIVE_PHASOR:
        raise ValueError("phasor_convention_out must be exp(+i omega t)")
    if not _number(case.get("resolution")) or not 0 < case["resolution"] <= 0.5:
        raise ValueError("resolution must be a wavelength fraction in (0, 0.5]")
    frequencies = case.get("frequencies_hz")
    if (not isinstance(frequencies, list) or len(frequencies) < 3
            or not all(map(_number, frequencies)) or any(f <= 0 for f in frequencies)
            or frequencies != sorted(frequencies)):
        raise ValueError("frequencies_hz must be ascending positive finite numbers (at least 3)")
    boxes = case.get("boxes")
    if not isinstance(boxes, list) or not boxes:
        raise ValueError("boxes must be a non-empty list")
    for i, box in enumerate(boxes):
        if not isinstance(box, dict):
            raise ValueError(f"boxes[{i}] must be an object")
        lo, hi = _point3(box.get("lo"), f"boxes[{i}].lo"), _point3(box.get("hi"), f"boxes[{i}].hi")
        if any(hi[k] <= lo[k] for k in range(3)):
            raise ValueError(f"boxes[{i}] must have positive volume")
        for key in ("eps_r", "mu_r", "tan_d"):
            if not _number(box.get(key)) or (key != "tan_d" and box[key] <= 0) or box["tan_d"] < 0:
                raise ValueError(f"boxes[{i}].{key} must be a valid material number")
    sheets = case.get("sheets")
    if not isinstance(sheets, list) or not sheets:
        raise ValueError("sheets must be a non-empty list")
    for i, sheet in enumerate(sheets):
        if not isinstance(sheet, dict):
            raise ValueError(f"sheets[{i}] must be an object")
        lo, hi = _point3(sheet.get("lo"), f"sheets[{i}].lo"), _point3(sheet.get("hi"), f"sheets[{i}].hi")
        axis = sheet.get("normal_axis")
        if axis not in (0, 1, 2) or type(axis) is not int:
            raise ValueError(f"sheets[{i}].normal_axis must be 0, 1 or 2")
        if hi[axis] != lo[axis] or any(hi[k] <= lo[k] for k in range(3) if k != axis):
            raise ValueError(f"sheets[{i}] must be a finite plate normal to axis {axis}")
    port = case.get("port")
    if not isinstance(port, dict):
        raise ValueError("port must be an object")
    lo, hi = _point3(port.get("lo"), "port.lo"), _point3(port.get("hi"), "port.hi")
    axis = port.get("direction_axis")
    if axis not in (0, 1, 2) or type(axis) is not int:
        raise ValueError("port.direction_axis must be 0, 1 or 2")
    if port.get("sign") not in (1, -1):
        raise ValueError("port.sign must be 1 or -1")
    for key in ("width", "height", "z0"):
        if not _number(port.get(key)) or port[key] <= 0:
            raise ValueError(f"port.{key} must be a positive finite number")
    if hi[axis] - lo[axis] <= 0:
        raise ValueError("port must span a nonzero gap along its direction")
    air = case.get("air")
    if not isinstance(air, dict):
        raise ValueError("air must be an object")
    air_lo, air_hi = _point3(air.get("lo"), "air.lo"), _point3(air.get("hi"), "air.hi")
    if any(air_hi[k] <= air_lo[k] for k in range(3)):
        raise ValueError("air must have positive volume")
    if not isinstance(case.get("limitations"), list) or not isinstance(case.get("pec_approximations"), list):
        raise ValueError("limitations and pec_approximations must be lists")
    return case


def _load_planar_case(case):
    if case.get("phasor_convention_out") != NATIVE_PHASOR:
        raise ValueError("phasor_convention_out must be exp(+i omega t)")
    if not _number(case.get("resolution")) or not 0 < case["resolution"] <= 0.5:
        raise ValueError("resolution must be a wavelength fraction in (0, 0.5]")
    if case.get("enclosure") not in ("shielded", "open"):
        raise ValueError("enclosure must be shielded or open")
    if not _number(case.get("metal_edge_m")) or case["metal_edge_m"] <= 0:
        raise ValueError("metal_edge_m must be a positive finite number")
    frequencies = case.get("frequencies_hz")
    if (not isinstance(frequencies, list) or len(frequencies) < 3
            or not all(map(_number, frequencies)) or any(f <= 0 for f in frequencies)
            or frequencies != sorted(frequencies)):
        raise ValueError("frequencies_hz must be ascending positive finite numbers (at least 3)")
    substrate = case.get("substrate")
    if not isinstance(substrate, dict):
        raise ValueError("substrate must be an object")
    lo, hi = _point3(substrate.get("lo"), "substrate.lo"), _point3(substrate.get("hi"), "substrate.hi")
    if any(hi[k] <= lo[k] for k in range(3)):
        raise ValueError("substrate must have positive volume")
    for key in ("eps_r", "mu_r", "tan_d"):
        if not _number(substrate.get(key)) or (key != "tan_d" and substrate[key] <= 0) or substrate["tan_d"] < 0:
            raise ValueError(f"substrate.{key} must be a valid material number")
    if not _number(case.get("ground_z")):
        raise ValueError("ground_z must be a finite number")
    traces = case.get("traces")
    if not isinstance(traces, list) or not traces:
        raise ValueError("traces must be a non-empty list")
    for i, trace in enumerate(traces):
        if not isinstance(trace, dict):
            raise ValueError(f"traces[{i}] must be an object")
        if not _number(trace.get("z")):
            raise ValueError(f"traces[{i}].z must be a finite number")
        xy = trace.get("xy")
        if not isinstance(xy, list) or len(xy) < 3:
            raise ValueError(f"traces[{i}].xy must have at least 3 vertices")
        for j, point in enumerate(xy):
            if (not isinstance(point, list) or len(point) != 2
                    or not all(map(_number, point))):
                raise ValueError(f"traces[{i}].xy[{j}] must be two finite numbers")
    terminals = case.get("terminals")
    if not isinstance(terminals, list) or len(terminals) != 2:
        raise ValueError("terminals must be a list of two ports")
    numbers = []
    for i, port in enumerate(terminals):
        if not isinstance(port, dict):
            raise ValueError(f"terminals[{i}] must be an object")
        lo, hi = _point3(port.get("lo"), f"terminals[{i}].lo"), _point3(port.get("hi"), f"terminals[{i}].hi")
        flat = [k for k in range(3) if hi[k] == lo[k]]
        if len(flat) != 1:
            raise ValueError(f"terminals[{i}] must be flat on exactly one axis")
        for key in ("width", "height", "z0"):
            if not _number(port.get(key)) or port[key] <= 0:
                raise ValueError(f"terminals[{i}].{key} must be a positive finite number")
        if type(port.get("number")) is not int or port["number"] not in (1, 2):
            raise ValueError(f"terminals[{i}].number must be 1 or 2")
        numbers.append(port["number"])
    if sorted(numbers) != [1, 2]:
        raise ValueError("terminals must be port numbers 1 and 2")
    air = case.get("air")
    if not isinstance(air, dict):
        raise ValueError("air must be an object")
    air_lo, air_hi = _point3(air.get("lo"), "air.lo"), _point3(air.get("hi"), "air.hi")
    if any(air_hi[k] <= air_lo[k] for k in range(3)):
        raise ValueError("air must have positive volume")
    if not isinstance(case.get("limitations"), list) or not isinstance(case.get("pec_approximations"), list):
        raise ValueError("limitations and pec_approximations must be lists")
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
    """Assemble fixture ``raw.json`` content. S-parameters are EMerge's, unmodified."""
    expected = case["frequency_hz"]
    frequencies = match_frequencies(expected, frequencies)
    s11 = _series(s11, "S11", len(frequencies))
    s21 = _series(s21, "S21", len(frequencies))
    raw = {"emerge_version": str(emerge_version), "frequency_hz": frequencies,
           "s11_re": [v.real for v in s11], "s11_im": [v.imag for v in s11],
           "s21_re": [v.real for v in s21], "s21_im": [v.imag for v in s21],
           "phasor_convention": NATIVE_PHASOR,
           "elapsed_seconds": float(elapsed_seconds),
           "solver_setup": {"resolution": case["resolution"],
                            "port_mode_alignment": "E field along +y at both ports",
                            "sparam_cap_single": False, "sparam_cap_column": False,
                            "sparam_enforce_reciprocity": False,
                            **(case.get("_sweep_setup") or {"nthreads": _nthreads(case)})}}
    if mesh:
        raw["mesh"] = {"nodes": int(mesh["nodes"]), "tetrahedra": int(mesh["tetrahedra"])}
    return raw


def build_design_raw(case, emerge_version, frequencies, s11, mesh, elapsed_seconds):
    """Assemble design ``raw.json`` content. S11 is EMerge's, unmodified."""
    expected = case["frequencies_hz"]
    frequencies = match_frequencies(expected, frequencies)
    s11 = _series(s11, "S11", len(frequencies))
    raw = {"kind": "design", "emerge_version": str(emerge_version), "frequency_hz": frequencies,
           "s11_re": [v.real for v in s11], "s11_im": [v.imag for v in s11],
           "z_ref": float(case["port"]["z0"]),
           "phasor_convention": NATIVE_PHASOR,
           "native_phasor_convention": NATIVE_PHASOR,
           "elapsed_seconds": float(elapsed_seconds),
           "solver_setup": {"resolution": case["resolution"],
                            "resolution_name": case.get("resolution_name"),
                            "abc_order": ABC_ORDER, "abc_type": ABC_TYPE,
                            "sparam_cap_single": False, "sparam_cap_column": False,
                            "sparam_enforce_reciprocity": False,
                            **(case.get("_sweep_setup") or {"nthreads": _nthreads(case)})},
           "limitations": list(case["limitations"]),
           "pec_approximations": list(case["pec_approximations"])}
    if mesh:
        raw["mesh"] = {"nodes": int(mesh["nodes"]), "tetrahedra": int(mesh["tetrahedra"])}
    return raw


def build_planar_raw(case, emerge_version, frequencies, s_params, mesh, elapsed_seconds):
    """Assemble planar ``raw.json`` content. S-parameters are EMerge's, unmodified.

    ``s_params`` maps ``"i,j"`` keys to complex sequences (response at i driven at j).
    """
    expected = case["frequencies_hz"]
    frequencies = match_frequencies(expected, frequencies)
    count = len(frequencies)
    s_out = {}
    for key in ("1,1", "2,1", "1,2", "2,2"):
        if key not in s_params:
            raise ValueError(f"missing S-parameter series {key}")
        series = _series(s_params[key], f"S{key}", count)
        s_out[key] = {"re": [v.real for v in series], "im": [v.imag for v in series]}
    terminals = sorted(case["terminals"], key=lambda t: t["number"])
    raw = {"kind": "planar", "emerge_version": str(emerge_version), "frequency_hz": frequencies,
           "s": s_out, "z_ref": [float(terminals[0]["z0"]), float(terminals[1]["z0"])],
           "enclosure": case["enclosure"],
           "phasor_convention": NATIVE_PHASOR,
           "native_phasor_convention": NATIVE_PHASOR,
           "elapsed_seconds": float(elapsed_seconds),
           "trace_count": len(case["traces"]),
           "solver_setup": {"resolution": case["resolution"],
                            "resolution_name": case.get("resolution_name"),
                            "enclosure": case["enclosure"],
                            "metal_edge_m": case["metal_edge_m"],
                            "abc_order": ABC_ORDER, "abc_type": ABC_TYPE,
                            "sparam_cap_single": False, "sparam_cap_column": False,
                            "sparam_enforce_reciprocity": False,
                            **(case.get("_sweep_setup") or {"nthreads": _nthreads(case)})},
           "limitations": list(case["limitations"]),
           "pec_approximations": list(case["pec_approximations"])}
    if mesh:
        raw["mesh"] = {"nodes": int(mesh["nodes"]), "tetrahedra": int(mesh["tetrahedra"])}
    return raw


def _nthreads(case):
    """Solver thread budget from the case (default 1). Caps at 64."""
    value = case.get("nthreads", 1)
    if type(value) is not int or value < 1:
        raise ValueError("nthreads must be a positive integer")
    return min(value, 64)


def _prepare_env(nthreads=1):
    """Pin BLAS/OpenMP/Numba to the case budget (EMerge import only setdefaults otherwise)."""
    text = str(max(1, int(nthreads)))
    for name in THREAD_VARIABLES:
        os.environ[name] = text
    os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")
    os.environ["EMERGE_BASE_PATH"] = str(Path.cwd())  # keep any EMerge output inside the case folder


def _run_frequency_sweep(sim, case):
    """Run the MW frequency sweep with EMerge 3 threading / optional distributed workers."""
    budget = _nthreads(case)
    frequencies = case.get("frequencies_hz") or case.get("frequency_hz") or []
    n_freq = len(frequencies)
    if n_freq >= 2 and budget >= 2:
        n_workers = min(n_freq, max(1, budget // 2), 8)
        per = max(1, budget // n_workers)
        data = sim.mw.run_sweep_distributed(n_workers=n_workers, nthreads=per, worker_type="thread")
        setup = {"mode": "distributed", "n_workers": n_workers, "nthreads": per,
                 "threads_budget": budget, "worker_type": "thread"}
        return data, setup
    data = sim.mw.run_sweep(nthreads=budget)
    return data, {"mode": "sequential", "nthreads": budget, "threads_budget": budget}


def _box(em, lo, hi):
    return em.geo.Box(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], position=tuple(lo))


def _plate(em, lo, hi, normal_axis):
    """Build a rectangular ``Plate`` from axis-aligned bounds (metres)."""
    u_axis, v_axis = [k for k in range(3) if k != normal_axis]
    origin = tuple(lo)
    u = [0.0, 0.0, 0.0]
    v = [0.0, 0.0, 0.0]
    u[u_axis] = hi[u_axis] - lo[u_axis]
    v[v_axis] = hi[v_axis] - lo[v_axis]
    return em.geo.Plate(origin, tuple(u), tuple(v))


def solve_fixture(case):
    """Build and solve the WR-90 fixture with EMerge. Imports EMerge, so call only in that env."""
    nthreads = _nthreads(case)
    _prepare_env(nthreads)
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
    data, sweep = _run_frequency_sweep(sim, case)
    case = {**case, "_sweep_setup": sweep}

    grid = data.scalar.grid
    frequencies = np.asarray(data.scalar.axis("freq"), dtype=float).reshape(-1)
    s11 = np.asarray(grid.S(1, 1)).reshape(-1)
    s21 = np.asarray(grid.S(2, 1)).reshape(-1)  # S(i, j): response at port i to a drive at port j
    return build_raw(case, em.__version__, frequencies.tolist(), s11.tolist(), s21.tolist(), mesh,
                     time.monotonic() - started)


def solve_design(case):
    """Build and solve an admitted Design case with EMerge. Imports EMerge, so call only in that env.

    Citations (EMerge 3.0.0b12 under site-packages/emerge/_emerge/):
    - LumpedPort voltage direction: physics/microwave/bcs/port_bcs.py:1453-1493, 1559-1599
      (uniform E along ``direction`` / ``Vdirection``; ``height`` is the extent along that axis;
      ``sign`` from the case is applied by negating the Axis).
    - AbsorbingBoundary order/abctype: bcs/boundary_conditions.py:135-188; assembler applies
      second-order correction when ``order == 2`` (assembler.py:668-675). Defaults used: order=2,
      abctype="B".
    - Priority: geometry.py:596-617, 924-980 — highest ``_priority`` wins for overlapping volumes;
      air uses ``background()`` so dielectric boxes (default priority 10) keep their material.
    - Plate on a dielectric face: geo/shapes.py:233-287; mesher.submit_objects fragments all
      registered GeoObject dimtags together (mesher.py:227-264), so PEC/port Plates do not need a
      separate embed/fragment call before ``commit_geometry``.
    """
    nthreads = _nthreads(case)
    _prepare_env(nthreads)
    import numpy as np
    import emerge as em

    started = time.monotonic()
    sim = em.Simulation("fairbeam_emerge_design", loglevel="INFO", save_file=False, write_log=False)
    sim.settings.mw_cap_sp_single = False
    sim.settings.mw_cap_sp_col = False
    sim.settings.mw_recip_sp = False

    air = _box(em, case["air"]["lo"], case["air"]["hi"]).background()
    for box in case["boxes"]:
        _box(em, box["lo"], box["hi"]).set_material(
            em.Material(box["eps_r"], box["mu_r"], box["tan_d"]))
    sheets = [_plate(em, sheet["lo"], sheet["hi"], sheet["normal_axis"]) for sheet in case["sheets"]]
    port = case["port"]
    # Admit keeps one transverse axis at zero extent; that axis is the plate normal.
    port_flat = [k for k in range(3) if port["hi"][k] == port["lo"][k]]
    if len(port_flat) != 1:
        raise ValueError("port plate must be flat on exactly one axis")
    port_plate = _plate(em, port["lo"], port["hi"], port_flat[0])

    sim.set_resolution(case["resolution"])
    sim.mw.set_frequency(list(case["frequencies_hz"]))
    sim.commit_geometry()  # fragments volumes and plates together; BCs after this

    for face in ("left", "right", "front", "back", "bottom", "top"):
        sim.mw.bc.AbsorbingBoundary(air.face(face), order=ABC_ORDER, abctype=ABC_TYPE)
    for sheet in sheets:
        sim.mw.bc.PEC(sheet)
    axes = (em.XAX, em.YAX, em.ZAX)
    direction = axes[port["direction_axis"]]
    if port["sign"] < 0:
        direction = -direction
    sim.mw.bc.LumpedPort(port_plate, 1, width=port["width"], height=port["height"],
                         direction=direction, Z0=port["z0"])

    sim.generate_mesh()
    mesh = {"nodes": int(sim.mesh.n_nodes), "tetrahedra": int(sim.mesh.n_tets)}
    data, sweep = _run_frequency_sweep(sim, case)
    case = {**case, "_sweep_setup": sweep}

    grid = data.scalar.grid
    frequencies = np.asarray(data.scalar.axis("freq"), dtype=float).reshape(-1)
    s11 = np.asarray(grid.S(1, 1)).reshape(-1)
    return build_design_raw(case, em.__version__, frequencies.tolist(), s11.tolist(), mesh,
                            time.monotonic() - started)


def solve_planar(case):
    """Build and solve an admitted planar two-port case with EMerge.

    Physics mirror the Level B2 Task 1 spike (originally measured on EMerge 2.8.9; pin is now 3.0.0b12): substrate ``Box``, zero-thickness
    ``XYPolygon.geo()`` PEC sheets, ``PEC`` on the substrate bottom, optional second-order ABC on
    the four sides and top when ``enclosure == "open"``, two ``LumpedPort`` strip-to-ground
    terminals (+z), and ``mesher.set_boundary_size`` on each trace (``metal_edge_m``, growth 3).
    """
    nthreads = _nthreads(case)
    _prepare_env(nthreads)
    import numpy as np
    import emerge as em

    started = time.monotonic()
    sim = em.Simulation("fairbeam_emerge_planar", loglevel="INFO", save_file=False, write_log=False)
    sim.settings.mw_cap_sp_single = False
    sim.settings.mw_cap_sp_col = False
    sim.settings.mw_recip_sp = False

    air = _box(em, case["air"]["lo"], case["air"]["hi"]).background()
    substrate = case["substrate"]
    diel = _box(em, substrate["lo"], substrate["hi"]).set_material(
        em.Material(substrate["eps_r"], substrate["mu_r"], substrate["tan_d"]))
    metals = []
    for i, trace in enumerate(case["traces"]):
        xs = [float(p[0]) for p in trace["xy"]]
        ys = [float(p[1]) for p in trace["xy"]]
        cs = em.GCS.displace(0.0, 0.0, float(trace["z"]))
        metal = em.geo.XYPolygon(xs, ys).geo(cs=cs, name=f"Cu_{i}")
        metal.set_material(em.lib.PEC)
        metals.append(metal)
    terminals = []
    for port in sorted(case["terminals"], key=lambda t: t["number"]):
        flat = [k for k in range(3) if port["hi"][k] == port["lo"][k]]
        if len(flat) != 1:
            raise ValueError(f"terminal {port['number']} must be flat on exactly one axis")
        terminals.append((port, _plate(em, port["lo"], port["hi"], flat[0])))

    sim.set_resolution(case["resolution"])
    sim.mw.set_frequency(list(case["frequencies_hz"]))
    sim.commit_geometry()

    sim.mw.bc.PEC(diel.bottom)
    if case["enclosure"] == "open":
        for face in ("left", "right", "front", "back", "top"):
            sim.mw.bc.AbsorbingBoundary(air.face(face), order=ABC_ORDER, abctype=ABC_TYPE)
    for metal in metals:
        sim.mw.bc.PEC(metal)
    for port, plate in terminals:
        sim.mw.bc.LumpedPort(plate, port["number"], width=port["width"], height=port["height"],
                             direction=em.ZAX, Z0=port["z0"])
    for metal in metals:
        sim.mesher.set_boundary_size(metal, case["metal_edge_m"], growth_rate=3.0)

    sim.generate_mesh()
    mesh = {"nodes": int(sim.mesh.n_nodes), "tetrahedra": int(sim.mesh.n_tets)}
    data, sweep = _run_frequency_sweep(sim, case)
    case = {**case, "_sweep_setup": sweep}

    grid = data.scalar.grid
    frequencies = np.asarray(data.scalar.axis("freq"), dtype=float).reshape(-1)
    s_params = {
        "1,1": np.asarray(grid.S(1, 1)).reshape(-1).tolist(),
        "2,1": np.asarray(grid.S(2, 1)).reshape(-1).tolist(),
        "1,2": np.asarray(grid.S(1, 2)).reshape(-1).tolist(),
        "2,2": np.asarray(grid.S(2, 2)).reshape(-1).tolist(),
    }
    return build_planar_raw(case, em.__version__, frequencies.tolist(), s_params, mesh,
                            time.monotonic() - started)


def solve(case):
    """Dispatch to the fixture, design or planar solver."""
    if case.get("kind") == "design":
        return solve_design(case)
    if case.get("kind") == "planar":
        return solve_planar(case)
    return solve_fixture(case)


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
