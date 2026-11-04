"""Admission of a bounded Design subset for the experimental EMerge driven port.

Turns an admitted Design plus run settings into a neutral, metre-based case dictionary.
It follows the admission rules of ``elmer_driven.prepare`` (not its mesher) and never imports
``emerge``, ``gmsh`` or ``emsutil``: those belong to the separate worker process only.
Anything outside the admitted subset raises ``ValueError``; nothing is dropped or coerced,
apart from the explicit, user-accepted ``approximate_metals`` and finite feed width.
"""
import copy
import math

from .design import check_design, design_params, resolve_names, resolve_parts, evaluate
from .model import resolve_params

C0 = 299792458.0
PHASOR_CONVENTION = "exp(+i omega t)"
RESOLUTIONS = {"coarse": 0.25, "fine": 0.15}  # wavelength fractions at f_max (provisional)
MAX_RESOURCE_CELLS = 200000  # provisional proxy limit
_REQUIRED = ("analysis", "accept_finite_feed", "feed_width_mm", "padding_mm", "resolution",
             "f_min_hz", "f_max_hz", "points")
_ALLOWED = frozenset(_REQUIRED) | {"approximate_metals"}
_PORT_KEYS = {"type", "number", "R", "start", "stop", "direction", "excite", "priority", "name", "label"}


def _positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a positive number")
    return float(value)


def _settings(settings):
    if not isinstance(settings, dict):
        raise ValueError("Settings must be an object")
    if set(settings) - _ALLOWED:
        raise ValueError("Unsupported settings must not be silently discarded: "
                         + ", ".join(sorted(map(str, set(settings) - _ALLOWED))))
    missing = [k for k in _REQUIRED if k not in settings]
    if missing:
        raise ValueError("Missing settings: " + ", ".join(missing))
    if settings["analysis"] != "driven" or settings["accept_finite_feed"] is not True:
        raise ValueError("Explicit experimental finite-feed acceptance is required")
    feed_width = _positive(settings["feed_width_mm"], "Finite feed width")
    padding = _positive(settings["padding_mm"], "Padding")
    if settings["resolution"] not in RESOLUTIONS:
        raise ValueError("Resolution must be coarse or fine")
    for key in ("f_min_hz", "f_max_hz"):
        v = settings[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 1e6 <= v <= 1e11:
            raise ValueError("Frequency must be between 1 MHz and 100 GHz")
    if not settings["f_min_hz"] < settings["f_max_hz"]:
        raise ValueError("The sweep band must be nonzero: f_min_hz must be below f_max_hz")
    points = settings["points"]
    if type(points) is not int or not 3 <= points <= 21:
        raise ValueError("Initial driven sweep supports 3 to 21 frequency points")
    if type(settings.get("approximate_metals", False)) is not bool:
        raise ValueError("approximate_metals must be boolean")
    return feed_width, padding


def _frequencies(f_min, f_max, points):
    values = [float(f_min) + (float(f_max) - float(f_min)) * i / (points - 1) for i in range(points)]
    values[-1] = float(f_max)
    return values


def _mm(v):
    return [float(x) * 1e-3 for x in v]


def admit(design, settings):
    """Return the neutral EMerge case for ``design`` or raise ``ValueError``."""
    feed_width_mm, padding_mm = _settings(settings)
    approximate = settings.get("approximate_metals", False)
    check_design(design)
    design = copy.deepcopy(design)
    pec_approximations = []
    if approximate:
        for material in design.get("materials", []):
            if material.get("kind") == "metal" and material.get("conductivity") is not None:
                pec_approximations.append(material.get("name"))
                material.pop("conductivity", None)
                material.pop("thickness", None)
    names = resolve_names(design, resolve_params(design_params(design), {}))
    ports = design.get("ports", [])
    if len(ports) != 1 or ports[0].get("type", "lumped") != "lumped":
        raise ValueError("Driven EMerge currently needs one rectangular lumped port")
    if design.get("resistors") or design.get("lumped_elements"):
        raise ValueError("Additional lumped elements are not yet supported by driven EMerge")
    port = ports[0]
    if port.get("excite", True) is False:
        raise ValueError("The single driven port must be excited")
    if set(port) - _PORT_KEYS:
        raise ValueError("Unsupported port properties must not be silently discarded")
    if port.get("direction") not in ("x", "y", "z"):
        raise ValueError("The port direction must be x, y or z")
    direction = "xyz".index(port["direction"])
    a, b = [[float(evaluate(v, names)) for v in port[key]] for key in ("start", "stop")]
    lo = [min(p, q) for p, q in zip(a, b)]
    hi = [max(p, q) for p, q in zip(a, b)]
    if hi[direction] - lo[direction] <= 0:
        raise ValueError("Feed must span a nonzero gap along its excitation direction")
    transverse = [k for k in range(3) if k != direction]
    if any(hi[k] != lo[k] for k in transverse):
        raise ValueError("Initial driven adapter expects an ideal line feed with explicit FEM width")
    width_axis = transverse[0]
    lo[width_axis] -= feed_width_mm / 2
    hi[width_axis] += feed_width_mm / 2
    impedance = float(evaluate(port.get("R", 50), names))
    if not math.isfinite(impedance) or impedance <= 0 or port.get("X"):
        raise ValueError("Initial driven adapter needs a positive real reference impedance")
    sheets, boxes = [], []
    for part in resolve_parts(design, names):
        original = design["parts"][part["index"]]
        if original.get("transforms") or original.get("cuts") or part.get("voids"):
            raise ValueError("Initial driven adapter supports untransformed boxes and sheets")
        material = part["material"]
        metal = material["kind"] == "metal"
        if not metal and material["kind"] != "dielectric":
            raise ValueError("Only PEC and isotropic dielectric materials are supported")
        allowed = {"name", "kind", "label", "color", "opacity", "library", "description"}
        if not metal:
            allowed |= {"eps_r", "mu_r", "tan_d", "tan_d_freq"}
        if set(material) - allowed:
            raise ValueError("Unsupported material properties must not be silently discarded")
        eps = float(evaluate(material.get("eps_r", 1), names))
        mu = float(evaluate(material.get("mu_r", 1), names))
        loss = float(evaluate(material.get("tan_d", 0), names))
        if loss and "tan_d_freq" not in material:
            raise ValueError("Lossy dielectric needs an explicit tan_d_freq reference in GHz")
        ref = float(evaluate(material.get("tan_d_freq", 1), names)) * 1e9
        if not all(math.isfinite(v) for v in (eps, mu, loss, ref)) or min(eps, mu, ref) <= 0 or loss < 0:
            raise ValueError("Invalid dielectric properties")
        for p in part["prims"]:
            if p["kind"] != "box" or p.get("_matrix"):
                raise ValueError("Initial driven adapter supports axis-aligned boxes and PEC sheets")
            low = [min(s, t) for s, t in zip(p["start"], p["stop"])]
            high = [max(s, t) for s, t in zip(p["start"], p["stop"])]
            flat = [k for k in range(3) if high[k] == low[k]]
            if metal:
                if len(flat) != 1:
                    raise ValueError("Initial driven metal geometry must be a PEC sheet")
                sheets.append((low, high, flat[0]))
            else:
                if flat:
                    raise ValueError("Dielectric geometry must have volume")
                boxes.append((low, high, eps, mu, loss))
    if not boxes or not sheets:
        raise ValueError("Driven patch prototype requires dielectric volumes and PEC sheets")
    for endpoint in (a, b):
        if not any(n == direction and abs(endpoint[n] - left[n]) < 1e-9 and all(
                left[q] <= lo[q] and hi[q] <= right[q] for q in range(3) if q != n) for left, right, n in sheets):
            raise ValueError("Both ends of the finite feed must contact PEC sheets across its full width")
    if any(n == direction and lo[n] < left[n] < hi[n] and all(left[q] <= a[q] <= right[q] for q in range(3) if q != n)
           for left, right, n in sheets):
        raise ValueError("A PEC sheet crosses the feed gap")
    for i, first in enumerate(boxes):
        for second in boxes[i + 1:]:
            if all(min(first[1][k], second[1][k]) - max(first[0][k], second[0][k]) > 1e-9 for k in range(3)):
                raise ValueError("Overlapping dielectric volumes are unsupported")
    solids = [(q[0], q[1]) for q in boxes] + [(q[0], q[1]) for q in sheets] + [(lo, hi)]
    air_lo = [min(s[0][k] for s in solids) - padding_mm for k in range(3)]
    air_hi = [max(s[1][k] for s in solids) + padding_mm for k in range(3)]
    f_min, f_max = float(settings["f_min_hz"]), float(settings["f_max_hz"])
    fraction = RESOLUTIONS[settings["resolution"]]
    volume = math.prod((air_hi[k] - air_lo[k]) * 1e-3 for k in range(3))
    cells = volume / (C0 / f_max * fraction) ** 3
    if cells > MAX_RESOURCE_CELLS:
        raise ValueError(f"Domain too large for the EMerge prototype (about {cells:.0f} cells, "
                         f"limit {MAX_RESOURCE_CELLS}); reduce padding or use coarse resolution")
    limitations = [
        "Finite rectangular feed replaces ideal line only in this FEM run.",
        "Absorbing outer boundary on all six faces; mesh and padding convergence are not certified.",
        "No far field in this run.",
    ]
    if any(q[4] for q in boxes):
        limitations.append("Constant loss tangent; Elmer maps tan_d to a conductivity at tan_d_freq.")
    if pec_approximations:
        limitations.append("Finite conductor loss omitted by PEC approximation: "
                           + ", ".join(map(str, pec_approximations)))
    return {
        "kind": "design",
        "boxes": [{"lo": _mm(q[0]), "hi": _mm(q[1]), "eps_r": q[2], "mu_r": q[3], "tan_d": q[4]} for q in boxes],
        "sheets": [{"lo": _mm(q[0]), "hi": _mm(q[1]), "normal_axis": q[2]} for q in sheets],
        "port": {"lo": _mm(lo), "hi": _mm(hi), "direction_axis": direction,
                 "sign": 1 if b[direction] > a[direction] else -1,
                 "width": feed_width_mm * 1e-3, "height": (hi[direction] - lo[direction]) * 1e-3,
                 "z0": impedance},
        "air": {"lo": _mm(air_lo), "hi": _mm(air_hi)},
        "frequencies_hz": _frequencies(f_min, f_max, settings["points"]),
        "resolution": fraction,
        "resolution_name": settings["resolution"],
        "phasor_convention_out": PHASOR_CONVENTION,
        "limitations": limitations,
        "pec_approximations": pec_approximations,
    }
