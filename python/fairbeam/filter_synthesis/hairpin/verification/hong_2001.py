"""Hong & Lancaster 2001 hairpin example vs the closed-form builder.

Source: Jia-Sheng Hong and M. J. Lancaster, *Microstrip Filters for RF/Microwave
Applications*, Wiley, 2001, section 5.2.3 and Figure 5.14. The figure is a
five-pole hairpin on 1.27 mm substrate, relative permittivity 6.15. The text
gives f0 = 2 GHz, fractional bandwidth 0.2, 0.1 dB Chebyshev, Qe = 5.734,
and equation (5.26) evaluated at L = 20.4 mm, Zr = 68.3 ohm, t = 6.03 mm.
The drawn layout (Figure 5.14) uses EM-curve gaps and a shortened input arm.

This module only calls the existing closed-form path. It does not change it.
The arm separation of 2.0 mm is an input the builder accepts; a zero difference
on that row is not a prediction.
"""

from __future__ import annotations

from fairbeam.analytic import microstrip_width
from fairbeam.filter_synthesis.hairpin_bp_common import hong_tap_from_fold_mm
from fairbeam.filter_synthesis.hairpin_microstrip_bp import (
    HairpinMicrostripBpSpec,
    synthesize_hairpin_microstrip_bp,
)

# Figure 5.14 and the paragraph that evaluates equation (5.26).
PUBLISHED = {
    "f0_hz": 2e9,
    "bw_hz": 0.4e9,
    "order": 5,
    "ripple_db": 0.1,
    "z0": 50.0,
    "eps_r": 6.15,
    "h_mm": 1.27,
    "intra_gap_mm": 2.0,
    "q_len_text_mm": 20.4,
    "arm_drawn_mm": 18.4,
    "resonator_width_mm": 1.0,
    "resonator_zr_ohm": 68.3,
    "feed_width_mm": 1.85,
    "tap_closed_form_mm": 6.03,
    "tap_em_mm": 7.625,
    "gap_outer_mm": 0.4,
    "gap_inner_mm": 0.6,
    "qe": 5.734,
}


def closed_form_dimensions() -> dict[str, float]:
    """Geometry from the same call the wizard uses for a closed-form hairpin."""
    spec = HairpinMicrostripBpSpec(
        f0_hz=PUBLISHED["f0_hz"],
        order=PUBLISHED["order"],
        bw_hz=PUBLISHED["bw_hz"],
        ripple_db=PUBLISHED["ripple_db"],
        response="chebyshev",
        z0=PUBLISHED["z0"],
        eps_r=PUBLISHED["eps_r"],
        h_mm=PUBLISHED["h_mm"],
        tan_d=0.0,
        intra_gap_mm=PUBLISHED["intra_gap_mm"],
    )
    result = synthesize_hairpin_microstrip_bp(spec)
    return {row["key"]: float(row["value"]) for row in result.dimensions}


def _row(name: str, published: float, designed: float, note: str) -> dict:
    delta = designed - published
    pct = 100.0 * delta / published if published else float("nan")
    return {
        "name": name,
        "published_mm": published,
        "designed_mm": designed,
        "delta_mm": delta,
        "delta_pct": pct,
        "note": note,
    }


def comparison_rows(dims: dict[str, float] | None = None) -> list[dict]:
    """One row per published length. Designed values come from the closed-form builder."""
    dims = closed_form_dimensions() if dims is None else dims
    book = PUBLISHED
    formula = hong_tap_from_fold_mm(
        book["q_len_text_mm"], book["qe"], book["z0"], zr=book["resonator_zr_ohm"]
    )
    width_at_zr = float(microstrip_width(book["resonator_zr_ohm"], book["eps_r"], book["h_mm"]))
    return [
        _row(
            "quarter-wave length vs text L",
            book["q_len_text_mm"],
            dims["q_len"],
            "Text L is λg/4 of the 1 mm arm. The builder uses the 50 ohm line.",
        ),
        _row(
            "quarter-wave length vs drawn arm",
            book["arm_drawn_mm"],
            dims["q_len"],
            "Figure 5.14 labels the input arm 18.4 mm after the book shortens the end resonators.",
        ),
        _row(
            "resonator width",
            book["resonator_width_mm"],
            dims["w0"],
            "Hong chose a 68.3 ohm, 1 mm arm. The builder sets every arm to the 50 ohm width.",
        ),
        _row(
            "50 ohm feed width",
            book["feed_width_mm"],
            dims["w_feed"],
            "Both are the 50 ohm line on this substrate.",
        ),
        _row(
            "U arm gap",
            book["intra_gap_mm"],
            dims["gap0"],
            "Passed in as intra_gap_mm. The builder does not compute this gap.",
        ),
        _row(
            "tap vs equation (5.26) as printed",
            book["tap_closed_form_mm"],
            dims["tap_from_fold"],
            "The builder uses its own length and Zr = Z0, not Hong's L and Zr.",
        ),
        _row(
            "tap vs EM curve",
            book["tap_em_mm"],
            dims["tap_from_fold"],
            "7.625 mm is the full-wave tap in the text, not a closed-form result.",
        ),
        _row(
            "outer coupling gap",
            book["gap_outer_mm"],
            dims["sp0"],
            "0.4 mm is read from Hong's EM coupling curve. The builder uses even/odd spacing.",
        ),
        _row(
            "inner coupling gap",
            book["gap_inner_mm"],
            dims["sp1"],
            "0.6 mm is the inner EM gap. sp1 and sp2 are the mirrored closed-form spacings.",
        ),
        _row(
            "equation (5.26) with Hong's L, Zr, Qe",
            book["tap_closed_form_mm"],
            formula,
            "Same helper the builder calls, fed the book's own L, Zr, and Qe.",
        ),
        _row(
            "line width at Hong's Zr",
            book["resonator_width_mm"],
            width_at_zr,
            "microstrip_width at 68.3 ohm. Not what the hairpin layout requests.",
        ),
    ]


def format_report(rows: list[dict] | None = None) -> str:
    rows = comparison_rows() if rows is None else rows
    lines = [
        "Hong & Lancaster 2001, Fig. 5.14, closed-form builder",
        f"{'parameter':<42} {'published':>10} {'designed':>10} {'delta mm':>10} {'delta %':>9}",
    ]
    for row in rows:
        lines.append(
            f"{row['name']:<42} {row['published_mm']:10.3f} {row['designed_mm']:10.3f} "
            f"{row['delta_mm']:+10.3f} {row['delta_pct']:+8.1f}%"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_report())
