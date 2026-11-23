"""Shared soft limits for experimental EMerge Design admission."""
import math

N_MAX = 8
# Post-solve E cut samples (same spirit as openEMS FIELD_PLANE_FREQS_MAX); not a re-FEM.
FIELD_CUT_FREQS_MAX = 4


def field_cut_frequencies_hz_from_settings(settings):
    """Optional ``field_cut_frequencies_hz`` → validated Hz list, or ``None`` if absent.

    Empty list is allowed (worker keeps auto one frequency). Bad values raise ``ValueError``
    — never silently dropped. Cap is ``FIELD_CUT_FREQS_MAX``.
    """
    if not isinstance(settings, dict) or "field_cut_frequencies_hz" not in settings:
        return None
    raw = settings["field_cut_frequencies_hz"]
    if not isinstance(raw, list):
        raise ValueError("field_cut_frequencies_hz must be a list")
    if len(raw) > FIELD_CUT_FREQS_MAX:
        raise ValueError(
            f"field_cut_frequencies_hz supports at most {FIELD_CUT_FREQS_MAX} frequencies")
    out = []
    for value in raw:
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value <= 0):
            raise ValueError("field_cut_frequencies_hz entries must be positive finite Hz")
        out.append(float(value))
    return out
