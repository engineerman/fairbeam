"""Admission of a planar N-port Design subset for experimental EMerge.

Turns an admitted Design plus run settings into a neutral, metre-based ``kind: "planar"`` case.
Ports are ``1…N_MAX`` homogeneous microstrip or classic CPW (``accept_lumped_terminals`` →
LumpedPort, or ``accept_modal_ports`` → WavePort) or Discrete/lumped (``accept_finite_feed``).
Anything outside the admitted subset raises ``ValueError``; nothing is dropped or coerced apart
from the explicit, user-accepted ``approximate_metals`` (force PEC) and port-map accept rewrites.
Trace metals keep ``conductivity`` / sheet thickness for EMerge ``ThinConductor`` unless
approximated as PEC. Microstrip / Discrete keep a substrate-bottom ground (PEC). Classic CPW uses
coplanar top grounds only (``ground_mode: "coplanar"``); grounded CPW is rejected. CPW terminal
faces span substrate height plus a fraction of ``air_height_mm`` above the metal plane so a
modal port can see coplanar/air fields (microstrip stays substrate-tall). This module
never imports ``emerge``, ``gmsh`` or ``emsutil``.
"""
import copy
import math

from .design import _given, check_design, design_params, resolve_names, resolve_parts, evaluate
from .emerge_design import sheet_conductor
from .emerge_limits import N_MAX, field_cut_frequencies_hz_from_settings
from .emerge_port_map import resolve
from .model import resolve_params

C0 = 299792458.0
PHASOR_CONVENTION = "exp(+i omega t)"
RESOLUTIONS = {"coarse": 0.25, "fine": 0.15}  # wavelength fractions at f_max (frozen Task 1)
PORT_PAD_MM = 1.0
METAL_EDGE_MM = 0.4
MAX_RESOURCE_CELLS = 400000  # tetrahedron-count proxy (frozen Task 1)
# O17: classic CPW quasi-TEM lives in gaps + air above metal; WavePort/Lumped face
# extends above substrate top by this fraction of air_height_mm (clamped to air box).
# Task 1 used 0.5 (human FAIL — still high S11); Task 1b tries full air column.
CPW_AIR_APERTURE_FRACTION = 1.0
_REQUIRED = ("analysis", "enclosure", "air_height_mm",
             "resolution", "f_min_hz", "f_max_hz", "points")
_ALLOWED = frozenset(_REQUIRED) | {
    "approximate_metals", "padding_mm", "refine_conductor_edges",
    "accept_lumped_terminals", "accept_modal_ports", "accept_finite_feed",
    "field_cut_frequencies_hz",
}
_TOL = 1e-9


def _positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a positive number")
    return float(value)


def _resolution_fraction(value):
    """Named preset → wavelength fraction, or a raw fraction in (0, 0.5]."""
    if value in RESOLUTIONS:
        return RESOLUTIONS[value], value
    # JSON / form paths may deliver the fraction as a decimal string.
    if isinstance(value, str) and value.strip() and value.strip() not in RESOLUTIONS:
        try:
            value = float(value.strip())
        except ValueError as exc:
            raise ValueError("Resolution must be coarse, fine, or a wavelength fraction in (0, 0.5]") from exc
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 0.5:
        raise ValueError("Resolution must be coarse, fine, or a wavelength fraction in (0, 0.5]")
    return float(value), "custom"


def _settings(settings):
    if not isinstance(settings, dict):
        raise ValueError("Settings must be an object")
    if set(settings) - _ALLOWED:
        raise ValueError("Unsupported settings must not be silently discarded: "
                         + ", ".join(sorted(map(str, set(settings) - _ALLOWED))))
    missing = [k for k in _REQUIRED if k not in settings]
    if missing:
        raise ValueError("Missing settings: " + ", ".join(missing))
    if settings["analysis"] != "emerge_nport":
        raise ValueError("Planar EMerge analysis must be emerge_nport")
    enclosure = settings["enclosure"]
    if enclosure not in ("shielded", "open"):
        raise ValueError("enclosure must be shielded or open")
    air_height = _positive(settings["air_height_mm"], "Air height")
    if enclosure == "open":
        if "padding_mm" not in settings:
            raise ValueError("padding_mm is required with open enclosure")
        padding = _positive(settings["padding_mm"], "Padding")
    else:
        if "padding_mm" in settings:
            raise ValueError("padding_mm is only valid with open enclosure, not shielded")
        padding = 0.0
    _resolution_fraction(settings["resolution"])  # validate early
    for key in ("f_min_hz", "f_max_hz"):
        v = settings[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 1e6 <= v <= 1e11:
            raise ValueError("Frequency must be between 1 MHz and 100 GHz")
    if not settings["f_min_hz"] < settings["f_max_hz"]:
        raise ValueError("The sweep band must be nonzero: f_min_hz must be below f_max_hz")
    points = settings["points"]
    if type(points) is not int or not 3 <= points <= 41:
        raise ValueError("Planar sweep supports 3 to 41 frequency points")
    if type(settings.get("approximate_metals", False)) is not bool:
        raise ValueError("approximate_metals must be boolean")
    if type(settings.get("refine_conductor_edges", True)) is not bool:
        raise ValueError("refine_conductor_edges must be boolean")
    field_cut_frequencies_hz_from_settings(settings)  # validate early; attach in admit
    refine_edges = settings.get("refine_conductor_edges", True)
    return enclosure, air_height, padding, refine_edges


def _frequencies(f_min, f_max, points):
    values = [float(f_min) + (float(f_max) - float(f_min)) * i / (points - 1) for i in range(points)]
    values[-1] = float(f_max)
    return values


def _mm(v):
    return [float(x) * 1e-3 for x in v]


def _mm_ring(ring):
    return [[float(x) * 1e-3, float(y) * 1e-3] for x, y in ring]


def _near(a, b, tol=_TOL):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def _box_bounds(start, stop):
    return [min(s, t) for s, t in zip(start, stop)], [max(s, t) for s, t in zip(start, stop)]


def _point_in_ring(x, y, ring, tol=1e-6):
    """True when (x, y) is inside or on the boundary of a simple ring."""
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy)
        if length <= tol:
            if math.hypot(x - x0, y - y0) <= tol:
                return True
            continue
        t = ((x - x0) * dx + (y - y0) * dy) / (length * length)
        if 0.0 <= t <= 1.0 and math.hypot(x - (x0 + t * dx), y - (y0 + t * dy)) <= tol:
            return True
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 0.0) + xi):
            inside = not inside
        j = i
    return inside


def _edge_covered(u0, u1, face, prop_axis, transverse, rings):
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        u = u0 + (u1 - u0) * t
        xy = [0.0, 0.0]
        xy[prop_axis] = face
        xy[transverse] = u
        if not any(_point_in_ring(xy[0], xy[1], ring) for ring in rings):
            return False
    return True


def _covers_footprint(lo, hi, sub_lo, sub_hi):
    return (_near(lo[0], sub_lo[0]) and _near(hi[0], sub_hi[0])
            and _near(lo[1], sub_lo[1]) and _near(hi[1], sub_hi[1])
            and _near(lo[2], sub_lo[2]) and _near(hi[2], sub_lo[2]))


def _admit_planar_ports(ports):
    """Validate planar port count / homogeneous type / numbers. Returns ``(sorted_ports, kind)``.

    ``kind`` is ``"microstrip"``, ``"cpw"``, or ``"lumped"``.
    """
    n = len(ports)
    if n < 1 or n > N_MAX:
        raise ValueError(
            f"Planar EMerge needs 1 to {N_MAX} ports of the same type "
            f"(got {n})")
    numbers = []
    for port in ports:
        number = port.get("number")
        if type(number) is not int:
            raise ValueError("Planar EMerge port numbers must be integers 1…N")
        numbers.append(number)
    if set(numbers) != set(range(1, n + 1)):
        raise ValueError(f"Planar EMerge needs contiguous port numbers 1…{n}")
    port_types = [p.get("type", "lumped") for p in ports]
    all_microstrip = all(t == "microstrip" for t in port_types)
    all_cpw = all(t == "cpw" for t in port_types)
    all_lumped = all(t == "lumped" for t in port_types)
    if not (all_microstrip or all_cpw or all_lumped):
        raise ValueError(
            "Planar EMerge needs all ports microstrip, all CPW, or all Discrete (lumped); "
            "mixed types are rejected")
    if all_microstrip:
        kind = "microstrip"
    elif all_cpw:
        kind = "cpw"
    else:
        kind = "lumped"
    return sorted(ports, key=lambda p: p["number"]), kind


def _pec_on_zm(boundaries):
    """True when Design boundaries put PEC on the substrate z− face."""
    if isinstance(boundaries, str):
        return boundaries == "PEC"
    if isinstance(boundaries, list) and len(boundaries) >= 5:
        return boundaries[4] == "PEC"
    return False


def _cpw_aperture_span_mm(strip_u0, strip_u1, gap_mm):
    """Board-edge transverse span: center strip widened by ``2*gap`` each side (locked O8)."""
    return strip_u0 - 2.0 * gap_mm, strip_u1 + 2.0 * gap_mm


def _cpw_terminal_z_top_mm(sub_hi_z, air_height_mm):
    """CPW board-edge face top z (mm): substrate top plus air above metal (O17).

    Microstrip / Discrete keep substrate-only height elsewhere. Extension is
    ``CPW_AIR_APERTURE_FRACTION * air_height_mm``, clamped so the port top stays at or
    below ``sub_hi_z + air_height_mm`` (open-enclosure padding is above that box).
    """
    air_above = min(CPW_AIR_APERTURE_FRACTION * float(air_height_mm), float(air_height_mm))
    return float(sub_hi_z) + air_above


def admit(design, settings):
    """Return the neutral planar EMerge case for ``design`` or raise ``ValueError``."""
    enclosure, air_height_mm, padding_mm, refine_edges = _settings(settings)
    approximate = settings.get("approximate_metals", False)
    check_design(design)
    design = copy.deepcopy(design)
    pec_approximations = []
    if approximate:
        for material in design.get("materials", []):
            if material.get("kind") == "metal" and _given(material.get("conductivity")):
                pec_approximations.append(material.get("name"))
                material.pop("conductivity", None)
                material.pop("thickness", None)
    names = resolve_names(design, resolve_params(design_params(design), {}))
    if design.get("resistors") or design.get("lumped_elements"):
        raise ValueError("Additional lumped elements are not supported by planar EMerge")
    ports, port_kind = _admit_planar_ports(design.get("ports", []))
    all_microstrip = port_kind == "microstrip"
    all_cpw = port_kind == "cpw"
    if all_microstrip or all_cpw:
        if (settings.get("accept_modal_ports") is not True
                and settings.get("accept_lumped_terminals") is not True):
            label = "CPW" if all_cpw else "microstrip"
            raise ValueError(
                "Explicit accept_modal_ports (WavePort) or accept_lumped_terminals "
                f"(LumpedPort) is required for planar {label} EMerge")
    else:
        if settings.get("accept_finite_feed") is not True:
            raise ValueError("Explicit experimental finite-feed acceptance is required")
    resolved_ports = []
    for port in ports:
        mapped = resolve(port, path="planar", settings=settings)
        if not mapped["ok"]:
            raise ValueError(mapped["error"])
        start = [float(evaluate(v, names)) for v in port["start"]]
        stop = [float(evaluate(v, names)) for v in port["stop"]]
        if all_microstrip or all_cpw:
            if port.get("direction") not in ("x", "y"):
                raise ValueError(
                    f"Planar EMerge {port_kind} port direction must be x or y")
            if all_microstrip:
                if port.get("excitation_direction") != "z":
                    raise ValueError("Planar EMerge microstrip excitation_direction must be z")
            else:
                transverse_name = "y" if port["direction"] == "x" else "x"
                if port.get("excitation_direction") != transverse_name:
                    raise ValueError(
                        "Planar EMerge CPW excitation_direction must be the in-plane "
                        f"transverse axis ({transverse_name})")
            conductor = next(
                (m for m in design.get("materials", []) if m.get("name") == port.get("conductor")), None)
            if conductor is None or conductor.get("kind") != "metal":
                raise ValueError("Planar port conductor must reference a metal material")
            impedance = float(evaluate(port.get("reference_ohm", 50), names))
            if not math.isfinite(impedance) or impedance <= 0:
                raise ValueError("Planar port reference_ohm must be a positive real number")
            entry = {
                "number": int(port["number"]), "kind": port_kind,
                "direction": port["direction"],
                "start": start, "stop": stop, "z0": impedance,
                "design_port_type": port.get("type", port_kind),
                "mapped_bc": mapped["mapped_bc"],
                "approximations": list(mapped["approximations"]),
                "accept_used": list(mapped["accept_used"]),
            }
            if all_cpw:
                gap = float(evaluate(port.get("gap"), names))
                if not math.isfinite(gap) or gap <= 0:
                    raise ValueError("Planar CPW port gap must be a positive real number")
                entry["gap"] = gap
            resolved_ports.append(entry)
        else:
            if port.get("direction") != "z":
                raise ValueError("Planar EMerge Discrete port direction must be z")
            impedance = float(evaluate(port.get("R", 50), names))
            if not math.isfinite(impedance) or impedance <= 0 or port.get("X"):
                raise ValueError("Planar Discrete port needs a positive real R")
            resolved_ports.append({
                "number": int(port["number"]), "kind": "lumped",
                "start": start, "stop": stop, "z0": impedance,
                "design_port_type": port.get("type", "lumped"),
                "mapped_bc": mapped["mapped_bc"],
                "approximations": list(mapped["approximations"]),
                "accept_used": list(mapped["accept_used"]),
            })

    substrate = None
    # ("box", lo, hi, axis, sigma, thickness_m) or ("polygon", ring, elevation, sigma, thickness_m)
    metal_items = []
    for part in resolve_parts(design, names):
        original = design["parts"][part["index"]]
        if original.get("transforms") or original.get("cuts") or part.get("voids"):
            raise ValueError("Planar EMerge does not support transforms, cuts or voids")
        material = part["material"]
        metal = material["kind"] == "metal"
        if not metal and material["kind"] != "dielectric":
            raise ValueError("Only metal and isotropic dielectric materials are supported")
        if not metal:
            eps = float(evaluate(material.get("eps_r", 1), names))
            mu = float(evaluate(material.get("mu_r", 1), names))
            loss = float(evaluate(material.get("tan_d", 0), names))
            if loss and "tan_d_freq" not in material:
                raise ValueError("Lossy dielectric needs an explicit tan_d_freq reference in GHz")
            if not all(math.isfinite(v) for v in (eps, mu, loss)) or min(eps, mu) <= 0 or loss < 0:
                raise ValueError("Invalid dielectric properties")
            if len(part["prims"]) != 1 or part["prims"][0]["kind"] != "box" or part["prims"][0].get("_matrix"):
                raise ValueError("Planar EMerge needs exactly one dielectric axis-aligned box")
            lo, hi = _box_bounds(part["prims"][0]["start"], part["prims"][0]["stop"])
            if any(_near(lo[k], hi[k]) for k in range(3)):
                raise ValueError("Dielectric geometry must have volume")
            if substrate is not None:
                raise ValueError("Planar EMerge needs exactly one dielectric part")
            substrate = {"lo": lo, "hi": hi, "eps_r": eps, "mu_r": mu, "tan_d": loss}
            continue

        sigma, thickness_m = sheet_conductor(material, names)
        for p in part["prims"]:
            if p.get("_matrix"):
                raise ValueError("Planar EMerge supports untransformed metal primitives only")
            if p["kind"] == "box":
                lo, hi = _box_bounds(p["start"], p["stop"])
                flat = [k for k in range(3) if _near(lo[k], hi[k])]
                if len(flat) != 1:
                    raise ValueError("Planar EMerge rejects metal boxes with volume")
                metal_items.append(("box", lo, hi, flat[0], sigma, thickness_m))
            elif p["kind"] == "polygon":
                if p["normal"] != 2:
                    raise ValueError("Planar EMerge polygons must have normal z")
                if len(p["points"]) < 3:
                    raise ValueError("Planar EMerge polygons need at least 3 vertices")
                metal_items.append(("polygon", [[float(q[0]), float(q[1])] for q in p["points"]],
                                   float(p["elevation"]), sigma, thickness_m))
            else:
                raise ValueError("Planar EMerge rejects unsupported metal primitives")

    if substrate is None:
        raise ValueError("Planar EMerge needs exactly one dielectric part")
    sub_lo, sub_hi = substrate["lo"], substrate["hi"]
    if not (sub_hi[2] - sub_lo[2] > 0):
        raise ValueError("Substrate height must be positive")

    traces = []
    ground_box = None
    for item in metal_items:
        if item[0] == "box":
            _, lo, hi, axis, sigma, thickness_m = item
            if axis != 2:
                raise ValueError("Planar EMerge metal sheets must have normal z")
            if _near(lo[2], sub_lo[2]):
                if not _covers_footprint(lo, hi, sub_lo, sub_hi):
                    raise ValueError("Ground metal must be a z-flat box covering the substrate footprint")
                if ground_box is not None:
                    raise ValueError("Planar EMerge expects a single ground sheet")
                # Ground stays PEC (infinite ground model); σ on the ground material is ignored.
                ground_box = (lo, hi)
                continue
            if not _near(lo[2], sub_hi[2]):
                raise ValueError("Trace metal must lie on the substrate top elevation")
            traces.append(([[lo[0], lo[1]], [hi[0], lo[1]], [hi[0], hi[1]], [lo[0], hi[1]]],
                           lo[2], sigma, thickness_m))
        else:
            _, ring, elevation, sigma, thickness_m = item
            if not _near(elevation, sub_hi[2]):
                raise ValueError("Trace metal must lie on the substrate top elevation")
            traces.append((ring, elevation, sigma, thickness_m))

    boundaries = design.get("simulation", {}).get("boundaries") or []
    if all_cpw:
        if ground_box is not None:
            raise ValueError(
                "Grounded CPW is not admitted yet (bottom ground sheet present)")
        if _pec_on_zm(boundaries):
            raise ValueError("Grounded CPW is not admitted yet (PEC on z−)")
        if len(traces) < 3:
            raise ValueError(
                "Classic CPW needs a center strip and at least two coplanar ground "
                "sheets on the substrate top")
        ground_mode = "coplanar"
    else:
        ground_ok = ground_box is not None
        if not ground_ok:
            if _pec_on_zm(boundaries):
                ground_ok = True
            else:
                raise ValueError(
                    "Planar EMerge needs a ground sheet at the substrate bottom or PEC on z−")
        ground_mode = "bottom"

    rings = [ring for ring, _z, _sigma, _thick in traces]
    terminals = []
    terminal_faces = []
    for port in sorted(resolved_ports, key=lambda p: p["number"]):
        a, b = port["start"], port["stop"]
        if port["kind"] in ("microstrip", "cpw"):
            prop = "xyz".index(port["direction"])
            transverse = 1 - prop
            faces = (a[prop], b[prop])
            on_edge = [_near(face, sub_lo[prop]) or _near(face, sub_hi[prop]) for face in faces]
            if sum(1 for ok in on_edge if ok) != 1:
                raise ValueError(
                    f"Each {port['kind']} port face must lie on the substrate edge")
            face = faces[0] if on_edge[0] else faces[1]
            strip_u0, strip_u1 = sorted((a[transverse], b[transverse]))
            if not (strip_u1 - strip_u0 > 0):
                raise ValueError(
                    f"{port['kind'].capitalize()} port must span a nonzero strip width")
            if port["kind"] == "cpw":
                gap = port["gap"]
                u0, u1 = _cpw_aperture_span_mm(strip_u0, strip_u1, gap)
                if not _edge_covered(strip_u0, strip_u1, face, prop, transverse, rings):
                    raise ValueError(
                        "A center strip must cover the CPW port strip across its full width")
                left_lo, left_hi = u0, strip_u0 - gap
                right_lo, right_hi = strip_u1 + gap, u1
                if not (left_hi - left_lo > 0 and right_hi - right_lo > 0):
                    raise ValueError("CPW aperture into coplanar grounds must be nonzero")
                if not _edge_covered(left_lo, left_hi, face, prop, transverse, rings):
                    raise ValueError(
                        "Classic CPW needs coplanar ground metal beside the strip "
                        "(into-ground aperture side)")
                if not _edge_covered(right_lo, right_hi, face, prop, transverse, rings):
                    raise ValueError(
                        "Classic CPW needs coplanar ground metal beside the strip "
                        "(into-ground aperture side)")
            else:
                u0, u1 = strip_u0, strip_u1
                if not _edge_covered(u0, u1, face, prop, transverse, rings):
                    raise ValueError(
                        "A trace must cover the terminal top edge across the full strip width")
        else:
            # Discrete: Design start/stop is the board-edge plate (flat on x or y); no feed_width_mm.
            lo_p, hi_p = _box_bounds(a, b)
            flat_xy = [k for k in (0, 1) if _near(lo_p[k], hi_p[k])]
            if len(flat_xy) != 1:
                raise ValueError(
                    "Each Discrete port must be a plate on the board-edge face (flat on x or y)")
            prop = flat_xy[0]
            transverse = 1 - prop
            face = lo_p[prop]
            if not (_near(face, sub_lo[prop]) or _near(face, sub_hi[prop])):
                raise ValueError("Each Discrete port face must lie on the substrate edge")
            u0, u1 = lo_p[transverse], hi_p[transverse]
            if not (u1 - u0 > 0):
                raise ValueError("Discrete port must span a nonzero strip width")
            if not (_near(lo_p[2], sub_lo[2]) and _near(hi_p[2], sub_hi[2])):
                raise ValueError("Discrete port must span substrate height (strip-to-ground)")
            if not _edge_covered(u0, u1, face, prop, transverse, rings):
                raise ValueError(
                    "A trace must cover the terminal top edge across the full strip width")
        if all_cpw:
            z_top = _cpw_terminal_z_top_mm(sub_hi[2], air_height_mm)
        else:
            z_top = sub_hi[2]
        height = z_top - sub_lo[2]
        lo = [0.0, 0.0, sub_lo[2]]
        hi = [0.0, 0.0, z_top]
        lo[prop] = hi[prop] = face
        lo[transverse], hi[transverse] = u0, u1
        terminals.append({
            "number": port["number"], "lo": _mm(lo), "hi": _mm(hi),
            "width": (u1 - u0) * 1e-3, "height": height * 1e-3, "z0": port["z0"],
            "design_port_type": port["design_port_type"],
            "mapped_bc": port["mapped_bc"],
            "approximations": list(port["approximations"]),
            "accept_used": list(port["accept_used"]),
        })
        terminal_faces.append((prop, face, _near(face, sub_lo[prop])))

    air_lo = list(sub_lo)
    air_hi = list(sub_hi)
    air_hi[2] = sub_hi[2] + air_height_mm
    for prop, face, on_lo in terminal_faces:
        if on_lo:
            air_lo[prop] = min(air_lo[prop], face - PORT_PAD_MM)
        else:
            air_hi[prop] = max(air_hi[prop], face + PORT_PAD_MM)
    if enclosure == "open":
        for axis in (0, 1):
            air_lo[axis] -= padding_mm
            air_hi[axis] += padding_mm
        air_hi[2] += padding_mm

    f_min, f_max = float(settings["f_min_hz"]), float(settings["f_max_hz"])
    fraction, resolution_name = _resolution_fraction(settings["resolution"])
    volume = math.prod((air_hi[k] - air_lo[k]) * 1e-3 for k in range(3))
    cells = volume / (C0 / f_max * fraction) ** 3
    if cells > MAX_RESOURCE_CELLS:
        raise ValueError(f"Domain too large for the EMerge prototype (about {cells:.0f} cells, "
                         f"limit {MAX_RESOURCE_CELLS}); reduce padding or use coarse resolution")

    mapped0 = resolved_ports[0]["mapped_bc"] if resolved_ports else None
    if all_microstrip:
        if mapped0 == "WavePort":
            port_limit = (
                "Each microstrip port becomes a WavePort at the board-edge face; "
                "feed_shift, measurement_shift and termination are unused in this FEM run."
            )
        else:
            port_limit = (
                "Each microstrip port becomes a lumped strip-to-ground terminal at the board-edge face; "
                "feed_shift, measurement_shift and termination are unused in this FEM run."
            )
    elif all_cpw:
        if mapped0 == "WavePort":
            port_limit = (
                "Each CPW port becomes a WavePort at the board-edge CPW aperture "
                "(center strip + gaps into coplanar grounds); "
                "feed_shift, measurement_shift and termination are unused in this FEM run."
            )
        else:
            port_limit = (
                "Each CPW port becomes a lumped gap terminal at the board-edge CPW aperture "
                "(center strip + gaps into coplanar grounds, not strip-to-ground); "
                "feed_shift, measurement_shift and termination are unused in this FEM run."
            )
    else:
        port_limit = (
            "Each Discrete port becomes a LumpedPort plate at the board-edge face; "
            "width comes from the Design plate, not from feed_width_mm."
        )
    limitations = [
        port_limit,
        f"Enclosure is {enclosure}; mesh and padding convergence are not certified.",
        "No far field in this run.",
    ]
    if all_cpw:
        limitations.append(
            "Classic CPW uses coplanar top grounds only; admit does not invent a "
            "substrate-bottom ground.")
    else:
        limitations.append(
            "Substrate-bottom ground remains PEC even when the ground material has finite conductivity.")
    if mapped0 == "WavePort" and (all_microstrip or all_cpw):
        if all_cpw:
            limitations.append(
                "WavePort faces use the board-edge CPW aperture; EMerge may warn that "
                "ports are partially not on the exterior boundary of the simulation domain.")
        else:
            limitations.append(
                "WavePort faces reuse the strip-to-ground board-edge plate; EMerge may warn that "
                "ports are partially not on the exterior boundary of the simulation domain.")
    if substrate["tan_d"]:
        limitations.append("Constant loss tangent; frequency dependence is not modelled beyond tan_d_freq.")
    if pec_approximations:
        limitations.append("Finite conductor loss omitted by PEC approximation: "
                           + ", ".join(map(str, pec_approximations)))
    elif any(sigma is not None for _ring, _z, sigma, _thick in traces):
        limitations.append(
            "Conductor loss on traces via EMerge ThinConductor (σ and sheet thickness); "
            "surface roughness is not modelled.")

    trace_dicts = []
    for ring, z, sigma, thickness_m in traces:
        entry = {"xy": _mm_ring(ring), "z": z * 1e-3}
        if sigma is not None:
            entry["conductivity"] = float(sigma)
            entry["thickness_m"] = float(thickness_m)
        trace_dicts.append(entry)

    case = {
        "kind": "planar",
        "substrate": {
            "lo": _mm(sub_lo), "hi": _mm(sub_hi),
            "eps_r": substrate["eps_r"], "mu_r": substrate["mu_r"], "tan_d": substrate["tan_d"],
        },
        "traces": trace_dicts,
        "ground_z": sub_lo[2] * 1e-3,
        "ground_mode": ground_mode,
        "terminals": terminals,
        "air": {"lo": _mm(air_lo), "hi": _mm(air_hi)},
        "enclosure": enclosure,
        "frequencies_hz": _frequencies(f_min, f_max, settings["points"]),
        "resolution": fraction,
        "resolution_name": resolution_name,
        "phasor_convention_out": PHASOR_CONVENTION,
        "limitations": limitations,
        "pec_approximations": pec_approximations,
    }
    if refine_edges:
        case["metal_edge_m"] = METAL_EDGE_MM * 1e-3
    field_cut_hz = field_cut_frequencies_hz_from_settings(settings)
    if field_cut_hz is not None:
        case["field_cut_frequencies_hz"] = field_cut_hz
    return case
