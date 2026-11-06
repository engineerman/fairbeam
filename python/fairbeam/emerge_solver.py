"""Unified EMerge N-port Design admission (classify driven vs planar).

Single entry for ``analysis: "emerge_nport"``. Classifies into ``geometry_kind``
``driven_lumped`` or ``planar_microstrip``, then reuses ``emerge_design`` /
``emerge_planar`` builders. Worker ``kind`` stays ``design`` | ``planar``.

Never imports ``emerge``, ``gmsh`` or ``emsutil``.
"""
from .emerge_design import admit as admit_driven
from .emerge_limits import N_MAX
from .emerge_planar import admit as admit_planar

ANALYSIS = "emerge_nport"
GEOMETRY_DRIVEN = "driven_lumped"
GEOMETRY_PLANAR = "planar_microstrip"
GEOMETRY_KINDS = (GEOMETRY_DRIVEN, GEOMETRY_PLANAR)
# Client / job analysis tokens that bind a Design to the EMerge experimental path.
EMERGE_DESIGN_ANALYSES = frozenset({ANALYSIS})

# Child admits reject unknown keys; filter the unified settings surface per path.
_DRIVEN_KEYS = frozenset({
    "analysis", "accept_finite_feed", "feed_width_mm", "padding_mm", "resolution",
    "f_min_hz", "f_max_hz", "points", "approximate_metals",
})
_PLANAR_KEYS = frozenset({
    "analysis", "enclosure", "air_height_mm", "resolution", "f_min_hz", "f_max_hz",
    "points", "approximate_metals", "padding_mm", "refine_conductor_edges",
    "accept_lumped_terminals", "accept_finite_feed",
})


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


def _stamp(case, geometry_kind):
    out = dict(case)
    out["analysis"] = ANALYSIS
    out["geometry_kind"] = geometry_kind
    return out


def admit_geometry(design, settings, geometry_kind):
    """Admit ``design`` forcing ``geometry_kind`` (bundle re-admit / tests)."""
    if geometry_kind not in GEOMETRY_KINDS:
        raise ValueError("geometry_kind must be driven_lumped or planar_microstrip")
    if not isinstance(settings, dict):
        raise ValueError("Settings must be an object")
    if geometry_kind == GEOMETRY_PLANAR:
        case = admit_planar(design, _child_settings(settings, _PLANAR_KEYS))
    else:
        case = admit_driven(design, _child_settings(settings, _DRIVEN_KEYS))
    return _stamp(case, geometry_kind)


def admit(design, settings):
    """Classify and admit a Design for experimental EMerge N-port, or raise ``ValueError``.

    Returns a case with worker ``kind`` ``design``|``planar``, plus ``analysis``
    ``emerge_nport`` and ``geometry_kind``. Soft port bound is ``N_MAX`` (via child admits).
    """
    if not isinstance(settings, dict):
        raise ValueError("Settings must be an object")
    analysis = settings.get("analysis")
    if analysis not in EMERGE_DESIGN_ANALYSES:
        raise ValueError("EMerge Design analysis must be emerge_nport")

    # Classify per Shared facts (planar before driven when both plausible).
    types = _port_types(design)
    if not types:
        raise ValueError(f"EMerge needs 1 to {N_MAX} ports")
    if any(t is None for t in types):
        raise ValueError("Each Design port must be an object")
    unique = set(types)
    if len(unique) > 1:
        raise ValueError(
            "Mixed port types are rejected; use all lumped or all microstrip "
            f"(got {sorted(unique)})")
    homogeneous = next(iter(unique))
    try_planar = homogeneous in ("microstrip", "lumped")
    try_driven = homogeneous == "lumped"

    planar_err = driven_err = None
    if try_planar:
        try:
            return admit_geometry(design, settings, GEOMETRY_PLANAR)
        except ValueError as exc:
            planar_err = str(exc)
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
            "planar_microstrip: ports must be all microstrip or all lumped")
    if try_driven:
        parts.append(f"driven_lumped: {driven_err}")
    else:
        parts.append("driven_lumped: ports must be all lumped")
    raise ValueError(
        "Design does not match an admitted EMerge geometry class ("
        + "; ".join(parts) + ")")
