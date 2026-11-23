"""2D geometry preview polylines for the filter designer (top view)."""

from __future__ import annotations

from typing import Any

from fairbeam.filter_synthesis.hairpin_bp_common import hairpin_u_x_layout


def _finite_bbox(points: list[tuple[float, float]]) -> list[float]:
    if not points:
        return [0.0, 0.0, 1.0, 1.0]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]


def hairpin_bp_geometry_sketch(
    *,
    x_feed0: float,
    x_end: float,
    feed_len: float,
    feed_centres: list[float],
    w_feed: float,
    sections: list[dict[str, Any]],
    quarter_mm: float,
    inter_spacing_mm: list[float] | None = None,
    tap_from_fold_mm: float | None = None,
    port1_label: str = "1",
    port2_label: str = "2",
) -> dict[str, Any]:
    """Top-view sketch of alternating hairpin U resonators with tapped feeds."""
    elements: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    points: list[tuple[float, float]] = []

    px0 = x_feed0
    px1 = x_end + feed_len
    for yc in feed_centres:
        points.extend(
            [
                (px0, yc - w_feed / 2),
                (px0, yc + w_feed / 2),
                (px1, yc - w_feed / 2),
                (px1, yc + w_feed / 2),
            ]
        )

    elements.append(
        {
            "kind": "port",
            "from": [x_feed0, feed_centres[0]],
            "to": [x_feed0, feed_centres[0]],
            "label": port1_label,
        }
    )
    elements.append(
        {
            "kind": "port",
            "from": [x_end + feed_len, feed_centres[1]],
            "to": [x_end + feed_len, feed_centres[1]],
            "label": port2_label,
        }
    )
    labels.append({"at": [x_feed0, feed_centres[0] + w_feed], "text": port1_label, "unit": ""})
    labels.append({"at": [x_end + feed_len, feed_centres[1] + w_feed], "text": port2_label, "unit": ""})

    x_bases, _ = hairpin_u_x_layout(sections, inter_spacing_mm)
    for k, sec in enumerate(sections):
        x0 = float(x_bases[k])
        w = float(sec["width_mm"])
        gap = float(sec["gap_mm"])
        open_down = bool(sec.get("open_down", k % 2 == 0))
        span_x = 2.0 * w + gap
        x_left = x0 + w / 2.0
        x_right = x0 + w + gap + w / 2.0
        if open_down:
            y_open, y_fold = 0.0, quarter_mm - w / 2.0
            y_leg_end = quarter_mm - w
        else:
            y_open, y_fold = quarter_mm, w / 2.0
            y_leg_end = w
        for x, y in (
            (x_left, y_open),
            (x_left, y_leg_end),
            (x_right, y_open),
            (x_right, y_leg_end),
            (x0, y_fold),
            (x0 + span_x, y_fold),
        ):
            points.append((x, y))
        elements.append({"kind": "segment", "from": [x_left, min(y_open, y_leg_end)], "to": [x_left, max(y_open, y_leg_end)], "width": w})
        elements.append({"kind": "segment", "from": [x_right, min(y_open, y_leg_end)], "to": [x_right, max(y_open, y_leg_end)], "width": w})
        elements.append({"kind": "segment", "from": [x0, y_fold], "to": [x0 + span_x, y_fold], "width": w})
        labels.append({"at": [x0 + gap / 2 + w, quarter_mm * 0.35], "text": f"{gap:.3g}", "unit": "mm"})

    elements.append(
        {"kind": "segment", "from": [x_feed0, feed_centres[0]], "to": [0, feed_centres[0]], "width": w_feed}
    )
    elements.append(
        {
            "kind": "segment",
            "from": [x_end, feed_centres[1]],
            "to": [x_end + feed_len, feed_centres[1]],
            "width": w_feed,
        }
    )
    if tap_from_fold_mm is not None and sections:
        open_down0 = bool(sections[0].get("open_down", True))
        fold_y = quarter_mm if open_down0 else 0.0
        labels.append(
            {
                "at": [float(x_bases[0]) + float(sections[0]["width_mm"]), (fold_y + feed_centres[0]) / 2.0],
                "text": f"t={tap_from_fold_mm:.3g}",
                "unit": "mm",
            }
        )

    return {"unit": "mm", "elements": elements, "labels": labels, "bbox": _finite_bbox(points)}


def stepped_microstrip_lp_geometry_sketch(
    *,
    feed_len: float,
    x_end: float,
    w_feed: float,
    sections: list[dict[str, Any]],
) -> dict[str, Any]:
    """Top-view stepped-impedance line segments along +x (centerline at y=0)."""
    elements: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    points: list[tuple[float, float]] = [(0.0, 0.0), (x_end, 0.0)]

    elements.append({"kind": "port", "from": [0.0, 0.0], "to": [0.0, 0.0], "label": "1"})
    elements.append({"kind": "port", "from": [x_end, 0.0], "to": [x_end, 0.0], "label": "2"})

    x = feed_len
    elements.append({"kind": "segment", "from": [0.0, 0.0], "to": [feed_len, 0.0], "width": w_feed})
    for k, sec in enumerate(sections):
        length = float(sec["length"])
        width = float(sec["width"])
        x1 = x + length
        elements.append({"kind": "segment", "from": [x, 0.0], "to": [x1, 0.0], "width": width})
        labels.append({"at": [x + length * 0.5, width * 0.6], "text": f"{length:.3g}", "unit": "mm"})
        points.extend([(x, 0.0), (x1, 0.0)])
        x = x1
    elements.append({"kind": "segment", "from": [x, 0.0], "to": [x_end, 0.0], "width": w_feed})

    return {"unit": "mm", "elements": elements, "labels": labels, "bbox": _finite_bbox(points)}


def coupled_line_bp_geometry_sketch(
    *,
    x_start: float,
    x_end: float,
    centres: list[float],
    widths: list[float],
    gaps: list[float],
    w_feed: float,
) -> dict[str, Any]:
    """Coupled-line bandpass: two parallel microstrip rails in the top view."""
    elements: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    points: list[tuple[float, float]] = []

    elements.append({"kind": "port", "from": [x_start, 0.0], "to": [x_start, 0.0], "label": "1"})
    elements.append({"kind": "port", "from": [x_end, 0.0], "to": [x_end, 0.0], "label": "2"})

    for k, yc in enumerate(centres):
        w = widths[k] if k < len(widths) else w_feed
        gap = gaps[k] if k < len(gaps) else 0.3
        y_lo = yc - gap / 2 - w / 2
        y_hi = yc + gap / 2 + w / 2
        elements.append({"kind": "segment", "from": [x_start, y_lo], "to": [x_end, y_lo], "width": w})
        elements.append({"kind": "segment", "from": [x_start, y_hi], "to": [x_end, y_hi], "width": w})
        points.extend([(x_start, y_lo), (x_end, y_hi)])
        labels.append({"at": [x_start + (x_end - x_start) * 0.4, yc], "text": f"{gap:.3g}", "unit": "mm"})

    return {"unit": "mm", "elements": elements, "labels": labels, "bbox": _finite_bbox(points)}
