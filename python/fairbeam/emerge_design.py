"""Admission of a bounded Design subset for the experimental EMerge driven ports.

Turns an admitted Design plus run settings into a neutral, metre-based case dictionary.
It follows the admission rules of ``elmer_driven.prepare`` (not its mesher), widened to
``1…N_MAX`` rectangular lumped ports, and never imports ``emerge``, ``gmsh`` or ``emsutil``:
those belong to the separate worker process only.
Anything outside the admitted subset raises ``ValueError``; nothing is dropped or coerced,
apart from the explicit, user-accepted ``approximate_metals`` (force PEC) and finite feed width.
Finite-conductivity metal sheets keep ``conductivity`` / sheet thickness for EMerge
``ThinConductor`` unless the user opts into PEC approximation.
"""
import copy
import math

from .design import _given, check_design, design_params, resolve_names, resolve_parts, evaluate
from .emerge_limits import N_MAX
from .emerge_port_map import resolve
from .model import resolve_params

C0 = 299792458.0
PHASOR_CONVENTION = "exp(+i omega t)"
# Same default as ``simulation.SHEET_THICKNESS_MM`` (avoid importing CSXCAD via simulation).
SHEET_THICKNESS_MM = 0.035
RESOLUTIONS = {"coarse": 0.25, "fine": 0.15}  # wavelength fractions at f_max (frozen Task 5)
MAX_RESOURCE_CELLS = 200000  # tetrahedron-count proxy (frozen Task 5)
_REQUIRED = ("analysis", "accept_finite_feed", "feed_width_mm", "padding_mm", "resolution",
             "f_min_hz", "f_max_hz", "points")
_ALLOWED = frozenset(_REQUIRED) | {"approximate_metals"}
_PORT_KEYS = {"type", "number", "R", "start", "stop", "direction", "excite", "priority", "name", "label"}
_METAL_KEYS = frozenset({"name", "kind", "label", "color", "opacity", "library", "description",
                         "conductivity", "thickness"})
_DIEL_KEYS = frozenset({"name", "kind", "label", "color", "opacity", "library", "description",
                        "eps_r", "mu_r", "tan_d", "tan_d_freq"})


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


def sheet_conductor(material, names):
    """Return ``(conductivity_S_per_m, thickness_m)`` or ``(None, None)`` for PEC.

    Matches openEMS ``design.metal_loss``: empty conductivity is PEC; missing thickness uses
    ``SHEET_THICKNESS_MM`` (0.035 mm). Used by driven and planar admission for ThinConductor.
    """
    if not _given(material.get("conductivity")):
        return None, None
    sigma = float(evaluate(material["conductivity"], names))
    if not math.isfinite(sigma) or sigma <= 0:
        raise ValueError("Metal conductivity must be > 0 S/m (leave empty for PEC)")
    if _given(material.get("thickness")):
        thick_mm = float(evaluate(material["thickness"], names))
    else:
        thick_mm = float(SHEET_THICKNESS_MM)
    if not math.isfinite(thick_mm) or thick_mm <= 0:
        raise ValueError("Metal sheet thickness must be > 0 mm")
    return sigma, thick_mm * 1e-3


def _settings(settings):
    if not isinstance(settings, dict):
        raise ValueError("Settings must be an object")
    if set(settings) - _ALLOWED:
        raise ValueError("Unsupported settings must not be silently discarded: "
                         + ", ".join(sorted(map(str, set(settings) - _ALLOWED))))
    missing = [k for k in _REQUIRED if k not in settings]
    if missing:
        raise ValueError("Missing settings: " + ", ".join(missing))
    if settings["analysis"] != "emerge_nport" or settings["accept_finite_feed"] is not True:
        raise ValueError("Explicit experimental finite-feed acceptance is required")
    feed_width = _positive(settings["feed_width_mm"], "Finite feed width")
    padding = _positive(settings["padding_mm"], "Padding")
    _resolution_fraction(settings["resolution"])  # validate early
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


def _admit_driven_ports(ports):
    """Validate driven port count / types / numbers. Returns sorted ports (1…N)."""
    n = len(ports)
    if n < 1 or n > N_MAX:
        raise ValueError(
            f"Driven EMerge needs 1 to {N_MAX} rectangular lumped ports "
            f"(got {n})")
    if any(p.get("type", "lumped") != "lumped" for p in ports):
        raise ValueError("Driven EMerge needs all ports to be rectangular lumped ports")
    numbers = []
    for port in ports:
        number = port.get("number")
        if type(number) is not int:
            raise ValueError("Driven EMerge port numbers must be integers 1…N")
        numbers.append(number)
    if set(numbers) != set(range(1, n + 1)):
        raise ValueError(
            f"Driven EMerge needs contiguous port numbers 1…{n}")
    return sorted(ports, key=lambda p: p["number"])


def _driven_feed(port, names, feed_width_mm, settings):
    """Map one driven lumped feed to a finite rectangular plate (mm lo/hi + meta)."""
    mapped = resolve(port, path="driven", settings=settings)
    if not mapped["ok"]:
        raise ValueError(mapped["error"])
    if port.get("excite", True) is False:
        raise ValueError("Every driven port must be excited")
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
    return {
        "number": int(port["number"]),
        "a": a,
        "b": b,
        "lo": lo,
        "hi": hi,
        "direction": direction,
        "impedance": impedance,
        "mapped": mapped,
        "design_port_type": port.get("type", "lumped"),
    }


def _check_feed_contacts_sheets(feed, sheets):
    direction, a, lo, hi = feed["direction"], feed["a"], feed["lo"], feed["hi"]
    for endpoint in (feed["a"], feed["b"]):
        if not any(n == direction and abs(endpoint[n] - left[n]) < 1e-9 and all(
                left[q] <= lo[q] and hi[q] <= right[q] for q in range(3) if q != n)
                   for left, right, n, _sigma, _thick in sheets):
            raise ValueError("Both ends of the finite feed must contact metal sheets across its full width")
    if any(n == direction and lo[n] < left[n] < hi[n] and all(left[q] <= a[q] <= right[q] for q in range(3) if q != n)
           for left, right, n, _sigma, _thick in sheets):
        raise ValueError("A metal sheet crosses the feed gap")


def admit(design, settings):
    """Return the neutral EMerge case for ``design`` or raise ``ValueError``."""
    feed_width_mm, padding_mm = _settings(settings)
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
        raise ValueError("Additional lumped elements are not yet supported by driven EMerge")
    ports = _admit_driven_ports(design.get("ports", []))
    feeds = [_driven_feed(port, names, feed_width_mm, settings) for port in ports]
    sheets, boxes = [], []
    lossy_sheet_names = []
    for part in resolve_parts(design, names):
        original = design["parts"][part["index"]]
        if original.get("transforms") or original.get("cuts") or part.get("voids"):
            raise ValueError("Initial driven adapter supports untransformed boxes and sheets")
        material = part["material"]
        metal = material["kind"] == "metal"
        if not metal and material["kind"] != "dielectric":
            raise ValueError("Only metal and isotropic dielectric materials are supported")
        allowed = _METAL_KEYS if metal else _DIEL_KEYS
        if set(material) - allowed:
            raise ValueError("Unsupported material properties must not be silently discarded")
        sigma, thickness_m = (None, None)
        if metal:
            sigma, thickness_m = sheet_conductor(material, names)
            if sigma is not None:
                lossy_sheet_names.append(material.get("name"))
        else:
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
                raise ValueError("Initial driven adapter supports axis-aligned boxes and metal sheets")
            low = [min(s, t) for s, t in zip(p["start"], p["stop"])]
            high = [max(s, t) for s, t in zip(p["start"], p["stop"])]
            flat = [k for k in range(3) if high[k] == low[k]]
            if metal:
                if len(flat) != 1:
                    raise ValueError("Initial driven metal geometry must be a sheet (zero thickness on one axis)")
                sheets.append((low, high, flat[0], sigma, thickness_m))
            else:
                if flat:
                    raise ValueError("Dielectric geometry must have volume")
                boxes.append((low, high, eps, mu, loss))
    if not boxes or not sheets:
        raise ValueError("Driven patch prototype requires dielectric volumes and metal sheets")
    for feed in feeds:
        _check_feed_contacts_sheets(feed, sheets)
    for i, first in enumerate(boxes):
        for second in boxes[i + 1:]:
            if all(min(first[1][k], second[1][k]) - max(first[0][k], second[0][k]) > 1e-9 for k in range(3)):
                raise ValueError("Overlapping dielectric volumes are unsupported")
    solids = [(q[0], q[1]) for q in boxes] + [(q[0], q[1]) for q in sheets] + [
        (feed["lo"], feed["hi"]) for feed in feeds]
    air_lo = [min(s[0][k] for s in solids) - padding_mm for k in range(3)]
    air_hi = [max(s[1][k] for s in solids) + padding_mm for k in range(3)]
    f_min, f_max = float(settings["f_min_hz"]), float(settings["f_max_hz"])
    fraction, resolution_name = _resolution_fraction(settings["resolution"])
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
    elif lossy_sheet_names:
        limitations.append(
            "Conductor loss on metal sheets via EMerge ThinConductor (σ and sheet thickness); "
            "surface roughness is not modelled: "
            + ", ".join(map(str, dict.fromkeys(lossy_sheet_names))))
    sheet_dicts = []
    for low, high, normal, sigma, thickness_m in sheets:
        entry = {"lo": _mm(low), "hi": _mm(high), "normal_axis": normal}
        if sigma is not None:
            entry["conductivity"] = float(sigma)
            entry["thickness_m"] = float(thickness_m)
        sheet_dicts.append(entry)
    port_dicts = []
    for feed in feeds:
        lo, hi, direction, b, a = feed["lo"], feed["hi"], feed["direction"], feed["b"], feed["a"]
        mapped = feed["mapped"]
        port_dicts.append({
            "number": feed["number"],
            "lo": _mm(lo), "hi": _mm(hi), "direction_axis": direction,
            "sign": 1 if b[direction] > a[direction] else -1,
            "width": feed_width_mm * 1e-3, "height": (hi[direction] - lo[direction]) * 1e-3,
            "z0": feed["impedance"],
            "design_port_type": feed["design_port_type"],
            "mapped_bc": mapped["mapped_bc"],
            "approximations": list(mapped["approximations"]),
            "accept_used": list(mapped["accept_used"]),
        })
    return {
        "kind": "design",
        "boxes": [{"lo": _mm(q[0]), "hi": _mm(q[1]), "eps_r": q[2], "mu_r": q[3], "tan_d": q[4]} for q in boxes],
        "sheets": sheet_dicts,
        "ports": port_dicts,
        # Singular ``port`` kept for driven result schema / bundle until emerge-result/2 (B3 Task 3).
        "port": port_dicts[0],
        "air": {"lo": _mm(air_lo), "hi": _mm(air_hi)},
        "frequencies_hz": _frequencies(f_min, f_max, settings["points"]),
        "resolution": fraction,
        "resolution_name": resolution_name,
        "phasor_convention_out": PHASOR_CONVENTION,
        "limitations": limitations,
        "pec_approximations": pec_approximations,
    }
