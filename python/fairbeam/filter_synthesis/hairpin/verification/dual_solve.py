"""Dual-solver S for Hong 2001 Fig. 5.14 vs the closed-form builder.

Builds two N=5 designs on the book stack (eps_r=6.15, h=1.27 mm, f0=2 GHz,
FBW=20%), then runs EMerge and openEMS one process at a time.

  published  — Figure 5.14 EM layout millimeters (uniform q_len = drawn arm)
  builder    — synthesize_hairpin_microstrip_bp with the same electrical inputs

Raw output (gitignored): .sim/hairpin-hong-2001-verification/

Usage (from python/, with OPENEMS_INSTALL_PATH set):

  python -m fairbeam.filter_synthesis.hairpin.verification.dual_solve build
  python -m fairbeam.filter_synthesis.hairpin.verification.dual_solve emerge published
  python -m fairbeam.filter_synthesis.hairpin.verification.dual_solve openems published
  python -m fairbeam.filter_synthesis.hairpin.verification.dual_solve emerge builder
  python -m fairbeam.filter_synthesis.hairpin.verification.dual_solve openems builder
  python -m fairbeam.filter_synthesis.hairpin.verification.dual_solve plot
  python -m fairbeam.filter_synthesis.hairpin.verification.dual_solve all
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
SIM = REPO / ".sim" / "hairpin-hong-2001-verification"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "python"))

os.environ.setdefault(
    "OPENEMS_INSTALL_PATH",
    r"C:\Users\ee\AppData\Local\org.fairbeam.desktop\runtime\openEMS",
)

from fairbeam.filter_synthesis.hairpin.verification.hong_2001 import (  # noqa: E402
    PUBLISHED,
    closed_form_dimensions,
)
from fairbeam.filter_synthesis.hairpin_edc import set_independent  # noqa: E402
from fairbeam.filter_synthesis.hairpin_microstrip_bp import (  # noqa: E402
    HairpinMicrostripBpSpec,
    synthesize_hairpin_microstrip_bp,
)

F0 = 2.0
FEED_LEN_MM = 8.0
BOARD_MARGIN_MM = 6.0
TAN_D = 0.0027  # RT/duroid 6006-class; same on both layouts
N_FREQ = 81

# Figure 5.14 full-wave layout (one shared q_len = drawn input arm).
PUBLISHED_LAYOUT = {
    "q_len": PUBLISHED["arm_drawn_mm"],
    "w": PUBLISHED["resonator_width_mm"],
    "w_feed": PUBLISHED["feed_width_mm"],
    "tap_from_fold": PUBLISHED["tap_em_mm"],
    "gap": PUBLISHED["intra_gap_mm"],
    "sp": [
        PUBLISHED["gap_outer_mm"],
        PUBLISHED["gap_inner_mm"],
        PUBLISHED["gap_inner_mm"],
        PUBLISHED["gap_outer_mm"],
    ],
}

EMERGE_SETTINGS = {
    "analysis": "emerge_nport",
    "accept_lumped_terminals": True,
    "enclosure": "shielded",
    "air_height_mm": 8.0,
    "resolution": "coarse",
    "f_min_hz": 1.40e9,
    "f_max_hz": 2.60e9,
    "points": 25,
    "approximate_metals": True,
}

CASES = ("published", "builder")


def _seed_spec(*, design_id: str, design_name: str) -> HairpinMicrostripBpSpec:
    return HairpinMicrostripBpSpec(
        f0_hz=PUBLISHED["f0_hz"],
        order=PUBLISHED["order"],
        bw_hz=PUBLISHED["bw_hz"],
        ripple_db=PUBLISHED["ripple_db"],
        response="chebyshev",
        z0=PUBLISHED["z0"],
        eps_r=PUBLISHED["eps_r"],
        h_mm=PUBLISHED["h_mm"],
        tan_d=TAN_D,
        feed_len_mm=FEED_LEN_MM,
        board_margin_mm=BOARD_MARGIN_MM,
        intra_gap_mm=PUBLISHED["intra_gap_mm"],
        design_id=design_id,
        design_name=design_name,
    )


def _apply_sim_band(design: dict) -> None:
    design["simulation"]["f_min"] = "f0-1.5*bw"
    design["simulation"]["f_max"] = "f0+1.5*bw"
    design["simulation"]["max_timesteps"] = 250_000
    design["simulation"]["end_criteria_db"] = -40
    design["far_field"] = {"enabled": False}
    design.pop("monitors", None)


def builder_design() -> tuple[dict, dict[str, float]]:
    result = synthesize_hairpin_microstrip_bp(
        _seed_spec(design_id="hong-2001-builder", design_name="Hong 2001 closed-form builder")
    )
    design = result.design
    _apply_sim_band(design)
    dims = {row["key"]: float(row["value"]) for row in result.dimensions}
    return design, dims


def published_design() -> tuple[dict, dict[str, float]]:
    """Clone the builder Design JSON, then force Figure 5.14 millimeters."""
    design, _ = builder_design()
    design = copy.deepcopy(design)
    design["model"]["id"] = "hong-2001-published"
    design["model"]["name"] = "Hong 2001 Fig. 5.14 published layout"
    order = int(PUBLISHED["order"])
    set_independent(design, "q_len", PUBLISHED_LAYOUT["q_len"])
    set_independent(design, "w_feed", PUBLISHED_LAYOUT["w_feed"])
    set_independent(design, "tap_from_fold", PUBLISHED_LAYOUT["tap_from_fold"])
    for k in range(order):
        set_independent(design, f"w{k}", PUBLISHED_LAYOUT["w"])
        set_independent(design, f"gap{k}", PUBLISHED_LAYOUT["gap"])
    for k, sp in enumerate(PUBLISHED_LAYOUT["sp"]):
        set_independent(design, f"sp{k}", sp)
    dims = {
        "q_len": PUBLISHED_LAYOUT["q_len"],
        "w_feed": PUBLISHED_LAYOUT["w_feed"],
        "tap_from_fold": PUBLISHED_LAYOUT["tap_from_fold"],
        **{f"w{k}": PUBLISHED_LAYOUT["w"] for k in range(order)},
        **{f"gap{k}": PUBLISHED_LAYOUT["gap"] for k in range(order)},
        **{f"sp{k}": float(sp) for k, sp in enumerate(PUBLISHED_LAYOUT["sp"])},
    }
    return design, dims


def case_dir(name: str) -> Path:
    return SIM / name


def build() -> None:
    SIM.mkdir(parents=True, exist_ok=True)
    makers = {
        "published": published_design,
        "builder": builder_design,
    }
    for name, maker in makers.items():
        design, dims = maker()
        out = case_dir(name)
        out.mkdir(parents=True, exist_ok=True)
        (out / "design.json").write_text(json.dumps(design, indent=2), encoding="utf-8")
        (out / "dimensions.json").write_text(
            json.dumps([{"key": k, "value": v} for k, v in sorted(dims.items())], indent=2),
            encoding="utf-8",
        )
        print(f"{name}: wrote {out / 'design.json'}", flush=True)
        print(f"  dims { {k: round(v, 4) for k, v in sorted(dims.items())} }", flush=True)
    # Geometry-only table for the README (no EM yet).
    geom = {
        "published": PUBLISHED_LAYOUT,
        "builder": closed_form_dimensions(),
        "stack": {
            "eps_r": PUBLISHED["eps_r"],
            "h_mm": PUBLISHED["h_mm"],
            "tan_d": TAN_D,
            "f0_hz": PUBLISHED["f0_hz"],
            "bw_hz": PUBLISHED["bw_hz"],
            "order": PUBLISHED["order"],
            "ripple_db": PUBLISHED["ripple_db"],
        },
        "note": (
            "Published uses one shared q_len = drawn arm 18.4 mm; the book shortens "
            "I/O resonators relative to text L = 20.4 mm. Builder arms are all 50 ohm."
        ),
    }
    (SIM / "geometry.json").write_text(json.dumps(geom, indent=2), encoding="utf-8")
    print("wrote", SIM / "geometry.json", flush=True)


def emerge(name: str) -> None:
    from fairbeam import emerge_runtime, research
    from fairbeam.research import encode

    out = case_dir(name)
    design = json.loads((out / "design.json").read_text(encoding="utf-8"))
    run_dir = out / "emerge"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    research_dir = run_dir / "research"
    spec = research.prepare(
        {
            "backend": "emerge",
            "path": str(emerge_runtime.python()),
            "design": design,
            "settings": EMERGE_SETTINGS,
        }
    )
    snap_dir = run_dir / "input"
    snap_dir.mkdir(parents=True, exist_ok=True)
    raw = encode(spec)
    snap = snap_dir / "research.json"
    snap.write_bytes(raw)
    checksum = hashlib.sha256(raw).hexdigest()
    print(f"{name}: emerge admit ok; launching worker…", flush=True)
    research.execute(snap, research_dir, checksum)
    result = json.loads((research_dir / "result.json").read_text(encoding="utf-8"))
    print(f"{name}: status {result.get('status')}", flush=True)
    summarize_emerge(result, out)
    if result.get("status") != "results_exported":
        raise SystemExit(f"{name}: EMerge status {result.get('status')}")


def summarize_emerge(result: dict, out: Path) -> None:
    freq = result["frequency_hz"]
    s = result["s"]
    rows = []
    for i, f in enumerate(freq):

        def mag_db(key: str, i: int = i) -> float:
            z = complex(s[key]["re"][i], s[key]["im"][i])
            return 20 * math.log10(max(abs(z), 1e-30))

        rows.append(
            {
                "f_GHz": f / 1e9,
                "S11_dB": mag_db("1,1"),
                "S21_dB": mag_db("1,2"),
                "S12_dB": mag_db("2,1"),
                "S22_dB": mag_db("2,2"),
            }
        )
    summary = {
        "backend": "emerge",
        "status": result["status"],
        "elapsed_seconds": result["elapsed_seconds"],
        "mesh_nodes": result["mesh"]["nodes"],
        "mesh_tets": result["mesh"]["tetrahedra"],
        "settings": result.get("settings"),
        "rows": rows,
    }
    (out / "emerge_s_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"{'f_GHz':>8} {'S11':>8} {'S21':>8}")
    for row in rows:
        if abs(row["f_GHz"] - 2.0) < 0.06 or abs(row["f_GHz"] - 1.8) < 0.06 or abs(row["f_GHz"] - 2.2) < 0.06:
            print(f"{row['f_GHz']:8.4f} {row['S11_dB']:8.2f} {row['S21_dB']:8.2f}")
    print(
        "elapsed",
        round(summary["elapsed_seconds"], 1),
        "s; nodes",
        summary["mesh_nodes"],
        "tets",
        summary["mesh_tets"],
        flush=True,
    )


def openems(name: str) -> None:
    from fairbeam.design import build
    from fairbeam.multiport import assemble_s
    import numpy as np

    out = case_dir(name)
    design = json.loads((out / "design.json").read_text(encoding="utf-8"))
    design = copy.deepcopy(design)
    _apply_sim_band(design)
    run_dir = out / "openems_direct"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    n_ports = len(design["ports"])
    sims = []
    for excite_n in range(1, n_ports + 1):
        d = json.loads(json.dumps(design))
        for p in d["ports"]:
            p["excite"] = int(p["number"]) == excite_n
        sim = build(d, {})
        path = run_dir / f"excite-{excite_n}"
        path.mkdir(parents=True)
        print(f"{name}: exciting port {excite_n}/{n_ports} …", flush=True)
        # Prefer GPU; fall back to multithread if the runtime pack has no GPU engine.
        try:
            stats = sim.run(str(path), threads=4, echo=False, engine="gpu", exact=False)
        except Exception as exc:  # noqa: BLE001 — record and retry CPU
            print(f"{name}: gpu failed ({exc}); retrying multithread", flush=True)
            stats = sim.run(str(path), threads=4, echo=False, engine="multithread", exact=False)
        print(
            "  timesteps",
            stats.get("timesteps"),
            "wall",
            stats.get("wall_time_s"),
            "converged",
            stats.get("converged"),
            "energy_db",
            stats.get("final_energy_db"),
            "grid",
            stats.get("grid"),
            flush=True,
        )
        sim.evaluate(n_freq=N_FREQ)
        sims.append((excite_n, sim, stats))

    primary = sims[0][1]
    f = np.asarray(primary.results["frequency"])
    a = np.zeros((len(sims), n_ports, len(f)), complex)
    b = np.zeros_like(a)
    for k, (pn, sim, _stats) in enumerate(sims):
        for i, p in enumerate(sim._port_objs):
            zr = np.sqrt(np.real(np.asarray(p.Z_ref, dtype=complex)))
            a[k, i] = np.asarray(p.uf_inc) / zr
            b[k, i] = np.asarray(p.uf_ref) / zr
    s = assemble_s(a, b, [pn for pn, _, _ in sims], n_ports)
    rows = []
    for i, fi in enumerate(f):
        s11 = s[i, 0, 0]
        s21 = s[i, 1, 0]
        s12 = s[i, 0, 1]
        s22 = s[i, 1, 1]
        rows.append(
            {
                "f_GHz": float(fi) / 1e9,
                "S11_dB": 20.0 * math.log10(max(abs(s11), 1e-30)),
                "S21_dB": 20.0 * math.log10(max(abs(s21), 1e-30)),
                "S12_dB": 20.0 * math.log10(max(abs(s12), 1e-30)),
                "S22_dB": 20.0 * math.log10(max(abs(s22), 1e-30)),
            }
        )
    grid = sims[0][2].get("grid")
    cells = int(np.prod(grid)) if grid else None
    summary = {
        "backend": "openems",
        "engine": sims[0][2].get("engine"),
        "wall_time_s": sum(float(st.get("wall_time_s") or 0) for _, _, st in sims),
        "timesteps": [st.get("timesteps") for _, _, st in sims],
        "converged": [st.get("converged") for _, _, st in sims],
        "final_energy_db": [st.get("final_energy_db") for _, _, st in sims],
        "grid": grid,
        "cells": cells,
        "n_freq": N_FREQ,
        "rows": rows,
    }
    (run_dir / "openems_s_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"{name}: wrote {run_dir / 'openems_s_summary.json'}", flush=True)
    print(f"{'f_GHz':>8} {'S11':>8} {'S21':>8}")
    for row in rows:
        ghz = row["f_GHz"]
        if abs(ghz - 2.0) <= 0.02 or abs(ghz - 1.8) <= 0.02 or abs(ghz - 2.2) <= 0.02:
            print(f"{ghz:8.4f} {row['S11_dB']:8.2f} {row['S21_dB']:8.2f}")


def _nearest(rows: list[dict], f0: float) -> dict:
    return min(rows, key=lambda r: abs(r["f_GHz"] - f0))


def _load_case(name: str) -> tuple[dict, dict, dict[str, float]]:
    out = case_dir(name)
    em = json.loads((out / "emerge_s_summary.json").read_text(encoding="utf-8"))
    om = json.loads((out / "openems_direct" / "openems_s_summary.json").read_text(encoding="utf-8"))
    dims = {d["key"]: float(d["value"]) for d in json.loads((out / "dimensions.json").read_text(encoding="utf-8"))}
    return em, om, dims


def plot() -> None:
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.2), dpi=140, sharey=True)
    titles = {
        "published": "Hong Fig. 5.14 published layout",
        "builder": "Closed-form builder",
    }
    highlights: dict[str, dict] = {}
    for ax, name in zip(axes, CASES):
        em, om, _dims = _load_case(name)
        em_f = [r["f_GHz"] for r in em["rows"]]
        om_f = [r["f_GHz"] for r in om["rows"]]
        ax.plot(em_f, [r["S11_dB"] for r in em["rows"]], "o-", color="#1f6feb", label="EMerge |S11|", ms=4)
        ax.plot(em_f, [r["S21_dB"] for r in em["rows"]], "s--", color="#1f6feb", label="EMerge |S21|", ms=4, alpha=0.9)
        ax.plot(om_f, [r["S11_dB"] for r in om["rows"]], "-", color="#c45c26", label="openEMS |S11|", lw=1.5)
        ax.plot(om_f, [r["S21_dB"] for r in om["rows"]], "--", color="#c45c26", label="openEMS |S21|", lw=1.5)
        ax.axvline(F0, color="#666", ls=":", lw=0.9)
        ax.axvspan(1.8, 2.2, color="#1f6feb", alpha=0.06)
        ax.set_xlim(1.4, 2.6)
        ax.set_ylim(-50, 2)
        ax.set_xlabel("f (GHz)")
        ax.set_title(titles[name])
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, ncol=2, loc="lower left")
        e2 = _nearest(em["rows"], 2.0)
        o2 = _nearest(om["rows"], 2.0)
        e18 = _nearest(em["rows"], 1.8)
        o18 = _nearest(om["rows"], 1.8)
        e22 = _nearest(em["rows"], 2.2)
        o22 = _nearest(om["rows"], 2.2)
        highlights[name] = {
            "emerge": {
                "at_1p8": e18,
                "at_2p0": e2,
                "at_2p2": e22,
                "elapsed_seconds": em.get("elapsed_seconds"),
                "mesh_nodes": em.get("mesh_nodes"),
                "mesh_tets": em.get("mesh_tets"),
                "status": em.get("status"),
            },
            "openems": {
                "at_1p8": o18,
                "at_2p0": o2,
                "at_2p2": o22,
                "wall_time_s": om.get("wall_time_s"),
                "cells": om.get("cells"),
                "grid": om.get("grid"),
                "converged": om.get("converged"),
                "final_energy_db": om.get("final_energy_db"),
                "engine": om.get("engine"),
            },
        }
        print(
            f"{name} @2.00 GHz: EMerge S11={e2['S11_dB']:.2f} S21={e2['S21_dB']:.2f} | "
            f"openEMS S11={o2['S11_dB']:.2f} S21={o2['S21_dB']:.2f}",
            flush=True,
        )
    axes[0].set_ylabel("|S| (dB)")
    fig.suptitle("Hong & Lancaster 2001 §5.2.3 — published vs closed-form builder", fontsize=11)
    fig.tight_layout()
    png = SIM / "compare_s.png"
    fig.savefig(png, bbox_inches="tight")
    doc = HERE / "compare_s.png"
    doc.write_bytes(png.read_bytes())
    (SIM / "highlights.json").write_text(json.dumps(highlights, indent=2), encoding="utf-8")
    print("wrote", png, flush=True)
    print("wrote", doc, flush=True)
    print("wrote", SIM / "highlights.json", flush=True)


def run_all() -> None:
    build()
    for name in CASES:
        emerge(name)
        openems(name)
    plot()


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "build":
        build()
    elif cmd == "emerge":
        if len(sys.argv) < 3 or sys.argv[2] not in CASES:
            raise SystemExit("usage: dual_solve.py emerge published|builder")
        emerge(sys.argv[2])
    elif cmd == "openems":
        if len(sys.argv) < 3 or sys.argv[2] not in CASES:
            raise SystemExit("usage: dual_solve.py openems published|builder")
        openems(sys.argv[2])
    elif cmd == "plot":
        plot()
    elif cmd == "all":
        run_all()
    else:
        raise SystemExit(
            "usage: dual_solve.py build|emerge <case>|openems <case>|plot|all"
        )


if __name__ == "__main__":
    main()
