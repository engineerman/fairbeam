# EMerge integration scope (fork intent)

EMerge ([FennisRobert/EMerge](https://github.com/FennisRobert/EMerge/), PyPI `emerge`) is a Python frequency-domain FEM solver. Fairbeam's default remains openEMS (FDTD). Elmer already proves an **experimental multi-solver** pattern; EMerge should follow that pattern, not replace it.

## Levels

### A — Fixture MVP (first target)

- Optional Install EMerge (managed venv / pinned wheels), Windows first.
- One fixed research fixture (cavity or simple waveguide), not arbitrary Design translation.
- Discover / capabilities handshake; results + provenance on disk; optional thin UI entry under Experimental solvers.
- Success: reproducible run, documented limits, tests without requiring GPU.

### B — Bounded Design subset (legacy recipe under B3)

- Axis-aligned dielectric boxes + metal sheets + lumped ports (Elmer antenna-class geometry gate).
- Originally shipped as exactly one Discrete port and a separate **Experimental antenna** Run option;
  that count gate and dual UI are superseded by Level B3 (recipe kept as the driven/lumped
  classifier).
- Sheet conductor loss via EMerge ThinConductor when Design `conductivity` is set; optional PEC approx.
- Explicit reject for curves, booleans, thick metal volumes / SurfaceImpedance walls, and unsupported
  port types (not “wrong count alone” after B3).
- Map S into Fairbeam result tabs; label experimental.
- Success (historical): one documented design class; openEMS still default; qualification notes honest.

### B2 — Planar microstrip (hairpin class) — done; legacy recipe under B3

- One substrate box, ground at the bottom (metal z-flat box or domain-floor PEC), z-normal copper
  polygons (or z-flat boxes) on the substrate top, homogeneous microstrip or Discrete ports at board
  edges.
- Originally shipped as exactly two ports and a separate **Experimental planar two-port** Run option;
  that count gate and dual UI are superseded by Level B3 (recipe kept as the planar classifier).
- Worker rebuilds as substrate `Box` + copper traces (`ThinConductor` when σ set, else PEC) + PEC
  ground + lumped strip-to-ground terminals; full experimental S in shared Results.
- Rejects multilayer, vias, CPW, mixed port types, arbitrary PCB import; no silent geometry coercion.
- Human decision (2026-11-04): integrate the hairpin class as Level B2 (plan
  `docs/agent/plans/2026-11-04-emerge-level-b2-planar-two-port.md`).
- Closed 2026-11-04 on `feat/emerge-experimental`. Open qualification gaps stay in that plan's
  Task 8 notes (no openEMS S-parameter agreement claim; 41-pt timing deferred; hairpin numbers
  primarily from managed 2.8.9 before the 3.0.0b12 pin).

### B3 — Unified N-port experimental solver — done

- One Run option **EMerge FEM · Experimental** (`backend: "emerge"`, `analysis: "emerge_nport"`)
  when health `emerge` ≥ 3; dual antenna/planar selector removed from the UI.
- Admits **1…N_MAX** ports (`N_MAX = 8`), all the same type, under today’s geometry recipes:
  driven/lumped (Level B class) or planar microstrip/Discrete (Level B2 class). Classifier picks
  `geometry_kind`; mixed types and unsupported geometry still reject explicitly.
- Full experimental N×N S-matrix (`fairbeam.emerge-result/2`); status `results_exported` only.
- Spec: `docs/agent/specs/2026-11-06-emerge-unified-nport-design.md`. Plan:
  `docs/agent/plans/2026-11-06-emerge-unified-nport-b3.md`.

### B4 — Shim cleanup — done

- Design EMerge accepts only `analysis: "emerge_nport"` (no `driven` / `planar_two_port` remaps).
- Assessed Design results are only `fairbeam.emerge-result/2` with `geometry_kind`; v1 schemas and
  `as_nport_result` adapters removed. Dual Run re-exports deleted.
- Spec: `docs/agent/specs/2026-11-06-emerge-b4-shim-cleanup-design.md`. Plan:
  `docs/agent/plans/2026-11-06-emerge-b4-shim-cleanup.md`.
- **B5+**: geometry widen (stackup/vias) and richer port BCs — not part of B4.

### C — Out of scope for now

- Production parity with openEMS (optimizer, arrays, thin copper sheets, full CAD).
- Bundling EMerge into the stock first-run installer.
- Silent “make it fit” geometry conversion.
- Marketing comparisons with proprietary FEM tools.

## License posture

- Fairbeam: GPL-3.0-or-later. New fork code (adapter, worker, UI, tests, docs) uses the same license; the fork cannot relicense upstream Fairbeam code.
- EMerge **3.0.0b12** (managed pin; was 2.8.9): **GPL-2.0-or-later** (source headers: "version 2 ... or (at your option) any later version"; wheel ships GPL-2 LICENSE text; headers still offer later versions). That allows use under GPL-3.0, so it is compatible with Fairbeam. Rechecked 2026-11-04 on the `emerge-3.0.0b12` wheel; recheck again when the pinned version changes.
- Human decision (2026-11-04): prefer the broadest license terms the upstream projects permit, which is the GPL-2.0-or-later reading above.
- Managed install dependencies (fetched from PyPI on request, never shipped): gmsh GPL-2.0-or-later; emsutil MIT upstream with some GNU-headed files; Intel MKL and its runtime packages under the proprietary Intel Simplified Software License. Human decision (2026-11-04): keep MKL and disclose its license before install.
- Still required: optional external install + adapter in a separate process (Elmer style). The installer bundles nothing. Vendoring EMerge source or shipping its binaries needs maintainer review, because Fairbeam would then carry EMerge's (and gmsh/MKL's) distribution and corresponding-source obligations.

## Reference inside Fairbeam

See `.cursor/skills/emerge-agent-workflow/references/elmer-touchpoints.md` and `docs/EXPERIMENTAL-SOLVERS.md`.
