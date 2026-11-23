# EMerge integration scope (fork intent)

EMerge ([FennisRobert/EMerge](https://github.com/FennisRobert/EMerge/), PyPI `emerge`) is a Python frequency-domain FEM solver. Fairbeam's default remains openEMS (FDTD). Elmer already proves an **experimental multi-solver** pattern; EMerge follows that pattern, not a replacement.

## What exists today (experimental)

- Optional **Install EMerge** (managed venv / pinned `emerge==3.0.0b12` wheels), Windows first; separate process / import isolation (Elmer style).
- Fixed **Research** WR-90 waveguide fixture (no Design translation).
- One Design Run option **EMerge FEM · Experimental** (`backend: "emerge"`, `analysis: "emerge_nport"`, health `emerge` ≥ 3): homogeneous **1…8** ports, full experimental N×N S (`fairbeam.emerge-result/2`, `results_exported` only).
- Geometry recipes on that path: driven/lumped (axis-aligned boxes + metal sheets), planar microstrip/Discrete (single-layer board + ground; microstrip may opt into `WavePort` via `accept_modal_ports`, else lumped terminals), classic CPW (coplanar top grounds; `WavePort` / lumped gap plate behind the same accept pair; GCPW rejected), all-coaxial TEM (`CoaxPort`, `accept_coaxial_tem`).
- Session **Simulation › Solver** picker (openEMS default vs EMerge experimental): retargets settings chrome, mesh-only generate, FEM exterior overlay — not FDTD planes.
- Explicit reject for unsupported geometry / mixed port types; no silent coercion.
- Port-map matrix + Run preview/accept: [specs/2026-11-05-emerge-openems-port-mapping-design.md](specs/2026-11-05-emerge-openems-port-mapping-design.md). Limits: [EMERGE-EXPERIMENT.md](../EMERGE-EXPERIMENT.md).

## What to do next

Open work lives only in [BACKLOG-emerge-port-map.md](BACKLOG-emerge-port-map.md). Write a plan under `plans/` before multi-file coding. Do not reopen finished path wiring unless fixing a regression.

## Out of scope for now

- Production parity with openEMS (optimizer, arrays, full CAD).
- Bundling EMerge into the stock first-run installer.
- Silent “make it fit” geometry conversion.
- Marketing comparisons with proprietary FEM tools.
- Neutral Design “port intent” schema; shared `translate_port()` with openEMS; `results_validated` / S-agreement claims for mapped EMerge runs.

## License posture

- Fairbeam: GPL-3.0-or-later. New fork code (adapter, worker, UI, tests, docs) uses the same license; the fork cannot relicense upstream Fairbeam code.
- EMerge **3.0.0b12** (managed pin): **GPL-2.0-or-later** (source headers offer later versions; wheel ships GPL-2 LICENSE text). Compatible with Fairbeam under GPL-3.0. Recheck when the pinned version changes.
- Human decision (2026-11-04): prefer the broadest license terms the upstream projects permit (GPL-2.0-or-later reading above).
- Managed install dependencies (fetched from PyPI on request, never shipped): gmsh GPL-2.0-or-later; emsutil MIT upstream with some GNU-headed files; Intel MKL and its runtime packages under the proprietary Intel Simplified Software License. Keep MKL and disclose its license before install.
- Still required: optional external install + adapter in a separate process. The installer bundles nothing. Vendoring EMerge source or shipping its binaries needs maintainer review.

## Reference inside Fairbeam

See `.cursor/skills/emerge-agent-workflow/references/elmer-touchpoints.md` and `docs/EXPERIMENTAL-SOLVERS.md`.
