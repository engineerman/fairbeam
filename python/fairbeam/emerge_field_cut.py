"""Map an EMerge post-solve E-field cut into Fairbeam ``field_planes``.

The worker stores SI grids (metres, V/m complex) under ``field_cut``. This module does not
import EMerge; it only reshapes that payload into the shared Results ``FieldPlaneMap`` schema
(``fairbeam.field_planes``), with complex ``phasor`` so Magnitude / Phase / Animate (Play) work.
"""
from __future__ import annotations

import math

import numpy as np

from .field_planes import entry, phasor_payload

FIELD_CUT_SCHEMA = "fairbeam.emerge-field-cut/1"
FIELD_CUT_NOTE = (
    "E-field cut is one frequency (harmonic); Play animates phase, not a full-band FDTD time movie."
)


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _grid(re_vals, im_vals, nu, nv, name):
    if (not isinstance(re_vals, list) or not isinstance(im_vals, list)
            or len(re_vals) != nv or len(im_vals) != nv):
        raise ValueError(f"{name} must be {nv} rows")
    out = np.empty((nv, nu), dtype=complex)
    for j, (re_row, im_row) in enumerate(zip(re_vals, im_vals)):
        if (not isinstance(re_row, list) or not isinstance(im_row, list)
                or len(re_row) != nu or len(im_row) != nu
                or not all(map(_number, re_row)) or not all(map(_number, im_row))):
            raise ValueError(f"{name}[{j}] must hold {nu} finite re/im samples")
        out[j] = np.asarray(re_row, dtype=float) + 1j * np.asarray(im_row, dtype=float)
    return out


def validate_field_cut(cut):
    """Structural check of a worker ``field_cut``; returns a cleaned copy."""
    if not isinstance(cut, dict):
        raise ValueError("field_cut must be an object")
    if cut.get("schema") != FIELD_CUT_SCHEMA:
        raise ValueError(f"field_cut.schema must be {FIELD_CUT_SCHEMA}")
    if cut.get("quantity") != "E" or cut.get("component") != "abs" or cut.get("normal") != "z":
        raise ValueError("field_cut must be an absolute E map with normal z")
    if cut.get("axis") != 2:
        raise ValueError("field_cut.axis must be 2 (z-normal)")
    for key in ("position_m", "freq_hz"):
        if not _number(cut.get(key)):
            raise ValueError(f"field_cut.{key} must be a finite number")
    if cut["freq_hz"] <= 0:
        raise ValueError("field_cut.freq_hz must be positive")
    nu, nv = cut.get("nu"), cut.get("nv")
    if type(nu) is not int or type(nv) is not int or nu < 2 or nv < 2:
        raise ValueError("field_cut.nu and nv must be integers >= 2")
    for key in ("u_m", "v_m"):
        span = cut.get(key)
        if (not isinstance(span, list) or len(span) != 2
                or not all(map(_number, span)) or span[1] <= span[0]):
            raise ValueError(f"field_cut.{key} must be [lo, hi] with hi > lo")
    if cut.get("freq_choice") not in ("max_abs_s21", "min_abs_s11", "band_center"):
        raise ValueError("field_cut.freq_choice is unknown")
    port = cut.get("port", 1)
    if type(port) is not int or port < 1:
        raise ValueError("field_cut.port must be a positive integer")
    # Touch grids so bad shapes fail in assess, not only in the bundle.
    _grid(cut.get("ex_re"), cut.get("ex_im"), nu, nv, "ex")
    _grid(cut.get("ey_re"), cut.get("ey_im"), nu, nv, "ey")
    _grid(cut.get("ez_re"), cut.get("ez_im"), nu, nv, "ez")
    return {
        "schema": FIELD_CUT_SCHEMA,
        "quantity": "E", "component": "abs", "normal": "z", "axis": 2,
        "position_m": float(cut["position_m"]), "freq_hz": float(cut["freq_hz"]),
        "freq_choice": cut["freq_choice"], "port": port,
        "u_m": [float(cut["u_m"][0]), float(cut["u_m"][1])],
        "v_m": [float(cut["v_m"][0]), float(cut["v_m"][1])],
        "nu": nu, "nv": nv,
        "ex_re": cut["ex_re"], "ex_im": cut["ex_im"],
        "ey_re": cut["ey_re"], "ey_im": cut["ey_im"],
        "ez_re": cut["ez_re"], "ez_im": cut["ez_im"],
    }


def to_field_plane(cut):
    """Convert a validated ``field_cut`` into one Fairbeam ``field_planes`` entry (drawing units = mm)."""
    cut = validate_field_cut(cut)
    nu, nv = cut["nu"], cut["nv"]
    ex = _grid(cut["ex_re"], cut["ex_im"], nu, nv, "ex")
    ey = _grid(cut["ey_re"], cut["ey_im"], nu, nv, "ey")
    ez = _grid(cut["ez_re"], cut["ez_im"], nu, nv, "ez")
    # Drawing units in Fairbeam designs / emerge_bundle domain are millimetres.
    scale = 1000.0
    pos_mm = float(cut["position_m"]) * scale
    gu = np.linspace(cut["u_m"][0] * scale, cut["u_m"][1] * scale, nu)
    gv = np.linspace(cut["v_m"][0] * scale, cut["v_m"][1] * scale, nv)
    magnitude = np.sqrt(np.abs(ex) ** 2 + np.abs(ey) ** 2 + np.abs(ez) ** 2)
    magnitude = np.where(np.isfinite(magnitude), np.maximum(magnitude, 0.0), 0.0)
    pay = phasor_payload([ex, ey, ez], ["x", "y", "z"])
    pl = {
        "quantity": "E", "component": "abs", "normal": "z",
        "axis": 2, "position": pos_mm, "requested": pos_mm,
    }
    # EMerge FEM cut is not openEMS 1 W incident-normalized; keep unit honest.
    plane = entry(pl, float(cut["freq_hz"]), gu, gv, magnitude, cut["port"],
                  normalized=False, phasor=pay)
    plane["experimental"] = {
        "source": "emerge_cutplane",
        "freq_choice": cut["freq_choice"],
        "note": FIELD_CUT_NOTE,
    }
    return plane
