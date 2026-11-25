"""Admission of a stripline sandwich for experimental EMerge.

Turns an admitted Design plus run settings into a metre-based case with kind
"stripline". One dielectric box, a ground sheet on each face, and one strip
elevation strictly between those faces. Ports are 1 to N_MAX, all lumped, and
map through the planar lumped path to LumpedPort. Anything outside that subset
raises ValueError. This module never imports emerge, gmsh, or emsutil.
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
RESOLUTIONS = {"coarse": 0.25, "fine": 0.15}  # wavelength fractions at f_max, same as planar
METAL_EDGE_MM = 0.4
MAX_RESOURCE_CELLS = 400000  # same tetrahedron-count proxy as planar
_REQUIRED = ("analysis", "accept_finite_feed", "padding_mm", "resolution",
             "f_min_hz", "f_max_hz", "points")
_ALLOWED = frozenset(_REQUIRED) | {
    "approximate_metals", "refine_conductor_edges", "field_cut_frequencies_hz",
}
_TOL = 1e-9


def _positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a positive number")
    return float(value)


def _resolution_fraction(value):
    """Named preset to wavelength fraction, or a raw fraction in (0, 0.5]."""
    if value in RESOLUTIONS:
        return RESOLUTIONS[value], value
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
        raise ValueError("Stripline EMerge analysis must be emerge_nport")
    if settings["accept_finite_feed"] is not True:
        raise ValueError("Explicit experimental finite-feed acceptance is required")
    padding = _positive(settings["padding_mm"], "Padding")
    _resolution_fraction(settings["resolution"])
    for key in ("f_min_hz", "f_max_hz"):
        v = settings[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 1e6 <= v <= 1e11:
            raise ValueError("Frequency must be between 1 MHz and 100 GHz")
    if not settings["f_min_hz"] < settings["f_max_hz"]:
        raise ValueError("The sweep band must be nonzero: f_min_hz must be below f_max_hz")
    points = settings["points"]
    if type(points) is not int or not 3 <= points <= 41:
        raise ValueError("Stripline sweep supports 3 to 41 frequency points")
    if type(settings.get("approximate_metals", False)) is not bool:
        raise ValueError("approximate_metals must be boolean")
    if type(settings.get("refine_conductor_edges", True)) is not bool:
        raise ValueError("refine_conductor_edges must be boolean")
    field_cut_frequencies_hz_from_settings(settings)
    refine_edges = settings.get("refine_conductor_edges", True)
    return padding, refine_edges


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


def _covers_xy(lo, hi, sub_lo, sub_hi):
    return (_near(lo[0], sub_lo[0]) and _near(hi[0], sub_hi[0])
            and _near(lo[1], sub_lo[1]) and _near(hi[1], sub_hi[1]))


def _box_ring(lo, hi):
    return [[lo[0], lo[1]], [hi[0], lo[1]], [hi[0], hi[1]], [lo[0], hi[1]]]


def _admit_ports(ports):
    """Validate lumped port count and numbers. Returns ports sorted by number."""
    n = len(ports)
    if n < 1 or n > N_MAX:
        raise ValueError(f"Stripline EMerge needs 1 to {N_MAX} lumped ports (got {n})")
    numbers = []
    for port in ports:
        number = port.get("number")
        if type(number) is not int:
            raise ValueError("Stripline EMerge port numbers must be integers 1…N")
        numbers.append(number)
    if set(numbers) != set(range(1, n + 1)):
        raise ValueError(f"Stripline EMerge needs contiguous port numbers 1…{n}")
    if any(p.get("type", "lumped") != "lumped" for p in ports):
        raise ValueError("Stripline EMerge needs all ports to be lumped")
    return sorted(ports, key=lambda p: p["number"])


def _span_reaches(z0, z1, target):
    lo, hi = (z0, z1) if z0 <= z1 else (z1, z0)
    return (lo <= target <= hi) or _near(lo, target) or _near(hi, target)


def _z_pair(z0, z1, a, b):
    return (_near(z0, a) and _near(z1, b)) or (_near(z0, b) and _near(z1, a))


def admit(design, settings):
    """Return the neutral stripline EMerge case for ``design`` or raise ``ValueError``."""
    padding_mm, refine_edges = _settings(settings)
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
        raise ValueError("Additional lumped elements are not supported by stripline EMerge")
    ports = _admit_ports(design.get("ports", []))
    resolved_ports = []
    for port in ports:
        if port.get("direction") != "z":
            raise ValueError("Stripline EMerge lumped port direction must be z")
        mapped = resolve(port, path="planar", settings=settings)
        if not mapped["ok"]:
            raise ValueError(mapped["error"])
        start = [float(evaluate(v, names)) for v in port["start"]]
        stop = [float(evaluate(v, names)) for v in port["stop"]]
        impedance = float(evaluate(port.get("R", 50), names))
        if not math.isfinite(impedance) or impedance <= 0 or port.get("X"):
            raise ValueError("Stripline lumped port needs a positive real R")
        resolved_ports.append({
            "number": int(port["number"]),
            "start": start,
            "stop": stop,
            "z0": impedance,
            "design_port_type": port.get("type", "lumped"),
            "mapped_bc": mapped["mapped_bc"],
            "approximations": list(mapped["approximations"]),
            "accept_used": list(mapped["accept_used"]),
        })

    substrate = None
    # ("box", lo, hi, sigma, thickness_m) or ("polygon", ring, elevation, sigma, thickness_m)
    metal_items = []
    for part in resolve_parts(design, names):
        original = design["parts"][part["index"]]
        if original.get("transforms") or original.get("cuts") or part.get("voids"):
            raise ValueError("Stripline EMerge does not support transforms, cuts or voids")
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
                raise ValueError("Stripline EMerge needs exactly one dielectric axis-aligned box")
            lo, hi = _box_bounds(part["prims"][0]["start"], part["prims"][0]["stop"])
            if any(_near(lo[k], hi[k]) for k in range(3)):
                raise ValueError("Dielectric geometry must have volume")
            if substrate is not None:
                raise ValueError("Stripline EMerge needs exactly one dielectric part")
            substrate = {"lo": lo, "hi": hi, "eps_r": eps, "mu_r": mu, "tan_d": loss}
            continue

        sigma, thickness_m = sheet_conductor(material, names)
        for p in part["prims"]:
            if p.get("_matrix"):
                raise ValueError("Stripline EMerge supports untransformed metal primitives only")
            if p["kind"] == "box":
                lo, hi = _box_bounds(p["start"], p["stop"])
                flat = [k for k in range(3) if _near(lo[k], hi[k])]
                if len(flat) != 1:
                    raise ValueError("Stripline EMerge rejects metal boxes with volume")
                if flat[0] != 2:
                    raise ValueError("Stripline EMerge metal sheets must have normal z")
                metal_items.append(("box", lo, hi, sigma, thickness_m))
            elif p["kind"] == "polygon":
                if p["normal"] != 2:
                    raise ValueError("Stripline EMerge polygons must have normal z")
                if len(p["points"]) < 3:
                    raise ValueError("Stripline EMerge polygons need at least 3 vertices")
                metal_items.append(("polygon", [[float(q[0]), float(q[1])] for q in p["points"]],
                                   float(p["elevation"]), sigma, thickness_m))
            else:
                raise ValueError("Stripline EMerge rejects unsupported metal primitives")

    if substrate is None:
        raise ValueError("Stripline EMerge needs exactly one dielectric part")
    sub_lo, sub_hi = substrate["lo"], substrate["hi"]
    bottom_z, top_z = sub_lo[2], sub_hi[2]
    grounds = set()
    traces = []
    for item in metal_items:
        if item[0] == "box":
            _, lo, hi, sigma, thickness_m = item
            z = lo[2]
            ring = _box_ring(lo, hi)
        else:
            _, ring, z, sigma, thickness_m = item
        on_bottom = _near(z, bottom_z)
        on_top = _near(z, top_z)
        if on_bottom or on_top:
            if item[0] != "box" or not _covers_xy(lo, hi, sub_lo, sub_hi):
                raise ValueError("A strip on a ground face is not admitted")
            face = "bottom" if on_bottom else "top"
            if face in grounds:
                raise ValueError("A third ground is not admitted")
            grounds.add(face)
            continue
        if not (bottom_z < z < top_z):
            raise ValueError("Trace metal must lie strictly between the ground planes")
        traces.append((ring, z, sigma, thickness_m))

    if grounds != {"bottom", "top"}:
        raise ValueError("Stripline EMerge needs one ground sheet on each dielectric face")
    if not traces:
        raise ValueError("Stripline EMerge needs a strip strictly between the grounds")
    strip_z = traces[0][1]
    if any(not _near(z, strip_z) for _ring, z, _sigma, _thick in traces):
        raise ValueError("Trace metal must share one elevation between the grounds")

    rings = [ring for ring, _z, _sigma, _thick in traces]
    terminals = []
    for port in resolved_ports:
        lo_p, hi_p = _box_bounds(port["start"], port["stop"])
        flat_xy = [k for k in (0, 1) if _near(lo_p[k], hi_p[k])]
        if len(flat_xy) != 1:
            raise ValueError("Each lumped port must be a plate flat in x or y")
        prop = flat_xy[0]
        transverse = 1 - prop
        face = lo_p[prop]
        if not (_near(face, sub_lo[prop]) or _near(face, sub_hi[prop])):
            raise ValueError("Each lumped port face must lie on the dielectric edge")
        u0, u1 = lo_p[transverse], hi_p[transverse]
        if not (u1 - u0 > 0):
            raise ValueError("Lumped port must span a nonzero width")
        z0, z1 = lo_p[2], hi_p[2]
        if _span_reaches(z0, z1, bottom_z) and _span_reaches(z0, z1, top_z):
            raise ValueError("A port plate that reaches both grounds is rejected")
        if not (_z_pair(z0, z1, bottom_z, strip_z) or _z_pair(z0, z1, top_z, strip_z)):
            raise ValueError("Port z span must run from one ground face to the strip elevation")
        if not _edge_covered(u0, u1, face, prop, transverse, rings):
            raise ValueError("A trace must cover the port across its full width at the dielectric edge")
        terminals.append({
            "number": port["number"],
            "lo": _mm(lo_p),
            "hi": _mm(hi_p),
            "width": (u1 - u0) * 1e-3,
            "height": (z1 - z0) * 1e-3,
            "z0": port["z0"],
            "design_port_type": port["design_port_type"],
            "mapped_bc": port["mapped_bc"],
            "approximations": list(port["approximations"]),
            "accept_used": list(port["accept_used"]),
        })

    air_lo = [sub_lo[0] - padding_mm, sub_lo[1] - padding_mm, sub_lo[2]]
    air_hi = [sub_hi[0] + padding_mm, sub_hi[1] + padding_mm, sub_hi[2]]
    f_min, f_max = float(settings["f_min_hz"]), float(settings["f_max_hz"])
    fraction, resolution_name = _resolution_fraction(settings["resolution"])
    volume = math.prod((air_hi[k] - air_lo[k]) * 1e-3 for k in range(3))
    cells = volume / (C0 / f_max * fraction) ** 3
    if cells > MAX_RESOURCE_CELLS:
        raise ValueError(f"Domain too large for the EMerge prototype (about {cells:.0f} cells, "
                         f"limit {MAX_RESOURCE_CELLS}); reduce padding or use coarse resolution")

    limitations = [
        "The domain height is the ground separation.",
        "enclosure and air_height_mm are unused.",
        f"The lateral margin is padding_mm ({padding_mm:g} mm).",
        "Lid and floor stay PEC.",
        "There is no far field.",
    ]
    if substrate["tan_d"]:
        limitations.append("Constant loss tangent.")
    if pec_approximations:
        limitations.append("Finite conductor loss omitted by PEC approximation: "
                           + ", ".join(map(str, pec_approximations)))
    elif any(sigma is not None for _ring, _z, sigma, _thick in traces):
        limitations.append(
            "Conductor loss on traces uses conductivity and sheet thickness. "
            "Surface roughness is not modelled.")

    trace_dicts = []
    for ring, z, sigma, thickness_m in traces:
        entry = {"xy": _mm_ring(ring), "z": z * 1e-3}
        if sigma is not None:
            entry["conductivity"] = float(sigma)
            entry["thickness_m"] = float(thickness_m)
        trace_dicts.append(entry)

    case = {
        "kind": "stripline",
        "substrate": {
            "lo": _mm(sub_lo), "hi": _mm(sub_hi),
            "eps_r": substrate["eps_r"], "mu_r": substrate["mu_r"], "tan_d": substrate["tan_d"],
        },
        "traces": trace_dicts,
        "grounds": {"bottom_z": bottom_z * 1e-3, "top_z": top_z * 1e-3},
        "terminals": terminals,
        "air": {"lo": _mm(air_lo), "hi": _mm(air_hi)},
        "padding_m": padding_mm * 1e-3,
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
