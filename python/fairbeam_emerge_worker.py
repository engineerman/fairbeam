"""EMerge worker for the WR-90 fixture, admitted Designs, and planar N-port cases.

Runs INSIDE the external EMerge environment (``fairbeam_emerge.py`` starts it as a separate
process with that environment's interpreter). This is the only Fairbeam file that imports EMerge;
it imports nothing from ``fairbeam``. Usage: ``python fairbeam_emerge_worker.py case.json``.

It builds exactly the case described by ``case.json``, solves it in this process, and writes
``raw.json`` next to the case. Threading uses EMerge 3 ``run_sweep(nthreads=…)`` from
``case["nthreads"]`` (one frequency at a time). Concurrent ``run_sweep_distributed`` factorizations
are not used: on large planar meshes they duplicate SuperLU memory and have aborted under Windows
(job ``20261104-204027-177887``). The adapter checks the raw S-parameters; nothing here adjusts a
result.
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
# Matches fairbeam.emerge_limits.N_MAX (worker must not import fairbeam).
N_MAX = 8
THREAD_VARIABLES = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMBA_NUM_THREADS",
                    "VECLIB_NUM_THREADS", "NUMEXPR_NUM_THREADS")
# AbsorbingBoundary: constructor default is order=2 / abctype="B"
# (physics/microwave/bcs/boundary_conditions.py:138-160). The docstring claims only first order is
# supported, but assembler.py:668-675 / 1025-1030 / 1268-1273 applies the second-order correction
# when bc.order == 2. Level B therefore runs the default second-order ABC.
ABC_ORDER = 2
ABC_TYPE = "B"
# Stage A port-map provenance (duplicated; worker must not import fairbeam).
PORT_MAP_KEYS = ("design_port_type", "mapped_bc", "approximations", "accept_used")
APPROX_FIXTURE_WG = "fixture RectangularWaveguide TE10"
FIXTURE_PORT_MAP_ENTRY = {
    "design_port_type": "waveguide",
    "mapped_bc": "RectangularWaveguide",
    "approximations": [APPROX_FIXTURE_WG],
    "accept_used": [],
}


def _port_map_entry(source):
    if not isinstance(source, dict) or not all(key in source for key in PORT_MAP_KEYS):
        return None
    return {
        "design_port_type": source["design_port_type"],
        "mapped_bc": source["mapped_bc"],
        "approximations": list(source["approximations"]),
        "accept_used": list(source["accept_used"]),
    }


def _attach_port_map(raw, entries):
    port_map = [entry for entry in entries if entry is not None]
    if port_map:
        raw["port_map"] = port_map
    return raw


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


def _optional_conductor(entry, label):
    """Validate optional ThinConductor fields; return ``(sigma, thickness_m)`` or ``(None, None)``."""
    has_sigma = "conductivity" in entry
    has_thick = "thickness_m" in entry
    if has_sigma != has_thick:
        raise ValueError(f"{label} must supply conductivity and thickness_m together")
    if not has_sigma:
        return None, None
    sigma, thickness = entry["conductivity"], entry["thickness_m"]
    if not _number(sigma) or sigma <= 0:
        raise ValueError(f"{label}.conductivity must be a positive finite number")
    if not _number(thickness) or thickness <= 0:
        raise ValueError(f"{label}.thickness_m must be a positive finite number")
    return float(sigma), float(thickness)


def _apply_metal_bc(sim, em, geo, sigma, thickness_m):
    """PEC when σ is absent; otherwise EMerge ThinConductor with bulk conductivity and thickness."""
    if sigma is None:
        sim.mw.bc.PEC(geo)
        return
    material = em.Material(cond=sigma)
    sim.mw.bc.ThinConductor(geo, material=material, thickness=thickness_m)


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
        _optional_conductor(sheet, f"sheets[{i}]")
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
    if "metal_edge_m" in case and case["metal_edge_m"] is not None:
        if not _number(case["metal_edge_m"]) or case["metal_edge_m"] <= 0:
            raise ValueError("metal_edge_m must be a positive finite number when set")
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
        _optional_conductor(trace, f"traces[{i}]")
    terminals = case.get("terminals")
    if not isinstance(terminals, list) or not (1 <= len(terminals) <= N_MAX):
        raise ValueError(f"terminals must be a list of 1 to {N_MAX} ports")
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
        number = port.get("number")
        if type(number) is not int or number < 1 or number > len(terminals):
            raise ValueError(f"terminals[{i}].number must be an integer 1…{len(terminals)}")
        numbers.append(number)
    if set(numbers) != set(range(1, len(terminals) + 1)):
        raise ValueError(f"terminals must be contiguous port numbers 1…{len(terminals)}")
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


MESH_SURFACE_SCHEMA = "fairbeam.emerge-mesh-surface/1"
# Cap exterior edges exported for the designer overlay (payload / WebGL).
MESH_SURFACE_MAX_EDGES = 40000


def pack_surface_edges(nodes_m, edge_pairs, *, max_edges=MESH_SURFACE_MAX_EDGES):
    """Pack exterior edge wireframe for Fairbeam (metres in → millimetres out).

    ``nodes_m`` is shape (3, n) in metres. ``edge_pairs`` is shape (2, m) of node indices.
    Pure NumPy; used by the worker and by unit tests without importing EMerge.
    """
    import numpy as np

    nodes = np.asarray(nodes_m, dtype=float)
    edges = np.asarray(edge_pairs, dtype=np.int64)
    if nodes.ndim != 2 or nodes.shape[0] != 3:
        raise ValueError("nodes_m must have shape (3, n)")
    if edges.ndim != 2 or edges.shape[0] != 2:
        raise ValueError("edge_pairs must have shape (2, m)")
    if edges.size == 0:
        return {"schema": MESH_SURFACE_SCHEMA, "units": "mm", "nodes_mm": [], "edges": [],
                "thinned": False, "edge_stride": 1, "edge_count": 0}
    if not np.isfinite(nodes).all():
        raise ValueError("nodes_m must be finite")
    if edges.min(initial=0) < 0 or edges.max(initial=0) >= nodes.shape[1]:
        raise ValueError("edge_pairs index out of range for nodes_m")

    stride = 1
    thinned = False
    count = int(edges.shape[1])
    if count > max_edges:
        stride = int(math.ceil(count / max_edges))
        edges = edges[:, ::stride]
        thinned = True
        count = int(edges.shape[1])

    used = np.unique(edges.reshape(-1))
    remap = {int(old): i for i, old in enumerate(used.tolist())}
    nodes_mm = (nodes[:, used] * 1000.0).T
    packed_edges = [[remap[int(a)], remap[int(b)]] for a, b in edges.T.tolist()]
    return {
        "schema": MESH_SURFACE_SCHEMA,
        "units": "mm",
        "nodes_mm": [[float(x), float(y), float(z)] for x, y, z in nodes_mm.tolist()],
        "edges": packed_edges,
        "thinned": thinned,
        "edge_stride": stride,
        "edge_count": count,
    }


def export_mesh_surface(sim_mesh, *, max_edges=MESH_SURFACE_MAX_EDGES):
    """Exterior surface edges from an EMerge 3.x ``Mesh3D`` (``sim.mesh`` after generate_mesh)."""
    import numpy as np

    tags = list(getattr(sim_mesh, "exterior_face_tags", None) or [])
    if not tags:
        tags = list(getattr(sim_mesh, "ftag_to_edge", {}) or {})
    if tags:
        edge_ids = np.asarray(sim_mesh.get_edges(tags), dtype=np.int64).reshape(-1)
        if edge_ids.size == 0:
            edge_pairs = np.zeros((2, 0), dtype=np.int64)
        else:
            edge_pairs = np.asarray(sim_mesh.edges[:, edge_ids], dtype=np.int64)
    else:
        edge_pairs = np.asarray(sim_mesh.edges, dtype=np.int64)
    return pack_surface_edges(sim_mesh.nodes, edge_pairs, max_edges=max_edges)


def mesh_counts(sim, *, include_surface=True):
    """Node/tet counts plus optional exterior surface wireframe for the designer overlay."""
    mesh = {"nodes": int(sim.mesh.n_nodes), "tetrahedra": int(sim.mesh.n_tets)}
    if include_surface:
        mesh["surface"] = export_mesh_surface(sim.mesh)
    return mesh


def _mesh_raw_block(mesh):
    """``raw.json`` mesh object: counts required; surface optional."""
    if (not isinstance(mesh, dict)
            or any(isinstance(mesh.get(k), bool) or type(mesh.get(k)) is not int or mesh[k] < 0
                   for k in ("nodes", "tetrahedra"))):
        raise ValueError("mesh must hold non-negative integer nodes and tetrahedra")
    block = {"nodes": int(mesh["nodes"]), "tetrahedra": int(mesh["tetrahedra"])}
    surface = mesh.get("surface")
    if surface is not None:
        if not isinstance(surface, dict) or surface.get("schema") != MESH_SURFACE_SCHEMA:
            raise ValueError("mesh.surface must use fairbeam.emerge-mesh-surface/1")
        block["surface"] = surface
    return block


def build_mesh_raw(case, emerge_version, mesh, elapsed_seconds):
    """Assemble mesh-only ``raw.json`` (no frequency sweep / S-parameters)."""
    kind = case.get("kind", "fixture")
    if kind not in ("fixture", "design", "planar"):
        raise ValueError("mesh-only case kind must be fixture, design or planar")
    return {"mesh_only": True, "kind": kind, "emerge_version": str(emerge_version),
            "elapsed_seconds": float(elapsed_seconds),
            "mesh": _mesh_raw_block(mesh),
            "solver_setup": {"mesh_only": True, "nthreads": _nthreads(case),
                             "resolution": case.get("resolution")}}


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
        raw["mesh"] = _mesh_raw_block(mesh)
    if isinstance(case.get("port_map"), list) and case["port_map"]:
        raw["port_map"] = list(case["port_map"])
    else:
        raw["port_map"] = [dict(FIXTURE_PORT_MAP_ENTRY), dict(FIXTURE_PORT_MAP_ENTRY)]
    return raw


FIELD_CUT_SCHEMA = "fairbeam.emerge-field-cut/1"
# Cap samples along the longer in-plane edge (Fairbeam field_planes MAX_SAMPLES is 200).
FIELD_CUT_MAX_EDGE = 100


def _pick_efield_cut_freq(frequencies, *, s11=None, s21=None):
    """Choose one sweep frequency for the post-solve E cut (documented in ``freq_choice``)."""
    freqs = [float(f) for f in frequencies]
    if not freqs:
        raise ValueError("frequencies required for E-field cut")
    if s21 is not None:
        series = [complex(v) for v in s21]
        index = max(range(len(series)), key=lambda i: abs(series[i]))
        return freqs[index], "max_abs_s21"
    if s11 is not None:
        series = [complex(v) for v in s11]
        index = min(range(len(series)), key=lambda i: abs(series[i]))
        return freqs[index], "min_abs_s11"
    return freqs[len(freqs) // 2], "band_center"


def _field_cut_s_kwargs(s_params, n_ports):
    """S-series kwargs for ``try_export_efield_cut``.

    Prefer ``S(2,1)`` when ``n_ports >= 2`` (max-|S21| pick); otherwise ``S(1,1)`` (min-|S11|).
    Heuristic for a representative cut frequency only — not a physics claim.
    """
    if n_ports >= 2:
        return {"s21": s_params["2,1"]}
    return {"s11": s_params["1,1"]}


def _extract_s_matrix(grid, n_ports):
    """Build ``{"i,j": complex sequence}`` for ``i,j in 1…n`` from ``grid.S(i, j)``."""
    import numpy as np
    s_params = {}
    for i in range(1, n_ports + 1):
        for j in range(1, n_ports + 1):
            s_params[f"{i},{j}"] = np.asarray(grid.S(i, j)).reshape(-1).tolist()
    return s_params


def _efield_cut_z_m(case):
    """Board-parallel cut height (metres): substrate mid for planar, else first box / air mid-z."""
    if case.get("kind") == "planar":
        lo, hi = case["substrate"]["lo"], case["substrate"]["hi"]
        return 0.5 * (float(lo[2]) + float(hi[2]))
    boxes = case.get("boxes") or []
    if boxes:
        lo, hi = boxes[0]["lo"], boxes[0]["hi"]
        return 0.5 * (float(lo[2]) + float(hi[2]))
    lo, hi = case["air"]["lo"], case["air"]["hi"]
    return 0.5 * (float(lo[2]) + float(hi[2]))


def _grid_lists(arr):
    """Finite (nv, nu) float grid as nested lists (NaN/Inf → 0)."""
    import numpy as np
    a = np.asarray(arr, dtype=float)
    if a.ndim != 2:
        raise ValueError(f"field cut grid must be 2-D, got shape {a.shape}")
    a = np.where(np.isfinite(a), a, 0.0)
    return [[float(v) for v in row] for row in a]


def export_efield_cut(data, *, z_m, freq_hz, freq_choice, max_edge_samples=FIELD_CUT_MAX_EDGE):
    """Sample a complex E cutplane at ``freq_hz`` (port-1 excitation). Returns a JSON-safe dict.

    Uses EMerge ``MWField.cutplane`` + complex Ex/Ey/Ez. Outside-mesh samples are zeroed
    (``usenan=False``). Units are SI (metres, V/m); the Fairbeam bundle converts to drawing units.
    """
    import numpy as np

    field = data.field.find(freq=float(freq_hz))
    field.set_field_vector()  # port 1 driven (howto / MWField default)
    xb, yb, _zb = field.basis.bounds
    span = max(float(xb[1] - xb[0]), float(yb[1] - yb[0]))
    if not math.isfinite(span) or span <= 0:
        raise ValueError("mesh bounds are empty; cannot build E-field cut")
    n = max(2, min(int(max_edge_samples), 200))
    ds = span / (n - 1)
    cut = field.cutplane(ds=ds, z=float(z_m), usenan=False)
    ex = np.asarray(cut.Ex, dtype=complex)
    ey = np.asarray(cut.Ey, dtype=complex)
    ez = np.asarray(cut.Ez, dtype=complex)
    x = np.asarray(cut.x, dtype=float)
    y = np.asarray(cut.y, dtype=float)
    if ex.ndim != 2 or ey.shape != ex.shape or ez.shape != ex.shape:
        raise ValueError(f"cutplane E shape mismatch: {ex.shape}, {ey.shape}, {ez.shape}")
    # meshgrid default indexing='xy' → shape (len(ys), len(xs)) = (nv, nu) for normal=z
    nv, nu = ex.shape
    u0, u1 = float(np.min(x)), float(np.max(x))
    v0, v1 = float(np.min(y)), float(np.max(y))
    return {
        "schema": FIELD_CUT_SCHEMA,
        "quantity": "E",
        "component": "abs",
        "normal": "z",
        "axis": 2,
        "position_m": float(z_m),
        "freq_hz": float(freq_hz),
        "freq_choice": str(freq_choice),
        "port": 1,
        "u_m": [u0, u1],
        "v_m": [v0, v1],
        "nu": int(nu),
        "nv": int(nv),
        "ex_re": _grid_lists(ex.real), "ex_im": _grid_lists(ex.imag),
        "ey_re": _grid_lists(ey.real), "ey_im": _grid_lists(ey.imag),
        "ez_re": _grid_lists(ez.real), "ez_im": _grid_lists(ez.imag),
    }


def try_export_efield_cut(data, case, frequencies, *, s11=None, s21=None):
    """Best-effort cut export; on failure returns ``(None, note)`` so S-results still ship."""
    try:
        freq_hz, choice = _pick_efield_cut_freq(frequencies, s11=s11, s21=s21)
        cut = export_efield_cut(data, z_m=_efield_cut_z_m(case), freq_hz=freq_hz, freq_choice=choice)
        return cut, None
    except Exception as exc:  # noqa: BLE001 — experimental path must not fail the solve
        return None, f"E-field cut export skipped: {exc}"


def build_design_raw(case, emerge_version, frequencies, s11, mesh, elapsed_seconds, field_cut=None):
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
        raw["mesh"] = _mesh_raw_block(mesh)
    if field_cut is not None:
        raw["field_cut"] = field_cut
    return _attach_port_map(raw, [_port_map_entry(case.get("port"))])


def build_planar_raw(case, emerge_version, frequencies, s_params, mesh, elapsed_seconds, field_cut=None):
    """Assemble planar ``raw.json`` content. S-parameters are EMerge's, unmodified.

    ``s_params`` maps ``"i,j"`` keys to complex sequences (response at i driven at j) for all
    ``i,j in 1…n`` where ``n`` is the terminal count.
    """
    expected = case["frequencies_hz"]
    frequencies = match_frequencies(expected, frequencies)
    count = len(frequencies)
    terminals = sorted(case["terminals"], key=lambda t: t["number"])
    n = len(terminals)
    if n < 1 or n > N_MAX:
        raise ValueError(f"planar raw needs 1 to {N_MAX} terminals")
    s_out = {}
    for i in range(1, n + 1):
        for j in range(1, n + 1):
            key = f"{i},{j}"
            if key not in s_params:
                raise ValueError(f"missing S-parameter series {key}")
            series = _series(s_params[key], f"S{key}", count)
            s_out[key] = {"re": [v.real for v in series], "im": [v.imag for v in series]}
    raw = {"kind": "planar", "emerge_version": str(emerge_version), "frequency_hz": frequencies,
           "s": s_out, "z_ref": [float(t["z0"]) for t in terminals],
           "enclosure": case["enclosure"],
           "phasor_convention": NATIVE_PHASOR,
           "native_phasor_convention": NATIVE_PHASOR,
           "elapsed_seconds": float(elapsed_seconds),
           "trace_count": len(case["traces"]),
           "solver_setup": {"resolution": case["resolution"],
                            "resolution_name": case.get("resolution_name"),
                            "enclosure": case["enclosure"],
                            **({"metal_edge_m": case["metal_edge_m"]}
                              if case.get("metal_edge_m") is not None else {}),
                            "abc_order": ABC_ORDER, "abc_type": ABC_TYPE,
                            "sparam_cap_single": False, "sparam_cap_column": False,
                            "sparam_enforce_reciprocity": False,
                            **(case.get("_sweep_setup") or {"nthreads": _nthreads(case)})},
           "limitations": list(case["limitations"]),
           "pec_approximations": list(case["pec_approximations"])}
    if mesh:
        raw["mesh"] = _mesh_raw_block(mesh)
    if field_cut is not None:
        raw["field_cut"] = field_cut
    return _attach_port_map(raw, [_port_map_entry(terminal) for terminal in terminals])


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
    """Run the MW frequency sweep sequentially with EMerge 3 ``nthreads``.

    Frequencies are solved one after another (same pattern as the RFSim hairpin script). The
    thread budget still goes to SuperLU/OpenMP inside each solve. Parallel frequency workers are
    avoided because each holds a full factorization and large planar cases OOM under Windows.
    """
    budget = _nthreads(case)
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
    mesh = mesh_counts(sim)
    if case.get("mesh_only"):
        return build_mesh_raw(case, em.__version__, mesh, time.monotonic() - started)
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
    sheets = []
    for sheet in case["sheets"]:
        geo = _plate(em, sheet["lo"], sheet["hi"], sheet["normal_axis"])
        sigma, thickness_m = _optional_conductor(sheet, "sheet")
        if sigma is None:
            geo.set_material(em.lib.PEC)
        else:
            geo.set_material(em.Material(cond=sigma))
        sheets.append((geo, sigma, thickness_m))
    # Prefer the multiport list from admit; fall back to legacy singular ``port``.
    ports = case.get("ports") or [case["port"]]
    if not (1 <= len(ports) <= N_MAX):
        raise ValueError(f"design case needs 1 to {N_MAX} ports")
    port_plates = []
    for port in sorted(ports, key=lambda p: p.get("number", 1)):
        # Admit keeps one transverse axis at zero extent; that axis is the plate normal.
        port_flat = [k for k in range(3) if port["hi"][k] == port["lo"][k]]
        if len(port_flat) != 1:
            raise ValueError(f"port {port.get('number')} plate must be flat on exactly one axis")
        port_plates.append((port, _plate(em, port["lo"], port["hi"], port_flat[0])))

    sim.set_resolution(case["resolution"])
    sim.mw.set_frequency(list(case["frequencies_hz"]))
    sim.commit_geometry()  # fragments volumes and plates together; BCs after this

    for face in ("left", "right", "front", "back", "bottom", "top"):
        sim.mw.bc.AbsorbingBoundary(air.face(face), order=ABC_ORDER, abctype=ABC_TYPE)
    for geo, sigma, thickness_m in sheets:
        _apply_metal_bc(sim, em, geo, sigma, thickness_m)
    axes = (em.XAX, em.YAX, em.ZAX)
    for port, port_plate in port_plates:
        direction = axes[port["direction_axis"]]
        if port["sign"] < 0:
            direction = -direction
        number = int(port.get("number", 1))
        sim.mw.bc.LumpedPort(port_plate, number, width=port["width"], height=port["height"],
                             direction=direction, Z0=port["z0"])

    sim.generate_mesh()
    mesh = mesh_counts(sim)
    if case.get("mesh_only"):
        return build_mesh_raw(case, em.__version__, mesh, time.monotonic() - started)
    data, sweep = _run_frequency_sweep(sim, case)
    case = {**case, "_sweep_setup": sweep}

    grid = data.scalar.grid
    frequencies = np.asarray(data.scalar.axis("freq"), dtype=float).reshape(-1)
    s_params = _extract_s_matrix(grid, len(port_plates))
    # Driven result schema still ships S11 until unified emerge-result/2 (B3 Task 3).
    s11 = s_params["1,1"]
    field_cut, cut_note = try_export_efield_cut(
        data, case, frequencies.tolist(), **_field_cut_s_kwargs(s_params, len(port_plates)))
    if cut_note:
        case = {**case, "limitations": list(case["limitations"]) + [cut_note]}
    return build_design_raw(case, em.__version__, frequencies.tolist(), s11, mesh,
                            time.monotonic() - started, field_cut=field_cut)


def solve_planar(case):
    """Build and solve an admitted planar N-port case with EMerge.

    Physics mirror the Level B2 Task 1 spike (originally measured on EMerge 2.8.9; pin is now 3.0.0b12): substrate ``Box``, zero-thickness
    ``XYPolygon.geo()`` traces with ``ThinConductor`` when σ is present (else PEC), ``PEC`` on the
    substrate bottom, optional second-order ABC on the four sides and top when
    ``enclosure == "open"``, ``1…N_MAX`` ``LumpedPort`` strip-to-ground terminals (+z), and
    optional ``mesher.set_boundary_size`` on each trace when ``metal_edge_m`` is set
    (Fairbeam default 0.4 mm, growth 3).
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
        sigma, thickness_m = _optional_conductor(trace, f"traces[{i}]")
        if sigma is None:
            metal.set_material(em.lib.PEC)
        else:
            metal.set_material(em.Material(cond=sigma))
        metals.append((metal, sigma, thickness_m))
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
    for metal, sigma, thickness_m in metals:
        _apply_metal_bc(sim, em, metal, sigma, thickness_m)
    for port, plate in terminals:
        sim.mw.bc.LumpedPort(plate, port["number"], width=port["width"], height=port["height"],
                             direction=em.ZAX, Z0=port["z0"])
    edge = case.get("metal_edge_m")
    if edge is not None:
        for metal, _sigma, _thick in metals:
            sim.mesher.set_boundary_size(metal, edge, growth_rate=3.0)

    sim.generate_mesh()
    mesh = mesh_counts(sim)
    if case.get("mesh_only"):
        return build_mesh_raw(case, em.__version__, mesh, time.monotonic() - started)
    data, sweep = _run_frequency_sweep(sim, case)
    case = {**case, "_sweep_setup": sweep}

    grid = data.scalar.grid
    frequencies = np.asarray(data.scalar.axis("freq"), dtype=float).reshape(-1)
    n_ports = len(terminals)
    s_params = _extract_s_matrix(grid, n_ports)
    field_cut, cut_note = try_export_efield_cut(
        data, case, frequencies.tolist(), **_field_cut_s_kwargs(s_params, n_ports))
    if cut_note:
        case = {**case, "limitations": list(case["limitations"]) + [cut_note]}
    return build_planar_raw(case, em.__version__, frequencies.tolist(), s_params, mesh,
                            time.monotonic() - started, field_cut=field_cut)


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
