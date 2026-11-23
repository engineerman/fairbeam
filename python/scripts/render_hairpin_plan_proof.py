"""Plan-view PNG from resolved Fairbeam design primitives (same path as openEMS build).

Not part of CI — run after hairpin layout changes to produce visual proof.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "python") not in sys.path:
    sys.path.insert(0, str(REPO / "python"))

from fairbeam.design import build, check_design, resolve_names, resolve_primitive  # noqa: E402
from fairbeam.filter_synthesis.hairpin_microstrip_bp import (  # noqa: E402
    HairpinMicrostripBpSpec,
    synthesize_hairpin_microstrip_bp,
)

# Staggered y_in before hairpin_align_u_baseline (order-3 defaults).
STAGGER_Y_IN = [-7.441410042553192, -4.096166808510639, 0.0, 4.277026382978724]


def _top_metal_xy(rects: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    if not rects:
        return (0.0, 0.0, 1.0, 1.0)
    xs = [r[0] for r in rects] + [r[1] for r in rects]
    ys = [r[2] for r in rects] + [r[3] for r in rects]
    return (min(xs), min(ys), max(xs), max(ys))


def resolved_filter_metal_xy(
    design: dict,
    *,
    value_overrides: dict[str, float] | None = None,
) -> tuple[list[tuple[float, float, float, float]], dict[str, float], int]:
    """Microstrip top-metal (z = h) rectangles for the filter part."""
    check_design(design)
    names = resolve_names(design, {k: float(v) for k, v in (value_overrides or {}).items()})
    z_metal = float(names["h"])
    filter_part = next(p for p in design["parts"] if p.get("name") == "filter")
    rects: list[tuple[float, float, float, float]] = []
    n_boxes = 0
    for j, pr in enumerate(filter_part.get("primitives", [])):
        if pr.get("kind") != "box":
            continue
        rp = resolve_primitive(pr, names, f"filter.primitives[{j}]", 10)
        a, c = rp["start"], rp["stop"]
        n_boxes += 1
        if abs(a[2] - c[2]) > 1e-9:
            continue
        if abs(a[2] - z_metal) > 1e-6:
            continue
        rects.append(
            (
                min(a[0], c[0]),
                max(a[0], c[0]),
                min(a[1], c[1]),
                max(a[1], c[1]),
            )
        )
    y_ins = [
        float(names[k])
        for k in sorted(names)
        if k.startswith("y_in")
    ]
    return rects, names, len(filter_part.get("primitives", []))


def _draw_metal(ax, rects: list[tuple[float, float, float, float]], *, title: str) -> None:
    for xmin, xmax, ymin, ymax in rects:
        ax.add_patch(
            mpatches.Rectangle(
                (xmin, ymin),
                xmax - xmin,
                ymax - ymin,
                facecolor="#d97706",
                edgecolor="#92400e",
                linewidth=0.6,
            )
        )
    x0, y0, x1, y1 = _top_metal_xy(rects)
    pad = 3.0
    ax.set_xlim(x0 - pad, x1 + pad)
    ax.set_ylim(y0 - pad, y1 + pad)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, alpha=0.25, linewidth=0.5)
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.set_title(title, fontsize=10)


def main() -> int:
    spec = HairpinMicrostripBpSpec(f0_hz=2e9, order=3, bw_hz=0.2e9)
    result = synthesize_hairpin_microstrip_bp(spec)
    design = result.design

    stagger_override = {f"y_in{i}": v for i, v in enumerate(STAGGER_Y_IN)}
    rects_before, _, n_prim = resolved_filter_metal_xy(design, value_overrides=stagger_override)
    rects_after, names_after, _ = resolved_filter_metal_xy(design)

    d_build = dict(design)
    d_build["far_field"] = {"enabled": False}
    d_build.pop("monitors", None)
    sim = build(d_build, {})
    if sim.fdtd is None:
        raise RuntimeError("build() did not return an FDTD object")

    out_dir = REPO / "docs" / "agent" / "media"
    out_dir.mkdir(parents=True, exist_ok=True)
    png_path = out_dir / "hairpin-u-baseline-proof.png"
    json_path = REPO / "python" / "models" / "_proof_hairpin_u_baseline.design.json"

    y_after = sorted(float(names_after[k]) for k in names_after if k.startswith("y_in"))
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5))
    _draw_metal(
        axes[0],
        rects_before,
        title=(
            f"Before (overridden y_in): {len(rects_before)} top-metal sheets, "
            f"{n_prim} filter primitives — staggered open ends"
        ),
    )
    _draw_metal(
        axes[1],
        rects_after,
        title=(
            f"After (synthesis defaults): {len(rects_after)} top-metal sheets at z=h={names_after['h']:.2f} mm; "
            f"y_in all {y_after[0]:.3f} mm · build() OK"
        ),
    )
    fig.suptitle(
        "Hairpin microstrip BP — resolved filter boxes (fairbeam.design.resolve_primitive → openEMS build)",
        fontsize=11,
    )
    fig.tight_layout()
    fig.savefig(png_path, dpi=160, bbox_inches="tight")
    plt.close(fig)

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(design, indent=2), encoding="utf-8")

    print(f"wrote {png_path}")
    print(f"wrote {json_path}")
    print(f"filter primitives: {n_prim} boxes, top-metal sheets drawn: {len(rects_after)}")
    print(f"y_in after (resolved): {y_after}")
    print(f"first resonator leg box (after): {rects_after[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
