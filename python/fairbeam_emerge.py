"""Opt-in external EMerge research adapter (WR-90 fixture, Designs, planar N-port); stdlib only.

This adapter never imports EMerge. It finds an external EMerge Python environment, writes
``case.json`` and starts ``fairbeam_emerge_worker.py`` in that environment as a separate process.
Only the worker imports EMerge. Fixture raw S-parameters are checked against the analytic
straight-waveguide reference; Design and planar raw S-parameters are checked against their
exported-result schemas only (``results_exported``, never validated).
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
SUPPORTED_EMERGE = ("3.0.0b12",)
PHASOR = "exp(+i omega t)"
NATIVE_PHASORS = ("exp(+i omega t)", "exp(-i omega t)")
# Acceptance criteria owned by the Planner (docs/agent/plans/2026-11-04-emerge-level-a-fixture.md),
# frozen from the recorded EMerge 2.8.9 coarse/fine runs.
CRITERIA = {"s11_max": 0.02, "s21_min": 0.995, "phase_error_deg_max": 2.0, "passivity_max": 1.005}
RESULT_SCHEMA = "fairbeam.emerge-fixture-result/1"
MANIFEST_SCHEMA = "fairbeam-emerge-fixture-1"
DESIGN_MANIFEST_SCHEMA = "fairbeam-emerge-design-1"
PLANAR_MANIFEST_SCHEMA = "fairbeam-emerge-planar-1"
NPORT_RESULT_SCHEMA = "fairbeam.emerge-result/2"
GEOMETRY_KINDS = ("driven_lumped", "planar_microstrip")
GEOMETRY_DRIVEN = "driven_lumped"
GEOMETRY_PLANAR = "planar_microstrip"
MESH_RESULT_SCHEMA = "fairbeam.emerge-mesh-result/1"
MESH_SURFACE_SCHEMA = "fairbeam.emerge-mesh-surface/1"
MESH_SURFACE_MAX_NODES = 100_000
MESH_SURFACE_MAX_EDGES = 200_000
S11_ABS_MAX = 1.01  # same bound as Elmer driven
S_ABS_MAX = 1.01  # planar |S_ij| bound
PLANAR_COLUMN_POWER_MAX = 1.02
PLANAR_RECIPROCITY_MAX = 0.02
WORKER = Path(__file__).resolve().with_name("fairbeam_emerge_worker.py")
WORKER_TIMEOUT_S = 600
DESIGN_WORKER_TIMEOUT_S = 1800  # Design sweep timeout (frozen Task 5; Level A waveguide stays 600 s)
PLANAR_WORKER_TIMEOUT_S = 3600  # planar N-port timeout (frozen Task 1; B3 widened count)
# Soft admit limit; keep in sync with fairbeam.emerge_limits.N_MAX (avoid importing fairbeam here).
PLANAR_N_MAX = 8
MESH_WORKER_TIMEOUT_S = 900  # mesh-only generate (no frequency sweep)
LIMITATIONS = [
    "Fixed WR-90 straight air-filled waveguide fixture only; no user design is translated.",
    "Reference planes are the port faces; ideal PEC walls, lossless fill, single-mode band.",
    "No mesh convergence study; precision_converged is always false.",
    "Not qualified for driven antenna results.",
]
# Stage A port-map provenance keys (must match fairbeam.emerge_port_map Shared facts).
PORT_MAP_KEYS = ("design_port_type", "mapped_bc", "approximations", "accept_used")
# Frozen fixture strings — duplicated here because this adapter is stdlib-only.
APPROX_FIXTURE_WG = "fixture RectangularWaveguide TE10"
FIXTURE_PORT_MAP_ENTRY = {
    "design_port_type": "waveguide",
    "mapped_bc": "RectangularWaveguide",
    "approximations": [APPROX_FIXTURE_WG],
    "accept_used": [],
}


def _port_map_entry(source):
    """Copy Stage A provenance fields from a case port/terminal dict, or None if incomplete."""
    if not isinstance(source, dict) or not all(key in source for key in PORT_MAP_KEYS):
        return None
    return {
        "design_port_type": source["design_port_type"],
        "mapped_bc": source["mapped_bc"],
        "approximations": list(source["approximations"]),
        "accept_used": list(source["accept_used"]),
    }


def port_map_from_design_case(case):
    entry = _port_map_entry((case or {}).get("port"))
    return [entry] if entry else []


def port_map_from_planar_case(case):
    out = []
    for terminal in sorted((case or {}).get("terminals") or [], key=lambda item: item.get("number", 0)):
        entry = _port_map_entry(terminal)
        if entry is not None:
            out.append(entry)
    return out


def fixture_port_map():
    """Two WR-90 face ports mapped as RectangularWaveguide (fixture path only)."""
    return [dict(FIXTURE_PORT_MAP_ENTRY), dict(FIXTURE_PORT_MAP_ENTRY)]


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


def default_nthreads():
    """Host thread budget when the caller does not pass one (mirrors ``resources.auto_threads``)."""
    logical = max(1, int(os.cpu_count() or 1))
    physical = logical  # adapter stays stdlib-only; research injects a better value via resources
    if physical >= 4:
        n = physical - 1
    elif physical <= 2:
        n = 1
    else:
        n = physical
    return max(1, min(n, 4, logical))


def with_nthreads(case, threads=None):
    """Copy ``case`` and set a positive ``nthreads`` field (1..64)."""
    if not isinstance(case, dict):
        raise ValueError("case must be an object")
    if threads is None:
        threads = case.get("nthreads", default_nthreads())
    if type(threads) is not int or threads < 1:
        raise ValueError("nthreads must be a positive integer")
    return {**case, "nthreads": min(threads, 64)}


def case(resolution, *, threads=None):
    """The JSON document handed to the worker: the fixed fixture and nothing else."""
    validate_case(resolution)
    return with_nthreads({
        "schema": "fairbeam-emerge-fixture-case/1", "physics": "wr90_waveguide_fixture",
        "geometry": {"a_m": A_M, "b_m": B_M, "length_m": L_M, "walls": "PEC",
                     "fill": {"eps_r": 1.0, "mu_r": 1.0}},
        "frequency_hz": list(FREQUENCIES_HZ),
        "ports": [
            {"name": "port1", "face_z_m": 0.0, "mode": "TE10", **dict(FIXTURE_PORT_MAP_ENTRY)},
            {"name": "port2", "face_z_m": L_M, "mode": "TE10", **dict(FIXTURE_PORT_MAP_ENTRY)},
        ],
        "port_map": fixture_port_map(),
        "resolution": {"name": resolution, "value": RESOLUTIONS[resolution]},
        "phasor_convention_out": PHASOR,
    }, threads)


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
        context["mesh"] = _mesh_ok(raw["mesh"])
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
            "limitations": list(LIMITATIONS),
            "port_map": (list(raw["port_map"]) if isinstance(raw.get("port_map"), list) and raw["port_map"]
                         else fixture_port_map())}


def _text(value):
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return value or ""


def _surface_ok(surface):
    """Validate optional exterior-edge wireframe for the FEM mesh overlay."""
    if not isinstance(surface, dict) or surface.get("schema") != MESH_SURFACE_SCHEMA:
        raise ValueError("mesh.surface must use fairbeam.emerge-mesh-surface/1")
    if surface.get("units") != "mm":
        raise ValueError("mesh.surface.units must be mm")
    nodes = surface.get("nodes_mm")
    edges = surface.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise ValueError("mesh.surface needs nodes_mm and edges lists")
    if len(nodes) > MESH_SURFACE_MAX_NODES or len(edges) > MESH_SURFACE_MAX_EDGES:
        raise ValueError("mesh.surface exceeds Fairbeam overlay limits")
    for point in nodes:
        if (not isinstance(point, list) or len(point) != 3
                or any(isinstance(v, bool) or not _number(v) for v in point)):
            raise ValueError("mesh.surface.nodes_mm entries must be [x, y, z] finite numbers")
    n = len(nodes)
    packed_edges = []
    for edge in edges:
        if (not isinstance(edge, list) or len(edge) != 2
                or any(isinstance(v, bool) or type(v) is not int or v < 0 or v >= n for v in edge)):
            raise ValueError("mesh.surface.edges entries must be in-range integer pairs")
        packed_edges.append([int(edge[0]), int(edge[1])])
    thinned = surface.get("thinned", False)
    if type(thinned) is not bool:
        raise ValueError("mesh.surface.thinned must be boolean when present")
    stride = surface.get("edge_stride", 1)
    if type(stride) is not int or stride < 1:
        raise ValueError("mesh.surface.edge_stride must be a positive integer")
    edge_count = surface.get("edge_count", len(packed_edges))
    if type(edge_count) is not int or edge_count < 0:
        raise ValueError("mesh.surface.edge_count must be a non-negative integer")
    return {"schema": MESH_SURFACE_SCHEMA, "units": "mm",
            "nodes_mm": [[float(p[0]), float(p[1]), float(p[2])] for p in nodes],
            "edges": packed_edges, "thinned": thinned, "edge_stride": stride,
            "edge_count": int(edge_count)}


def _mesh_ok(mesh):
    """Counts required; optional validated surface wireframe for Mesh view."""
    if (not isinstance(mesh, dict) or not {"nodes", "tetrahedra"} <= set(mesh)
            or not set(mesh) <= {"nodes", "tetrahedra", "surface"}
            or any(isinstance(mesh[k], bool) or type(mesh[k]) is not int or mesh[k] < 0
                   for k in ("nodes", "tetrahedra"))):
        raise ValueError("mesh must hold non-negative integer nodes and tetrahedra")
    block = {"nodes": int(mesh["nodes"]), "tetrahedra": int(mesh["tetrahedra"])}
    if "surface" in mesh:
        block["surface"] = _surface_ok(mesh["surface"])
    return block


def assess_mesh(raw, case):
    """Check mesh-only raw output; status is always ``mesh_exported`` when counts are finite."""
    if not isinstance(case, dict) or case.get("kind") not in ("design", "planar", "fixture"):
        raise ValueError("mesh-only case must be design, planar or fixture")
    if not isinstance(raw, dict) or raw.get("mesh_only") is not True:
        raise ValueError("mesh-only raw must set mesh_only true")
    if raw.get("kind") is not None and raw.get("kind") != case.get("kind"):
        raise ValueError("mesh-only raw kind must match the case")
    mesh = _mesh_ok(raw.get("mesh"))
    elapsed = raw.get("elapsed_seconds", 0.0)
    if not _number(elapsed) or elapsed < 0:
        raise ValueError("elapsed_seconds must be a finite non-negative number")
    context = {}
    if "emerge_version" in raw:
        if not isinstance(raw["emerge_version"], str):
            raise ValueError("emerge_version must be a string")
        context["emerge_version"] = raw["emerge_version"]
    settings = {"resolution": case.get("resolution"), "mesh_only": True}
    if "resolution_name" in case:
        settings["resolution_name"] = case["resolution_name"]
    if "enclosure" in case:
        settings["enclosure"] = case["enclosure"]
    limitations = ["Mesh generation only; no frequency sweep or S-parameters.",
                   "Node and tetrahedron counts are experimental."]
    if "surface" in mesh:
        limitations.append("Exterior surface edges are for experimental Mesh view overlay only.")
    else:
        limitations.append("No surface wireframe was exported for Mesh view.")
    return {"schema": MESH_RESULT_SCHEMA, "status": "mesh_exported",
            "kind": case.get("kind", "fixture"),
            "frequency_hz": [],  # no sweep; empty axis keeps research UI contracts honest
            "nodes": mesh["nodes"], "tetrahedra": mesh["tetrahedra"],
            "duration_s": float(elapsed),
            "mesh": mesh,
            "settings": settings, "precision_converged": False, "gain_qualified": False,
            "limitations": limitations,
            **context}


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


FIELD_CUT_SCHEMA = "fairbeam.emerge-field-cut/1"


def _field_cut_ok(cut):
    """Stdlib structural check of a worker E-field cut (full grid validation is in emerge_field_cut)."""
    if not isinstance(cut, dict):
        raise ValueError("field_cut must be an object")
    if cut.get("schema") != FIELD_CUT_SCHEMA:
        raise ValueError(f"field_cut.schema must be {FIELD_CUT_SCHEMA}")
    if cut.get("quantity") != "E" or cut.get("component") != "abs" or cut.get("normal") != "z":
        raise ValueError("field_cut must be an absolute E map with normal z")
    if cut.get("axis") != 2:
        raise ValueError("field_cut.axis must be 2")
    for key in ("position_m", "freq_hz"):
        if not _number(cut.get(key)):
            raise ValueError(f"field_cut.{key} must be a finite number")
    if cut["freq_hz"] <= 0:
        raise ValueError("field_cut.freq_hz must be positive")
    nu, nv = cut.get("nu"), cut.get("nv")
    if type(nu) is not int or type(nv) is not int or nu < 2 or nv < 2:
        raise ValueError("field_cut.nu and nv must be integers >= 2")
    for key in ("u_m", "v_m"):
        span = cut.get(key)
        if (not isinstance(span, list) or len(span) != 2
                or not all(map(_number, span)) or span[1] <= span[0]):
            raise ValueError(f"field_cut.{key} must be [lo, hi] with hi > lo")
    if cut.get("freq_choice") not in ("max_abs_s21", "min_abs_s11", "band_center"):
        raise ValueError("field_cut.freq_choice is unknown")
    port = cut.get("port", 1)
    if type(port) is not int or port < 1:
        raise ValueError("field_cut.port must be a positive integer")

    def rows(name):
        re_vals, im_vals = cut.get(f"{name}_re"), cut.get(f"{name}_im")
        if (not isinstance(re_vals, list) or not isinstance(im_vals, list)
                or len(re_vals) != nv or len(im_vals) != nv):
            raise ValueError(f"field_cut.{name}_* must be {nv} rows")
        for j, (re_row, im_row) in enumerate(zip(re_vals, im_vals)):
            if (not isinstance(re_row, list) or not isinstance(im_row, list)
                    or len(re_row) != nu or len(im_row) != nu
                    or not all(map(_number, re_row)) or not all(map(_number, im_row))):
                raise ValueError(f"field_cut.{name}[{j}] must hold {nu} finite re/im samples")
        return re_vals, im_vals

    ex_re, ex_im = rows("ex")
    ey_re, ey_im = rows("ey")
    ez_re, ez_im = rows("ez")
    return {
        "schema": FIELD_CUT_SCHEMA,
        "quantity": "E", "component": "abs", "normal": "z", "axis": 2,
        "position_m": float(cut["position_m"]), "freq_hz": float(cut["freq_hz"]),
        "freq_choice": cut["freq_choice"], "port": port,
        "u_m": [float(cut["u_m"][0]), float(cut["u_m"][1])],
        "v_m": [float(cut["v_m"][0]), float(cut["v_m"][1])],
        "nu": nu, "nv": nv,
        "ex_re": ex_re, "ex_im": ex_im,
        "ey_re": ey_re, "ey_im": ey_im,
        "ez_re": ez_re, "ez_im": ez_im,
    }


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
    context = {"z_ref": [float(z_ref)]}
    if "emerge_version" in raw:
        if not isinstance(raw["emerge_version"], str):
            raise ValueError("emerge_version must be a string")
        context["emerge_version"] = raw["emerge_version"]
    if "elapsed_seconds" in raw:
        if not _number(raw["elapsed_seconds"]) or raw["elapsed_seconds"] < 0:
            raise ValueError("elapsed_seconds must be a finite non-negative number")
        context["elapsed_seconds"] = float(raw["elapsed_seconds"])
    if "mesh" in raw:
        context["mesh"] = _mesh_ok(raw["mesh"])
    if "field_cut" in raw:
        context["field_cut"] = _field_cut_ok(raw["field_cut"])
    settings = {"resolution": case["resolution"], "frequencies_hz": expected}
    if "resolution_name" in case:
        settings["resolution_name"] = case["resolution_name"]
    limitations = list(case["limitations"])
    if isinstance(raw.get("limitations"), list):
        limitations = list(raw["limitations"])
    pec = list(case["pec_approximations"])
    if isinstance(raw.get("pec_approximations"), list):
        pec = list(raw["pec_approximations"])
    port_map = port_map_from_design_case(case)
    if isinstance(raw.get("port_map"), list) and raw["port_map"]:
        port_map = list(raw["port_map"])
    # Worker raw still ships S11; assessed Design results are always emerge-result/2.
    result = {"schema": NPORT_RESULT_SCHEMA, "geometry_kind": GEOMETRY_DRIVEN,
            "status": "results_exported",
            "frequency_hz": expected,
            "s": {"1,1": {"re": [v.real for v in s11], "im": [v.imag for v in s11]}},
            "settings": settings, "phasor_convention": PHASOR,
            "native_phasor_convention": native, **context,
            "precision_converged": False, "gain_qualified": False,
            "limitations": limitations, "pec_approximations": pec}
    if port_map:
        result["port_map"] = port_map
    return result


def planar_case_ok(case):
    """Structural check of an admitted planar case; raises ``ValueError`` if unusable."""
    if not isinstance(case, dict) or case.get("kind") != "planar":
        raise ValueError("Planar case must have kind 'planar'")
    if case.get("phasor_convention_out") != PHASOR:
        raise ValueError("phasor_convention_out must be exp(+i omega t)")
    if case.get("enclosure") not in ("shielded", "open"):
        raise ValueError("enclosure must be shielded or open")
    if not _number(case.get("resolution")) or not 0 < case["resolution"] <= 0.5:
        raise ValueError("resolution must be a wavelength fraction in (0, 0.5]")
    if "metal_edge_m" in case and case["metal_edge_m"] is not None:
        if not _number(case["metal_edge_m"]) or case["metal_edge_m"] <= 0:
            raise ValueError("metal_edge_m must be a positive finite number when set")
    frequencies = case.get("frequencies_hz")
    if (not isinstance(frequencies, list) or len(frequencies) < 3
            or not all(map(_number, frequencies)) or any(f <= 0 for f in frequencies)):
        raise ValueError("frequencies_hz must be at least three positive finite numbers")
    if list(frequencies) != sorted(frequencies):
        raise ValueError("frequencies_hz must be ascending")
    substrate, traces, terminals, air = (case.get("substrate"), case.get("traces"),
                                         case.get("terminals"), case.get("air"))
    if not isinstance(substrate, dict) or not isinstance(air, dict):
        raise ValueError("Planar case needs substrate and air objects")
    if not isinstance(traces, list) or not traces:
        raise ValueError("Planar case needs a non-empty traces list")
    if not isinstance(terminals, list) or not (1 <= len(terminals) <= PLANAR_N_MAX):
        raise ValueError(f"Planar case needs 1 to {PLANAR_N_MAX} terminals")
    numbers = []
    for port in terminals:
        if not isinstance(port, dict) or type(port.get("number")) is not int:
            raise ValueError("Each terminal needs an integer number")
        if not _number(port.get("z0")) or port["z0"] <= 0:
            raise ValueError("terminal z0 must be a positive finite number")
        for key in ("width", "height"):
            if not _number(port.get(key)) or port[key] <= 0:
                raise ValueError(f"terminal.{key} must be a positive finite number")
        numbers.append(port["number"])
    n = len(terminals)
    if set(numbers) != set(range(1, n + 1)):
        raise ValueError(f"terminals must be contiguous port numbers 1…{n}")
    if not isinstance(case.get("limitations"), list) or not isinstance(case.get("pec_approximations"), list):
        raise ValueError("limitations and pec_approximations must be lists")
    return True


def assess_planar(raw, case):
    """Check planar raw N×N S against Shared facts; always ``results_exported`` if ok."""
    planar_case_ok(case)
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
    terminals = sorted(case["terminals"], key=lambda t: t["number"])
    n = len(terminals)
    s_block = raw.get("s")
    if not isinstance(s_block, dict):
        raise ValueError("Raw s must be an object")
    s = {}
    for i in range(1, n + 1):
        for j in range(1, n + 1):
            key = f"{i},{j}"
            entry = s_block.get(key)
            if not isinstance(entry, dict):
                raise ValueError(f"s[{key}] must be an object with re and im")
            re_vals, im_vals = entry.get("re"), entry.get("im")
            if (not isinstance(re_vals, list) or not isinstance(im_vals, list)
                    or len(re_vals) != count or len(im_vals) != count
                    or not all(map(_number, re_vals)) or not all(map(_number, im_vals))):
                raise ValueError(f"s[{key}] must hold {count} finite re/im samples")
            s[key] = [complex(float(r), float(i_)) for r, i_ in zip(re_vals, im_vals)]
    for key, series in s.items():
        if any(abs(v) > S_ABS_MAX for v in series):
            raise ValueError(f"|S{key}| exceeds {S_ABS_MAX}")
    for j in range(1, n + 1):
        power = []
        for k in range(count):
            power.append(sum(abs(s[f"{i},{j}"][k]) ** 2 for i in range(1, n + 1)))
        if any(p > PLANAR_COLUMN_POWER_MAX for p in power):
            raise ValueError(f"column {j} power exceeds {PLANAR_COLUMN_POWER_MAX}")
    for i in range(1, n + 1):
        for j in range(i + 1, n + 1):
            recip = [abs(a - b) for a, b in zip(s[f"{i},{j}"], s[f"{j},{i}"])]
            if any(d > PLANAR_RECIPROCITY_MAX for d in recip):
                raise ValueError(
                    f"|S{i},{j} − S{j},{i}| exceeds {PLANAR_RECIPROCITY_MAX}")
    z_ref = raw.get("z_ref")
    if z_ref is None:
        z_ref = [t["z0"] for t in terminals]
    if (not isinstance(z_ref, list) or len(z_ref) != n
            or not all(_number(v) and v > 0 for v in z_ref)):
        raise ValueError(f"z_ref must be {n} positive finite numbers")
    enclosure = raw.get("enclosure", case["enclosure"])
    if enclosure not in ("shielded", "open"):
        raise ValueError("enclosure must be shielded or open")
    context = {"z_ref": [float(v) for v in z_ref], "enclosure": enclosure}
    if "emerge_version" in raw:
        if not isinstance(raw["emerge_version"], str):
            raise ValueError("emerge_version must be a string")
        context["emerge_version"] = raw["emerge_version"]
    if "elapsed_seconds" in raw:
        if not _number(raw["elapsed_seconds"]) or raw["elapsed_seconds"] < 0:
            raise ValueError("elapsed_seconds must be a finite non-negative number")
        context["elapsed_seconds"] = float(raw["elapsed_seconds"])
    if "mesh" in raw:
        context["mesh"] = _mesh_ok(raw["mesh"])
    if "field_cut" in raw:
        context["field_cut"] = _field_cut_ok(raw["field_cut"])
    settings = {"resolution": case["resolution"], "frequencies_hz": expected,
                "enclosure": case["enclosure"]}
    if case.get("metal_edge_m") is not None:
        settings["metal_edge_m"] = case["metal_edge_m"]
    if "resolution_name" in case:
        settings["resolution_name"] = case["resolution_name"]
    limitations = list(case["limitations"])
    if isinstance(raw.get("limitations"), list):
        limitations = list(raw["limitations"])
    pec = list(case["pec_approximations"])
    if isinstance(raw.get("pec_approximations"), list):
        pec = list(raw["pec_approximations"])
    port_map = port_map_from_planar_case(case)
    if isinstance(raw.get("port_map"), list) and raw["port_map"]:
        port_map = list(raw["port_map"])
    result = {"schema": NPORT_RESULT_SCHEMA, "geometry_kind": GEOMETRY_PLANAR,
            "status": "results_exported",
            "frequency_hz": expected,
            "s": {key: {"re": [v.real for v in series], "im": [v.imag for v in series]}
                  for key, series in s.items()},
            "settings": settings, "phasor_convention": PHASOR,
            "native_phasor_convention": native, **context,
            "precision_converged": False, "gain_qualified": False,
            "limitations": limitations, "pec_approximations": pec}
    if port_map:
        result["port_map"] = port_map
    return result


def _worker_env(nthreads):
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    text = str(max(1, int(nthreads)))
    env.update(OMP_NUM_THREADS=text, MKL_NUM_THREADS=text, OPENBLAS_NUM_THREADS=text,
               NUMBA_NUM_THREADS=text, VECLIB_NUM_THREADS=text, NUMEXPR_NUM_THREADS=text,
               MPLBACKEND="Agg", PYVISTA_OFF_SCREEN="true")
    return env


def run_fixture(out, *, root=None, resolution="coarse", experimental=False, threads=None):
    if not experimental:
        raise ValueError("Explicit --experimental opt-in is required")
    validate_case(resolution)
    python, site = discover(root)
    if not WORKER.is_file():
        raise FileNotFoundError(f"EMerge worker script not found: {WORKER}")
    directory = Path(out).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=False)
    payload = case(resolution, threads=threads)
    nthreads = payload["nthreads"]
    manifest = {"schema": MANIFEST_SCHEMA, "backend": "emerge-experimental",
                "physics": "wr90_waveguide_fixture", "resolution": resolution,
                "resolution_value": RESOLUTIONS[resolution], "threads": nthreads, "status": "inputs_generated",
                "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "input_provenance": "fixed WR-90 fixture constants; analytic straight-guide reference",
                "phasor_convention": PHASOR, "python": str(python), "python_sha256": digest(python),
                "emerge_version": emerge_version(site), "generator_sha256": digest(__file__)}

    def save():
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    (directory / "case.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n",
                                         encoding="utf-8")
    shutil.copyfile(WORKER, directory / WORKER.name)
    manifest["worker_sha256"] = digest(directory / WORKER.name)
    manifest["case_sha256"] = digest(directory / "case.json")
    save()
    env = _worker_env(nthreads)
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


def run_design(out, case, *, root=None, experimental=False, threads=None):
    """Run an admitted Design case through the EMerge worker (opt-in; fresh ``out`` directory)."""
    if not experimental:
        raise ValueError("Explicit --experimental opt-in is required")
    payload = with_nthreads(case, threads)
    design_case_ok(payload)
    mesh_only = payload.get("mesh_only") is True
    if payload.get("mesh_only") not in (None, False, True):
        raise ValueError("mesh_only must be boolean when present")
    python, site = discover(root)
    if not WORKER.is_file():
        raise FileNotFoundError(f"EMerge worker script not found: {WORKER}")
    directory = Path(out).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=False)
    nthreads = payload["nthreads"]
    timeout_s = MESH_WORKER_TIMEOUT_S if mesh_only else DESIGN_WORKER_TIMEOUT_S
    manifest = {"schema": DESIGN_MANIFEST_SCHEMA, "backend": "emerge-experimental",
                "physics": "design_driven", "kind": "design", "mesh_only": mesh_only,
                "resolution": payload.get("resolution_name", payload["resolution"]),
                "resolution_value": payload["resolution"], "threads": nthreads, "status": "inputs_generated",
                "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "input_provenance": "admitted Design case from emerge_design.admit",
                "phasor_convention": PHASOR, "python": str(python), "python_sha256": digest(python),
                "emerge_version": emerge_version(site), "generator_sha256": digest(__file__)}

    def save():
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    (directory / "case.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n",
                                         encoding="utf-8")
    shutil.copyfile(WORKER, directory / WORKER.name)
    manifest["worker_sha256"] = digest(directory / WORKER.name)
    manifest["case_sha256"] = digest(directory / "case.json")
    save()
    env = _worker_env(nthreads)
    try:
        manifest["status"] = "solver_started"
        save()
        start = time.monotonic()
        try:
            process = subprocess.run([str(python), "-I", "-X", "utf8", WORKER.name, "case.json"],
                                     cwd=directory, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                     timeout=timeout_s,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except subprocess.TimeoutExpired as exc:
            (directory / "worker.log").write_text(_text(exc.stdout), encoding="utf-8")
            raise RuntimeError(f"worker exceeded {timeout_s} second limit") from exc
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
        result = assess_mesh(raw, payload) if mesh_only else assess_design(raw, case)
        result["raw_sha256"] = {"raw.json": digest(directory / "raw.json")}
        (directory / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                                               encoding="utf-8")
        manifest["status"] = result["status"]
        save()
        expected = "mesh_exported" if mesh_only else "results_exported"
        if result["status"] != expected:
            raise ValueError("Design result was not exported; raw output retained")
        return result
    except BaseException as exc:
        if manifest["status"] not in ("results_exported", "mesh_exported"):
            manifest["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        manifest["error"] = str(exc)
        save()
        raise


def run_planar(out, case, *, root=None, experimental=False, threads=None):
    """Run an admitted planar two-port case through the EMerge worker (opt-in; fresh ``out``)."""
    if not experimental:
        raise ValueError("Explicit --experimental opt-in is required")
    payload = with_nthreads(case, threads)
    planar_case_ok(payload)
    mesh_only = payload.get("mesh_only") is True
    if payload.get("mesh_only") not in (None, False, True):
        raise ValueError("mesh_only must be boolean when present")
    python, site = discover(root)
    if not WORKER.is_file():
        raise FileNotFoundError(f"EMerge worker script not found: {WORKER}")
    directory = Path(out).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=False)
    nthreads = payload["nthreads"]
    timeout_s = MESH_WORKER_TIMEOUT_S if mesh_only else PLANAR_WORKER_TIMEOUT_S
    manifest = {"schema": PLANAR_MANIFEST_SCHEMA, "backend": "emerge-experimental",
                "physics": "planar_two_port", "kind": "planar", "mesh_only": mesh_only,
                "enclosure": payload["enclosure"],
                "resolution": payload.get("resolution_name", payload["resolution"]),
                "resolution_value": payload["resolution"], "threads": nthreads, "status": "inputs_generated",
                "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "input_provenance": "admitted planar case from emerge_planar.admit",
                "phasor_convention": PHASOR, "python": str(python), "python_sha256": digest(python),
                "emerge_version": emerge_version(site), "generator_sha256": digest(__file__)}

    def save():
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    (directory / "case.json").write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n",
                                         encoding="utf-8")
    shutil.copyfile(WORKER, directory / WORKER.name)
    manifest["worker_sha256"] = digest(directory / WORKER.name)
    manifest["case_sha256"] = digest(directory / "case.json")
    save()
    env = _worker_env(nthreads)
    try:
        manifest["status"] = "solver_started"
        save()
        start = time.monotonic()
        try:
            process = subprocess.run([str(python), "-I", "-X", "utf8", WORKER.name, "case.json"],
                                     cwd=directory, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                     timeout=timeout_s,
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except subprocess.TimeoutExpired as exc:
            (directory / "worker.log").write_text(_text(exc.stdout), encoding="utf-8")
            raise RuntimeError(f"worker exceeded {timeout_s} second limit") from exc
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
        result = assess_mesh(raw, payload) if mesh_only else assess_planar(raw, case)
        result["raw_sha256"] = {"raw.json": digest(directory / "raw.json")}
        (directory / "result.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                                               encoding="utf-8")
        manifest["status"] = result["status"]
        save()
        expected = "mesh_exported" if mesh_only else "results_exported"
        if result["status"] != expected:
            raise ValueError("Planar result was not exported; raw output retained")
        return result
    except BaseException as exc:
        if manifest["status"] not in ("results_exported", "mesh_exported"):
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
    planar = commands.add_parser("planar", help="run an admitted planar two-port case through EMerge")
    planar.add_argument("--experimental", action="store_true", help="explicitly opt into research execution")
    planar.add_argument("--case", type=Path, required=True, help="admitted planar case JSON")
    planar.add_argument("--out", type=Path, required=True, help="fresh output directory")
    args = parser.parse_args(argv)
    try:
        if args.command == "capabilities":
            result = capabilities(args.root)
        elif args.command == "waveguide":
            result = run_fixture(args.out, root=args.root, resolution=args.resolution,
                                 experimental=args.experimental)
        elif args.command == "design":
            case = json.loads(Path(args.case).read_text(encoding="utf-8"))
            result = run_design(args.out, case, root=args.root, experimental=args.experimental)
        else:
            case = json.loads(Path(args.case).read_text(encoding="utf-8"))
            result = run_planar(args.out, case, root=args.root, experimental=args.experimental)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(2, f"fairbeam-emerge: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
