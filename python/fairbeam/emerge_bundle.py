"""Export an EMerge driven Design result into the shared designer Results format.

Geometry comes from the admitted design; no openEMS simulation is performed.
EMerge 3.0.0b12 is natively ``exp(+i omega t)``, matching Fairbeam frames, so S is
not conjugated. Far field is empty in Level B / B2. Completion is never a validation claim.
"""
import copy
import math

import numpy as np

def _run_timing(result):
    """Map worker wall time into the Runs-dock fields (``solver_time_s`` / ``wall_time_s``).

    Timing only — no FDTD ``converged`` / ``hit_timestep_limit``. Header and ``run_quality``
    must treat EMerge via experimental-FEM branches (O16), not openEMS energy stop.
    """
    elapsed = result.get("elapsed_seconds")
    if elapsed is None:
        return None
    seconds = float(elapsed)
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError("elapsed_seconds must be a finite non-negative number")
    return {"solver_time_s": seconds, "wall_time_s": seconds}


def _pack_nport_sparams(s_block, z_refs):
    """Build per-port Zin diagonals and a complete N×N ``results.sparams`` section."""
    n = len(z_refs)
    if n < 1:
        raise ValueError("z_ref must hold at least one reference")
    if not isinstance(s_block, dict):
        raise ValueError("s must be an object")
    port_results = {}
    for number in range(1, n + 1):
        key = f"{number},{number}"
        entry = s_block.get(key)
        if not isinstance(entry, dict):
            raise ValueError(f"s[{key}] must be an object")
        reflection = np.asarray(entry["re"], dtype=float) + 1j * np.asarray(entry["im"], dtype=float)
        z0 = float(z_refs[number - 1])
        denominator = 1 - reflection
        if np.any(np.abs(denominator) < 1e-12):
            raise ValueError("Cannot export singular input impedance")
        impedance = z0 * (1 + reflection) / denominator
        # Keep native diagonal S (no conjugation), same as Level B.
        port_results[str(number)] = dict(
            s11_re=reflection.real.tolist(), s11_im=reflection.imag.tolist(),
            zin_re=impedance.real.tolist(), zin_im=impedance.imag.tolist(), z_ref=z0)
    sparams = dict(
        ports=list(range(1, n + 1)), z_ref=[float(v) for v in z_refs],
        excited=list(range(1, n + 1)), complete=True,
        method="FEM driven, all ports",
        s={f"{i},{j}": {"re": list(s_block[f"{i},{j}"]["re"]),
                       "im": list(s_block[f"{i},{j}"]["im"])}
           for i in range(1, n + 1) for j in range(1, n + 1)})
    return port_results, sparams


def _resolved_planar_ports(design):
    """Microstrip and CPW ports as the viewer stores them, with expressions evaluated.

    The openEMS preview build cannot take these ports: ``to_bundle`` runs the FDTD
    planar mesh gates, which must not reject an EMerge result. The saved bundle still
    needs ``number``, ``excite``, and numeric ends so a comparison can address
    ``results.ports`` by that number.
    """
    from .design import DesignError, resolve_names, evaluate

    params = design.get("params") if isinstance(design, dict) else None
    values = {p["key"]: p["default"] for p in params or []
              if isinstance(p, dict) and "expr" not in p and "key" in p and "default" in p}
    try:
        names = resolve_names(design if isinstance(design, dict) else {}, values)
    except (DesignError, TypeError, ValueError, KeyError):
        return []

    def num(value):
        return float(evaluate(value, names))

    out = []
    for po in (design.get("ports") or []) if isinstance(design, dict) else []:
        if not isinstance(po, dict) or po.get("type") not in ("microstrip", "cpw"):
            continue
        try:
            start = [num(v) for v in po["start"]]
            stop = [num(v) for v in po["stop"]]
            ref = num(po.get("reference_ohm", 50))
            feed = num(po.get("feed_shift", 0))
            meas = num(po["measurement_shift"])
            record = {
                "type": po["type"], "number": int(po["number"]),
                "start": start, "stop": stop,
                "direction": po["direction"],
                "excitation_direction": po["excitation_direction"],
                "conductor": po.get("conductor") or "PEC",
                "feed_shift": feed, "measurement_shift": meas,
                "termination": po.get("termination", "open"),
                "reference_ohm": ref, "R": ref,
                "excite": bool(po.get("excite", True)),
            }
            if po["type"] == "cpw":
                record["gap"] = num(po["gap"])
        except (DesignError, TypeError, ValueError, KeyError):
            continue
        out.append(record)
    return out


def _base_preview_bundle(design, settings, case, result, *, name_suffix=" · EMerge FEM"):
    from .preview import build_preview

    drawing = copy.deepcopy(design)
    if settings.get("approximate_metals"):
        for material in drawing["materials"]:
            if material.get("kind") == "metal":
                material.pop("conductivity", None)
                material.pop("thickness", None)
    # Geometry-only for Results: do not run openEMS planar mesh gates. FDTD rules
    # (e.g. "three cells across each CPW gap") are unrelated to the FEM tetrahedra
    # already in ``result`` and must not fail packaging after a successful EMerge solve.
    # Mesh / domain / solver fields below replace whatever preview would have written.
    # Lumped, coax, and waveguide ports stay on the drawing so driven-class export can
    # still widen feed boxes. Microstrip and CPW are resolved onto the bundle afterwards.
    drawing["ports"] = [
        p for p in (drawing.get("ports") or [])
        if not isinstance(p, dict) or p.get("type") not in ("microstrip", "cpw")
    ]
    bundle = build_preview(None, {}, design=drawing)["bundle"]
    bundle.pop("preview", None)
    bundle["ports"] = list(bundle.get("ports") or []) + _resolved_planar_ports(design)
    bundle["name"] += name_suffix
    air_lo = [float(v) * 1000 for v in case["air"]["lo"]]
    air_hi = [float(v) * 1000 for v in case["air"]["hi"]]
    axes = [np.array([air_lo[i], air_hi[i]]) for i in range(3)]
    steps = np.array([air_hi[i] - air_lo[i] for i in range(3)], dtype=float)
    mesh_counts = result.get("mesh") or {}
    tetrahedra = mesh_counts.get("tetrahedra", 0)
    bundle["mesh"] = dict(zip("xyz", [axis.tolist() for axis in axes]))
    bundle["mesh"].update(cells=[1, 1, 1], total_cells=int(tetrahedra) if tetrahedra else 1,
                          min_cell=float(steps.min()), max_cell=float(steps.max()),
                          nodes=int(mesh_counts.get("nodes", 0)),
                          tetrahedra=int(mesh_counts.get("tetrahedra", 0)))
    _attach_fem_surface(bundle, mesh_counts)
    bundle["domain"] = dict(min=air_lo, max=air_hi)
    bundle["nf2ff_box"] = copy.deepcopy(bundle["domain"])
    bundle["nf2ff_center"] = [0, 0, 0]
    bundle["half_space"] = None
    return bundle


def nport_result_bundle(design, result):
    """Export a unified ``fairbeam.emerge-result/2`` N-port result as shared Results."""
    from fairbeam_emerge import NPORT_RESULT_SCHEMA, GEOMETRY_KINDS
    from .emerge_solver import admit_geometry

    if result.get("schema") != NPORT_RESULT_SCHEMA:
        raise ValueError("unsupported EMerge N-port result schema")
    if result.get("status") != "results_exported":
        raise ValueError("EMerge N-port result must be results_exported")
    if result.get("precision_converged") is not False:
        raise ValueError("EMerge N-port never claims mesh convergence")
    if result.get("gain_qualified") is not False:
        raise ValueError("EMerge N-port never claims qualified gain")
    geometry_kind = result.get("geometry_kind")
    if geometry_kind not in GEOMETRY_KINDS:
        raise ValueError(
            "geometry_kind must be driven_lumped, planar_microstrip, or coaxial_tem")
    settings = result["settings"]
    case = admit_geometry(design, settings, geometry_kind)
    if geometry_kind == "planar_microstrip":
        bundle = _base_preview_bundle(design, settings, case, result)
        enclosure = result.get("enclosure", case["enclosure"])
        floor = "PEC"
        other = "PEC" if enclosure == "shielded" else "Second-order absorbing"
        boundaries = {k: other for k in ("x-", "x+", "y-", "y+", "z-", "z+")}
        boundaries["z-"] = floor
        excitation_type = "Harmonic lumped strip-to-ground terminals"
        bundle["solver"] = dict(
            engine="EMerge", method="Frequency-domain FEM (experimental)",
            excitation=dict(type=excitation_type,
                            f_min=settings["f_min_hz"], f_max=settings["f_max_hz"], dc_free=True),
            boundaries=boundaries, end_criteria_db=0, max_timesteps=0,
            enclosure=enclosure)
        limitations = list(result.get("limitations", case["limitations"]))
        if enclosure == "shielded" and not any("shielded" in text.lower() for text in limitations):
            limitations.append("Shielded enclosure: exterior faces use EMerge default PEC.")
        pec = list(result.get("pec_approximations", case["pec_approximations"]))
        port_map = result.get("port_map")
        if not port_map:
            from fairbeam_emerge import port_map_from_planar_case
            port_map = port_map_from_planar_case(case)
        terminals = sorted(case["terminals"], key=lambda t: t["number"])
        default_z = [t["z0"] for t in terminals]
        experimental_extra = {"enclosure": enclosure}
    elif geometry_kind == "coaxial_tem":
        bundle = _base_preview_bundle(design, settings, case, result)
        bundle["solver"] = dict(
            engine="EMerge", method="Frequency-domain FEM (experimental)",
            excitation=dict(type="Harmonic coaxial TEM ports", f_min=settings["f_min_hz"],
                            f_max=settings["f_max_hz"], dc_free=True),
            boundaries={k: "Second-order absorbing" for k in ("x-", "x+", "y-", "y+", "z-", "z+")},
            end_criteria_db=0, max_timesteps=0)
        limitations = list(result.get("limitations", case["limitations"]))
        pec = list(result.get("pec_approximations", case.get("pec_approximations") or []))
        port_map = result.get("port_map")
        if not port_map:
            from fairbeam_emerge import port_map_from_coax_case
            port_map = port_map_from_coax_case(case)
        # Analytic TEM Z0; same formula as the worker (η0/(2π√εr)·ln(r_o/r_i)).
        eta0 = 376.730313668
        default_z = []
        for port in sorted(case["ports"], key=lambda p: p["number"]):
            default_z.append(
                (eta0 / (2.0 * math.pi * math.sqrt(float(port["er"]))))
                * math.log(float(port["r_o"]) / float(port["r_i"])))
        experimental_extra = {}
    else:
        bundle = _base_preview_bundle(design, settings, case, result)
        bundle["solver"] = dict(
            engine="EMerge", method="Frequency-domain FEM (experimental)",
            excitation=dict(type="Harmonic rectangular terminal", f_min=settings["f_min_hz"],
                            f_max=settings["f_max_hz"], dc_free=True),
            boundaries={k: "Second-order absorbing" for k in ("x-", "x+", "y-", "y+", "z-", "z+")},
            end_criteria_db=0, max_timesteps=0)
        limitations = list(result.get("limitations", case["limitations"]))
        pec = list(result.get("pec_approximations", case["pec_approximations"]))
        port_map = result.get("port_map")
        if not port_map:
            from fairbeam_emerge import port_map_from_design_case
            port_map = port_map_from_design_case(case)
        case_ports = sorted(case["ports"], key=lambda p: p["number"])
        default_z = [p["z0"] for p in case_ports]
        experimental_extra = {}
        feed_width = settings.get("feed_width_mm", 1)
        for design_port, bundle_port in zip(design["ports"], bundle["ports"]):
            width_axis = next(
                i for i in range(3) if i != "xyz".index(design_port["direction"]))
            bundle_port["start"][width_axis] -= feed_width / 2
            bundle_port["stop"][width_axis] += feed_width / 2
    bundle["run"] = _run_timing(result)
    experimental = dict(
        solver="EMerge", precision_converged=False,
        limitations=limitations, settings=settings,
        input_sha256=result.get("input_sha256"),
        pec_approximations=pec,
        geometry_kind=geometry_kind,
        phasor_convention="exp(+i omega t); native EMerge, not conjugated",
        native_phasor_convention=result.get("native_phasor_convention", "exp(+i omega t)"),
        **experimental_extra)
    if port_map:
        experimental["port_map"] = list(port_map)
    bundle["experimental"] = experimental
    z_refs = [float(v) for v in result.get("z_ref", default_z)]
    if len(z_refs) != len(default_z):
        raise ValueError(f"z_ref must hold {len(default_z)} references")
    port_results, sparams = _pack_nport_sparams(result["s"], z_refs)
    bundle["results"] = dict(
        frequency=list(result["frequency_hz"]),
        ports=port_results, sparams=sparams,
        bands=[], signals={}, farfield=[])
    _attach_field_cut(bundle, result)
    return bundle


def export_emerge_bundle(design, result):
    """Dispatch unified N-port ``emerge-result/2`` into a shared Results bundle."""
    from fairbeam_emerge import NPORT_RESULT_SCHEMA

    if result.get("schema") != NPORT_RESULT_SCHEMA:
        raise ValueError(f"unsupported EMerge result schema {result.get('schema')!r}")
    return nport_result_bundle(design, result)


def _attach_fem_surface(bundle, mesh_counts):
    """Copy exterior surface edges onto ``bundle.mesh.fem`` for Mesh view (never FDTD planes)."""
    surface = mesh_counts.get("surface")
    if not isinstance(surface, dict):
        return
    bundle["mesh"]["fem"] = {
        "nodes": int(mesh_counts.get("nodes", 0)),
        "tetrahedra": int(mesh_counts.get("tetrahedra", 0)),
        "surface": copy.deepcopy(surface),
    }


def _attach_field_cut(bundle, result):
    """Map worker ``field_cuts`` (or legacy ``field_cut``) into switchable ``field_planes``."""
    cuts = result.get("field_cuts")
    if isinstance(cuts, list) and cuts:
        cut_list = cuts
    else:
        single = result.get("field_cut")
        cut_list = [single] if single else []
    if not cut_list:
        return
    from .emerge_field_cut import FIELD_CUT_NOTE, to_field_plane

    planes = [to_field_plane(cut) for cut in cut_list]
    bundle["field_planes"] = planes
    limitations = list(bundle["experimental"].get("limitations") or [])
    if FIELD_CUT_NOTE not in limitations:
        limitations.append(FIELD_CUT_NOTE)
    bundle["experimental"]["limitations"] = limitations
    summaries = [{
        "freq_hz": plane["f"],
        "freq_choice": (plane.get("experimental") or {}).get("freq_choice"),
        "position_mm": plane["position_mm"],
        "has_phasor": bool(plane.get("phasor")),
    } for plane in planes]
    bundle["experimental"]["field_cuts"] = summaries
    # Legacy single-cut summary (first map) for older readers.
    bundle["experimental"]["field_cut"] = summaries[0]
