"""Generate local port-map test designs under python/models/ (not for commit)."""
from __future__ import annotations

import json
from pathlib import Path

from fairbeam import starters
from fairbeam.design import blank_design, check_design
from fairbeam.emerge_design import admit as admit_driven
from fairbeam.emerge_planar import admit as admit_planar
from fairbeam.emerge_port_map import resolve

OUT = Path(__file__).resolve().parents[1] / "models"


def write(d: dict) -> None:
    check_design(d)
    path = OUT / f"{d['model']['id']}.design.json"
    path.write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8")
    print("wrote", path.name)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    d = blank_design("portmap_lumped_patch", "Port map · Lumped (patch)")
    d["model"]["description"] = (
        "TEST FIXTURE — one Discrete/lumped port. openEMS: Run as usual. "
        "EMerge: Run → EMerge · Experimental antenna; accept finite feed. "
        "Expected map: lumped → LumpedPort (Stage A)."
    )
    write(d)

    ms = starters.microstrip_design("portmap_microstrip_line", "Port map · Microstrip line")
    ms["model"]["description"] = (
        "TEST FIXTURE — 50 ohm microstrip with two microstrip ports. openEMS: Run as usual. "
        "EMerge: Run → EMerge FEM · Experimental planar two-port; accept lumped terminals. "
        "Expected map: microstrip → LumpedPort strip-to-ground (Stage A)."
    )
    for m in ms["materials"]:
        if m.get("name") == "fr4":
            m["tan_d"] = "0.002"
    ms["ports"] = [
        {
            "type": "microstrip",
            "number": 1,
            "conductor": "copper",
            "direction": "x",
            "excitation_direction": "z",
            "feed_shift": 2,
            "measurement_shift": 5,
            "reference_ohm": 50,
            "termination": "open",
            "excite": True,
            "start": ["-l/2", "-w/2", "h"],
            "stop": ["-l/2 + 10", "w/2", "0"],
        },
        {
            "type": "microstrip",
            "number": 2,
            "conductor": "copper",
            "direction": "x",
            "excitation_direction": "z",
            "feed_shift": 2,
            "measurement_shift": 5,
            "reference_ohm": 50,
            "termination": "open",
            "excite": True,
            "start": ["l/2", "-w/2", "h"],
            "stop": ["l/2 - 10", "w/2", "0"],
        },
    ]
    ms["far_field"] = {"enabled": False}
    write(ms)

    wg = starters.open_waveguide_design("portmap_waveguide_wr90", "Port map · Waveguide WR-90")
    wg["model"]["description"] = (
        "TEST FIXTURE — TE10 waveguide port (WR-90 open end). openEMS: Run as usual. "
        "EMerge Design paths: expect REJECT (Stage A has no Design waveguide admit). "
        "For EMerge waveguide mapping, use Research → WR-90 waveguide fixture instead."
    )
    write(wg)

    coax = {
        "schema": "fairbeam.design/1",
        "model": {
            "id": "portmap_coaxial_air",
            "name": "Port map · Coaxial air line",
            "description": (
                "TEST FIXTURE — coaxial TEM port (air-filled stub). openEMS: CPU experimental coax. "
                "EMerge FEM · Experimental: Stage B coaxial_tem (analytic CoaxPort) with "
                "accept_coaxial_tem; results_exported only — not openEMS-validated."
            ),
        },
        "params": [
            {"key": "f0", "default": 1.5, "label": "Design frequency", "unit": "GHz", "min": 0.1, "max": 10},
        ],
        "simulation": {
            "f_min": "1",
            "f_max": "2",
            "boundaries": ["PEC", "PEC", "PEC", "PEC", "PML_8", "PML_8"],
            "end_criteria_db": -40,
        },
        "materials": [{"name": "PEC", "kind": "metal"}],
        "parts": [],
        "ports": [
            {
                "number": 1,
                "type": "coaxial",
                "mode": "TEM",
                "direction": "z",
                "start": [0, 0, -30],
                "stop": [0, 0, 0],
                "r_i": 1,
                "r_o": 3,
                "r_os": 3.5,
                "conductor": "PEC",
                "dielectric": None,
                "feed_shift": 10,
                "measurement_shift": 20,
                "termination": "open",
                "excite": True,
            }
        ],
        "resistors": [],
        "mesh": {
            "mode": "manual",
            "lines": {
                "x": [round(v * 0.25, 4) for v in range(-16, 17)],
                "y": [round(v * 0.25, 4) for v in range(-16, 17)],
                "z": list(range(-30, 31)),
            },
        },
        "far_field": {"enabled": False},
    }
    write(coax)

    cpw = {
        "schema": "fairbeam.design/1",
        "model": {
            "id": "portmap_cpw_line",
            "name": "Port map · CPW line",
            "description": (
                "TEST FIXTURE — coplanar waveguide with two CPW ports. openEMS: Run as usual. "
                "EMerge classic CPW: admit with accept_modal_ports (WavePort) and/or "
                "accept_lumped_terminals (coplanar gap plate); GCPW not admitted."
            ),
        },
        "params": [
            {"key": "f0", "default": 2.4, "label": "Design frequency", "unit": "GHz", "min": 0.1, "max": 20},
            {"key": "l", "default": 30.0, "label": "Line length", "unit": "mm", "min": 5, "max": 200},
            {"key": "w", "default": 1.5, "label": "Center strip width", "unit": "mm", "min": 0.2, "max": 10},
            {"key": "g", "default": 0.5, "label": "Gap", "unit": "mm", "min": 0.1, "max": 5},
            {"key": "h", "default": 1.6, "label": "Substrate thickness", "unit": "mm", "min": 0.2, "max": 5},
            {"key": "wb", "default": 20.0, "label": "Board width", "unit": "mm", "min": 5, "max": 100},
        ],
        "simulation": {
            "f_min": "f0 * 0.5",
            "f_max": "f0 * 1.5",
            "boundaries": "MUR",
            "end_criteria_db": -40,
        },
        "materials": [
            {"name": "copper", "kind": "metal"},
            {"name": "fr4", "kind": "dielectric", "eps_r": "4.3", "tan_d": "0.02", "tan_d_freq": "f0"},
        ],
        "parts": [
            {
                "name": "substrate",
                "material": "fr4",
                "label": "Substrate",
                "primitives": [
                    {"kind": "box", "start": ["-l/2", "-wb/2", "0"], "stop": ["l/2", "wb/2", "h"]}
                ],
            },
            {
                "name": "center",
                "material": "copper",
                "label": "Center strip",
                "primitives": [
                    {"kind": "box", "start": ["-l/2", "-w/2", "h"], "stop": ["l/2", "w/2", "h"]}
                ],
            },
            {
                "name": "gnd_left",
                "material": "copper",
                "label": "Ground left",
                "primitives": [
                    {
                        "kind": "box",
                        "start": ["-l/2", "-wb/2", "h"],
                        "stop": ["l/2", "-(w/2 + g)", "h"],
                    }
                ],
            },
            {
                "name": "gnd_right",
                "material": "copper",
                "label": "Ground right",
                "primitives": [
                    {
                        "kind": "box",
                        "start": ["-l/2", "w/2 + g", "h"],
                        "stop": ["l/2", "wb/2", "h"],
                    }
                ],
            },
        ],
        "ports": [
            {
                "type": "cpw",
                "number": 1,
                "conductor": "copper",
                "gap": "g",
                "direction": "x",
                "excitation_direction": "y",
                "feed_shift": 2,
                "measurement_shift": 5,
                "reference_ohm": 50,
                "termination": "open",
                "excite": True,
                "start": ["-l/2", "-w/2", "h"],
                "stop": ["-l/2 + 10", "w/2", "h"],
            },
            {
                "type": "cpw",
                "number": 2,
                "conductor": "copper",
                "gap": "g",
                "direction": "x",
                "excitation_direction": "y",
                "feed_shift": 2,
                "measurement_shift": 5,
                "reference_ohm": 50,
                "termination": "open",
                "excite": True,
                "start": ["l/2", "-w/2", "h"],
                "stop": ["l/2 - 10", "w/2", "h"],
            },
        ],
        "resistors": [],
        # refine_features required: openEMS needs ≥3 cells across each CPW gap; with it
        # false, auto mesh stays ~λ/20 and designer preview/drag-drop never shows the model.
        "mesh": {"mode": "auto", "cells_per_wavelength": 20, "refine_features": True},
        "far_field": {"enabled": False},
    }
    write(cpw)

    print("\n=== EMerge admit / resolve expectations ===")
    cases = [
        (
            "portmap_lumped_patch",
            "driven",
            dict(
                analysis="driven",
                accept_finite_feed=True,
                feed_width_mm=1,
                padding_mm=40,
                resolution="coarse",
                f_min_hz=2e9,
                f_max_hz=3e9,
                points=5,
            ),
        ),
        (
            "portmap_microstrip_line",
            "planar",
            dict(
                analysis="planar_two_port",
                accept_lumped_terminals=True,
                enclosure="shielded",
                air_height_mm=6.4,
                resolution="coarse",
                f_min_hz=1.5e9,
                f_max_hz=3.5e9,
                points=5,
                approximate_metals=True,
            ),
        ),
        (
            "portmap_waveguide_wr90",
            "driven",
            dict(
                analysis="driven",
                accept_finite_feed=True,
                feed_width_mm=1,
                padding_mm=40,
                resolution="coarse",
                f_min_hz=8e9,
                f_max_hz=12e9,
                points=5,
            ),
        ),
        (
            "portmap_coaxial_air",
            "driven",
            dict(
                analysis="driven",
                accept_finite_feed=True,
                feed_width_mm=1,
                padding_mm=40,
                resolution="coarse",
                f_min_hz=1e9,
                f_max_hz=2e9,
                points=5,
            ),
        ),
        (
            "portmap_cpw_line",
            "planar",
            dict(
                analysis="emerge_nport",
                accept_modal_ports=True,
                enclosure="shielded",
                air_height_mm=6.4,
                resolution="coarse",
                f_min_hz=1.5e9,
                f_max_hz=3.5e9,
                points=5,
            ),
        ),
    ]
    for id_, path, settings in cases:
        design = json.loads((OUT / f"{id_}.design.json").read_text(encoding="utf-8"))
        port0 = design["ports"][0]
        r = resolve(port0, path=path, settings=settings)
        print(f"{id_}: resolve(path={path!r}) ok={r['ok']} bc={r.get('mapped_bc')} err={r.get('error')}")
        try:
            if path == "driven":
                case = admit_driven(design, settings)
                print(
                    f"  admit_driven OK mapped_bc={case['port'].get('mapped_bc')} "
                    f"approx={case['port'].get('approximations')}"
                )
            else:
                case = admit_planar(design, settings)
                print(
                    f"  admit_planar OK terminals="
                    f"{[(t.get('number'), t.get('mapped_bc')) for t in case.get('terminals', [])]}"
                )
        except Exception as e:
            print(f"  admit FAIL: {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
