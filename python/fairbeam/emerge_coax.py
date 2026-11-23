"""Admission of a bounded coaxial Design subset for experimental EMerge.

Turns an admitted all-coaxial Design plus run settings into a neutral, metre-based
``kind: "coax"`` case. Ports are ``1…N_MAX`` homogeneous ``coaxial`` TEM ports with
``accept_coaxial_tem``. Geometry (inner conductor, shield tube, dielectric fill, padded
domain) is synthesised from port radii and materials — Design ``parts`` are not admitted
in this Stage B MVP. Never imports ``emerge``, ``gmsh`` or ``emsutil``.
"""
import copy
import math

from .coax import resolved_coax
from .design import check_design, design_params, evaluate, resolve_names
from .emerge_limits import N_MAX, field_cut_frequencies_hz_from_settings
from .emerge_port_map import resolve
from .model import resolve_params

C0 = 299792458.0
PHASOR_CONVENTION = "exp(+i omega t)"
RESOLUTIONS = {"coarse": 0.25, "fine": 0.15}  # wavelength fractions at f_max
MAX_RESOURCE_CELLS = 200000  # tetrahedron-count proxy (reuse driven surface)
_REQUIRED = ("analysis", "accept_coaxial_tem", "padding_mm", "resolution",
             "f_min_hz", "f_max_hz", "points")
_ALLOWED = frozenset(_REQUIRED) | {"field_cut_frequencies_hz"}
_PORT_KEYS = {
    "type", "number", "mode", "direction", "start", "stop",
    "r_i", "r_o", "r_os", "conductor", "dielectric",
    "feed_shift", "measurement_shift", "termination", "excite",
    "priority", "name", "label",
}


def _positive(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a positive number")
    return float(value)


def _resolution_fraction(value):
    """Named preset → wavelength fraction, or a raw fraction in (0, 0.5]."""
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
        raise ValueError("Coax EMerge analysis must be emerge_nport")
    if settings["accept_coaxial_tem"] is not True:
        raise ValueError("Explicit accept_coaxial_tem is required for coax EMerge")
    padding = _positive(settings["padding_mm"], "Padding")
    _resolution_fraction(settings["resolution"])
    for key in ("f_min_hz", "f_max_hz"):
        v = settings[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 1e6 <= v <= 1e11:
            raise ValueError("Frequency must be between 1 MHz and 100 GHz")
    if not settings["f_min_hz"] < settings["f_max_hz"]:
        raise ValueError("The sweep band must be nonzero: f_min_hz must be below f_max_hz")
    points = settings["points"]
    if type(points) is not int or not 3 <= points <= 21:
        raise ValueError("Initial coax sweep supports 3 to 21 frequency points")
    field_cut_frequencies_hz_from_settings(settings)  # validate early; attach in admit
    return padding


def _frequencies(f_min, f_max, points):
    values = [float(f_min) + (float(f_max) - float(f_min)) * i / (points - 1) for i in range(points)]
    values[-1] = float(f_max)
    return values


def _mm(v):
    return [float(x) * 1e-3 for x in v]


def _admit_coax_ports(ports):
    """Validate coax port count / types / numbers. Returns sorted ports (1…N)."""
    n = len(ports)
    if n < 1 or n > N_MAX:
        raise ValueError(
            f"Coax EMerge needs 1 to {N_MAX} coaxial ports "
            f"(got {n})")
    if any(p.get("type") != "coaxial" for p in ports):
        raise ValueError("Coax EMerge needs all ports to be coaxial")
    numbers = []
    for port in ports:
        number = port.get("number")
        if type(number) is not int:
            raise ValueError("Coax EMerge port numbers must be integers 1…N")
        numbers.append(number)
    if set(numbers) != set(range(1, n + 1)):
        raise ValueError(f"Coax EMerge needs contiguous port numbers 1…{n}")
    return sorted(ports, key=lambda p: p["number"])


def _port_extent_mm(resolved):
    """Axis-aligned bounding box of one coax port in drawing units (mm)."""
    axis = "xyz".index(resolved["direction"])
    a, b = resolved["start"], resolved["stop"]
    r_os = float(resolved["r_os"])
    lo, hi = [], []
    for k in range(3):
        if k == axis:
            lo.append(min(a[k], b[k]))
            hi.append(max(a[k], b[k]))
        else:
            centre = a[k]
            lo.append(centre - r_os)
            hi.append(centre + r_os)
    return lo, hi


def admit(design, settings):
    """Return the neutral coax EMerge case for ``design`` or raise ``ValueError``."""
    padding_mm = _settings(settings)
    check_design(design)
    design = copy.deepcopy(design)
    names = resolve_names(design, resolve_params(design_params(design), {}))

    if design.get("resistors") or design.get("lumped_elements"):
        raise ValueError("Additional lumped elements are not supported by coax EMerge")
    if design.get("parts"):
        raise ValueError(
            "Coax EMerge synthesises geometry from ports only; Design parts are not yet supported")

    ports = _admit_coax_ports(design.get("ports", []))
    materials = design.get("materials", [])

    def num(value, path):
        return float(evaluate(value, names))

    port_dicts = []
    extents = []
    for port in ports:
        mapped = resolve(port, path="coax", settings=settings)
        if not mapped["ok"]:
            raise ValueError(mapped["error"])
        if set(port) - _PORT_KEYS:
            raise ValueError("Unsupported port properties must not be silently discarded")
        if port.get("excite", True) is False:
            raise ValueError("Every coax port must be excited")
        resolved = resolved_coax(port, materials, num)
        axis = "xyz".index(resolved["direction"])
        lo_mm, hi_mm = _port_extent_mm(resolved)
        extents.append((lo_mm, hi_mm))
        port_dicts.append({
            "number": int(port["number"]),
            "start": _mm(resolved["start"]),
            "stop": _mm(resolved["stop"]),
            "direction_axis": axis,
            "r_i": float(resolved["r_i"]) * 1e-3,
            "r_o": float(resolved["r_o"]) * 1e-3,
            "r_os": float(resolved["r_os"]) * 1e-3,
            "er": float(resolved["eps_r"]),
            "mu_r": float(resolved["mu_r"]),
            "tan_d": float(resolved["tan_d"]),
            "design_port_type": "coaxial",
            "mapped_bc": mapped["mapped_bc"],
            "approximations": list(mapped["approximations"]),
            "accept_used": list(mapped["accept_used"]),
        })

    air_lo = [min(e[0][k] for e in extents) - padding_mm for k in range(3)]
    air_hi = [max(e[1][k] for e in extents) + padding_mm for k in range(3)]
    f_min, f_max = float(settings["f_min_hz"]), float(settings["f_max_hz"])
    fraction, resolution_name = _resolution_fraction(settings["resolution"])
    volume = math.prod((air_hi[k] - air_lo[k]) * 1e-3 for k in range(3))
    cells = volume / (C0 / f_max * fraction) ** 3
    if cells > MAX_RESOURCE_CELLS:
        raise ValueError(f"Domain too large for the EMerge prototype (about {cells:.0f} cells, "
                         f"limit {MAX_RESOURCE_CELLS}); reduce padding or use coarse resolution")

    limitations = [
        "Design coaxial → analytic CoaxPort TEM; constant εr fill; experimental, not openEMS-validated.",
        "feed_shift, measurement_shift and termination are unused in this FEM run.",
        "Absorbing outer boundary on the padded domain; mesh and padding convergence are not certified.",
        "No far field in this run.",
    ]
    if any(p["tan_d"] for p in port_dicts):
        limitations.append("Constant loss tangent; frequency dependence is not modelled beyond Design tan_d.")

    case = {
        "kind": "coax",
        "ports": port_dicts,
        "air": {"lo": _mm(air_lo), "hi": _mm(air_hi)},
        "frequencies_hz": _frequencies(f_min, f_max, settings["points"]),
        "resolution": fraction,
        "resolution_name": resolution_name,
        "phasor_convention_out": PHASOR_CONVENTION,
        "limitations": limitations,
        "pec_approximations": [],
    }
    field_cut_hz = field_cut_frequencies_hz_from_settings(settings)
    if field_cut_hz is not None:
        case["field_cut_frequencies_hz"] = field_cut_hz
    return case
