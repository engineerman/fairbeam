"""Unified EMerge N-port Design admission (classify driven, planar, stripline, coax).

Single entry for ``analysis: "emerge_nport"``. Classifies into ``geometry_kind``
``driven_lumped``, ``planar_microstrip``, ``stripline``, or ``coaxial_tem``, then reuses
``emerge_design`` / ``emerge_planar`` / ``emerge_stripline`` / ``emerge_coax`` builders.
Worker ``kind`` stays ``design`` | ``planar`` | ``stripline`` | ``coax``.

Never imports ``emerge``, ``gmsh`` or ``emsutil``.
"""
from .emerge_coax import admit as admit_coax
from .emerge_design import admit as admit_driven
from .emerge_limits import N_MAX
from .emerge_planar import admit as admit_planar
from .emerge_stripline import admit as admit_stripline

ANALYSIS = "emerge_nport"
GEOMETRY_DRIVEN = "driven_lumped"
GEOMETRY_PLANAR = "planar_microstrip"
GEOMETRY_COAX = "coaxial_tem"
GEOMETRY_STRIPLINE = "stripline"
GEOMETRY_KINDS = (GEOMETRY_DRIVEN, GEOMETRY_PLANAR, GEOMETRY_COAX, GEOMETRY_STRIPLINE)
# Client / job analysis tokens that bind a Design to the EMerge experimental path.
EMERGE_DESIGN_ANALYSES = frozenset({ANALYSIS})

# Child admits reject unknown keys; filter the unified settings surface per path.
_DRIVEN_KEYS = frozenset({
    "analysis", "accept_finite_feed", "feed_width_mm", "padding_mm", "resolution",
    "f_min_hz", "f_max_hz", "points", "approximate_metals", "field_cut_frequencies_hz",
})
_PLANAR_KEYS = frozenset({
    "analysis", "enclosure", "air_height_mm", "resolution", "f_min_hz", "f_max_hz",
    "points", "approximate_metals", "padding_mm", "refine_conductor_edges",
    "accept_lumped_terminals", "accept_modal_ports", "accept_finite_feed",
    "field_cut_frequencies_hz",
})
_COAX_KEYS = frozenset({
    "analysis", "accept_coaxial_tem", "padding_mm", "resolution",
    "f_min_hz", "f_max_hz", "points", "field_cut_frequencies_hz",
})
_STRIPLINE_KEYS = frozenset({
    "analysis", "accept_finite_feed", "padding_mm", "resolution", "f_min_hz", "f_max_hz",
    "points", "approximate_metals", "refine_conductor_edges", "field_cut_frequencies_hz",
})
# The Run dialog sends these. The stripline child rejects unknown keys.
_STRIPLINE_DROPPED = ("enclosure", "air_height_mm", "feed_width_mm")


def _port_types(design):
    if not isinstance(design, dict):
        raise ValueError("Design must be an object")
    ports = design.get("ports")
    if not isinstance(ports, list):
        raise ValueError("Design ports must be a list")
    return [p.get("type", "lumped") if isinstance(p, dict) else None for p in ports]


def _child_settings(settings, allowed):
    out = {key: settings[key] for key in allowed if key in settings}
    out["analysis"] = ANALYSIS
    # Unified Run may send driven padding alongside shielded planar enclosure.
    # Planar admit rejects padding_mm unless enclosure is open; strip so classify
    # can still try planar before driven fallback.
    if out.get("enclosure") == "shielded":
        out.pop("padding_mm", None)
    return out


def _stripline_child_settings(settings):
    child = _child_settings(settings, _STRIPLINE_KEYS)
    for key in _STRIPLINE_DROPPED:
        child.pop(key, None)
    return child


def _stamp(case, geometry_kind):
    out = dict(case)
    out["analysis"] = ANALYSIS
    out["geometry_kind"] = geometry_kind
    return out


def admit_geometry(design, settings, geometry_kind):
    """Admit ``design`` forcing ``geometry_kind`` (bundle re-admit / tests)."""
    if geometry_kind not in GEOMETRY_KINDS:
        raise ValueError(
            "geometry_kind must be driven_lumped, planar_microstrip, coaxial_tem, or stripline")
    if not isinstance(settings, dict):
        raise ValueError("Settings must be an object")
    if geometry_kind == GEOMETRY_PLANAR:
        case = admit_planar(design, _child_settings(settings, _PLANAR_KEYS))
    elif geometry_kind == GEOMETRY_COAX:
        case = admit_coax(design, _child_settings(settings, _COAX_KEYS))
    elif geometry_kind == GEOMETRY_STRIPLINE:
        case = admit_stripline(design, _stripline_child_settings(settings))
    else:
        case = admit_driven(design, _child_settings(settings, _DRIVEN_KEYS))
    return _stamp(case, geometry_kind)


def admit(design, settings):
    """Classify and admit a Design for experimental EMerge N-port, or raise ``ValueError``.

    Returns a case with worker ``kind`` ``design``|``planar``|``stripline``|``coax``, plus
    ``analysis`` ``emerge_nport`` and ``geometry_kind``. Soft port bound is ``N_MAX``
    (via child admits).
    """
    if not isinstance(settings, dict):
        raise ValueError("Settings must be an object")
    analysis = settings.get("analysis")
    if analysis not in EMERGE_DESIGN_ANALYSES:
        raise ValueError("EMerge Design analysis must be emerge_nport")

    # Classify per Shared facts (coax-only when all coaxial; else planar before driven).
    types = _port_types(design)
    if not types:
        raise ValueError(f"EMerge needs 1 to {N_MAX} ports")
    if any(t is None for t in types):
        raise ValueError("Each Design port must be an object")
    unique = set(types)
    if len(unique) > 1:
        raise ValueError(
            "Mixed port types are rejected; use all lumped, all microstrip, all cpw, "
            f"or all coaxial (got {sorted(unique)})")
    homogeneous = next(iter(unique))

    if homogeneous == "coaxial":
        return admit_geometry(design, settings, GEOMETRY_COAX)

    # Classic CPW uses the planar worker (geometry_kind stays planar_microstrip).
    # All-lumped tries planar, then the stripline sandwich, then the driven feed.
    try_planar = homogeneous in ("microstrip", "lumped", "cpw")
    try_stripline = homogeneous == "lumped"
    try_driven = homogeneous == "lumped"

    planar_err = stripline_err = driven_err = None
    if try_planar:
        try:
            return admit_geometry(design, settings, GEOMETRY_PLANAR)
        except ValueError as exc:
            planar_err = str(exc)
    if try_stripline:
        try:
            return admit_geometry(design, settings, GEOMETRY_STRIPLINE)
        except ValueError as exc:
            stripline_err = str(exc)
    if try_driven:
        try:
            return admit_geometry(design, settings, GEOMETRY_DRIVEN)
        except ValueError as exc:
            driven_err = str(exc)

    parts = []
    if try_planar:
        parts.append(f"planar_microstrip: {planar_err}")
    else:
        parts.append(
            "planar_microstrip: ports must be all microstrip, all lumped, or all cpw")
    if try_stripline:
        parts.append(f"stripline: {stripline_err}")
    else:
        parts.append("stripline: ports must be all lumped")
    if try_driven:
        parts.append(f"driven_lumped: {driven_err}")
    else:
        parts.append("driven_lumped: ports must be all lumped")
    parts.append("coaxial_tem: ports must be all coaxial")
    raise ValueError(
        "Design does not match an admitted EMerge geometry class ("
        + "; ".join(parts) + ")")
