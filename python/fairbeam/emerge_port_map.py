"""Stage A–C openEMS → EMerge port mapping matrix (adapter-side policy only).

Design JSON ports stay openEMS-shaped. ``resolve`` records which EMerge BC a path may use
and which ``accept_*`` flags / approximation strings apply. Admission modules call this;
the worker applies BCs from case geometry and must not invent mapping policy.

Stage A: driven lumped, planar microstrip/lumped, fixture rectangular WG.
Stage B: coax path maps Design ``coaxial`` → analytic ``CoaxPort`` TEM (constant εr fill).
Stage C: planar microstrip or classic CPW may map to ``WavePort`` when
``accept_modal_ports`` is set (modal wins over lumped). CPW also maps to
``LumpedPort`` when only ``accept_lumped_terminals`` is set. Grounded CPW
(geometry) is rejected later in planar admit, not here. Non-planar paths
still reject CPW.

This module never imports ``emerge``, ``numpy``, ``gmsh`` or ``emsutil``.
"""

PATHS = frozenset({"driven", "planar", "fixture", "coax"})
MAPPED_LUMPED = "LumpedPort"
MAPPED_WAVE = "WavePort"
MAPPED_RECT_WG = "RectangularWaveguide"
MAPPED_COAX = "CoaxPort"

# Frozen approximation strings (Stage A–C Shared facts). Do not invent synonyms here.
APPROX_DRIVEN_LUMPED = "finite-width lumped feed plate"
APPROX_PLANAR_MICROSTRIP = (
    "microstrip → lumped strip-to-ground terminal; feed_shift/measurement_shift unused"
)
APPROX_PLANAR_MICROSTRIP_MODAL = (
    "microstrip → WavePort at board-edge face; feed_shift/measurement_shift unused"
)
APPROX_PLANAR_CPW = (
    "cpw → lumped gap terminal at board-edge face; feed_shift/measurement_shift unused"
)
APPROX_PLANAR_CPW_MODAL = (
    "cpw → WavePort at board-edge CPW aperture; feed_shift/measurement_shift unused"
)
APPROX_PLANAR_LUMPED = "planar discrete → LumpedPort plate at board-edge face"
APPROX_FIXTURE_WG = "fixture RectangularWaveguide TE10"
APPROX_COAX_TEM = "Design coaxial → analytic CoaxPort TEM; constant εr fill"

# Fixture path may pass type "waveguide" or this sentinel (documented for Level A WR-90).
FIXTURE_WAVEGUIDE_SENTINEL = "fixture_rectangular_waveguide"


def _fail(error):
    return {
        "ok": False,
        "mapped_bc": None,
        "accept_used": [],
        "approximations": [],
        "error": error,
    }


def _ok(mapped_bc, accept_used, approximations):
    return {
        "ok": True,
        "mapped_bc": mapped_bc,
        "accept_used": list(accept_used),
        "approximations": list(approximations),
        "error": None,
    }


def _port_type(port):
    if not isinstance(port, dict):
        return None
    if port.get("type") == FIXTURE_WAVEGUIDE_SENTINEL:
        return "waveguide"
    return port.get("type", "lumped")


def _is_tm_waveguide(port):
    """Reject TM on Design/fixture waveguide dicts (Open point: TM stays out of Design admit)."""
    if not isinstance(port, dict):
        return False
    mode = port.get("mode", "TE10")
    if isinstance(mode, str) and mode.upper().startswith("TM"):
        return True
    mode_type = port.get("mode_type")
    if isinstance(mode_type, str) and mode_type.upper() == "TM":
        return True
    return False


def resolve(port, *, path, settings):
    """Map one Design (or fixture) port for an EMerge experimental path.

    Returns a dict with keys ``ok``, ``mapped_bc``, ``accept_used``, ``approximations``,
    ``error``. Paths: driven lumped, planar microstrip/CPW (lumped or WavePort), planar
    discrete lumped, coax coaxial→CoaxPort, and fixture rectangular WG.
    """
    if path not in PATHS:
        return _fail(f"Unknown EMerge port-map path: {path!r}")
    if not isinstance(settings, dict):
        return _fail("Settings must be an object")
    if not isinstance(port, dict):
        return _fail("Port must be an object")

    if "group" in port:
        return _fail("EMerge does not support lumped port groups")

    ptype = _port_type(port)
    if ptype is None:
        return _fail("Port type is required")

    if ptype == "waveguide" and _is_tm_waveguide(port):
        return _fail("EMerge rejects TM waveguide modes on Design ports (TE only for fixture)")

    if path == "driven":
        if ptype == "coaxial":
            return _fail("EMerge does not yet support coaxial ports")
        if ptype == "microstrip":
            return _fail("Driven EMerge path does not admit microstrip ports")
        if ptype == "cpw":
            return _fail("Driven EMerge path does not admit CPW ports")
        if ptype == "waveguide":
            return _fail("Driven EMerge does not admit Design waveguide ports")
        if ptype != "lumped":
            return _fail(f"Driven EMerge does not map port type {ptype!r}")
        if settings.get("accept_finite_feed") is not True:
            return _fail("Explicit experimental finite-feed acceptance is required")
        return _ok(MAPPED_LUMPED, ["accept_finite_feed"], [APPROX_DRIVEN_LUMPED])

    if path == "planar":
        if ptype == "coaxial":
            return _fail("EMerge does not yet support coaxial ports")
        if ptype == "waveguide":
            return _fail("Planar EMerge does not admit Design waveguide ports")
        if ptype == "lumped":
            if settings.get("accept_finite_feed") is not True:
                return _fail("Explicit experimental finite-feed acceptance is required")
            return _ok(MAPPED_LUMPED, ["accept_finite_feed"], [APPROX_PLANAR_LUMPED])
        if ptype == "microstrip":
            if settings.get("accept_modal_ports") is True:
                return _ok(MAPPED_WAVE, ["accept_modal_ports"], [APPROX_PLANAR_MICROSTRIP_MODAL])
            if settings.get("accept_lumped_terminals") is True:
                return _ok(MAPPED_LUMPED, ["accept_lumped_terminals"], [APPROX_PLANAR_MICROSTRIP])
            return _fail(
                "Explicit accept_modal_ports (WavePort) or accept_lumped_terminals "
                "(LumpedPort) is required for planar microstrip EMerge"
            )
        if ptype == "cpw":
            if settings.get("accept_modal_ports") is True:
                return _ok(MAPPED_WAVE, ["accept_modal_ports"], [APPROX_PLANAR_CPW_MODAL])
            if settings.get("accept_lumped_terminals") is True:
                return _ok(MAPPED_LUMPED, ["accept_lumped_terminals"], [APPROX_PLANAR_CPW])
            return _fail(
                "Explicit accept_modal_ports (WavePort) or accept_lumped_terminals "
                "(LumpedPort) is required for planar CPW EMerge"
            )
        return _fail(f"Planar EMerge does not map port type {ptype!r}")

    if path == "coax":
        if ptype != "coaxial":
            return _fail(f"Coax EMerge does not map port type {ptype!r}")
        if settings.get("accept_coaxial_tem") is not True:
            return _fail("Explicit accept_coaxial_tem is required for coax EMerge")
        return _ok(MAPPED_COAX, ["accept_coaxial_tem"], [APPROX_COAX_TEM])

    # path == "fixture"
    if ptype == "coaxial":
        return _fail("EMerge does not yet support coaxial ports")
    if ptype != "waveguide":
        return _fail("Fixture EMerge path maps rectangular waveguide only")
    return _ok(MAPPED_RECT_WG, [], [APPROX_FIXTURE_WG])
