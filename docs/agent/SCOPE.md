# EMerge integration scope (fork intent)

EMerge ([FennisRobert/EMerge](https://github.com/FennisRobert/EMerge/), PyPI `emerge`) is a Python frequency-domain FEM solver. Fairbeam's default remains openEMS (FDTD). Elmer already proves an **experimental multi-solver** pattern; EMerge should follow that pattern, not replace it.

## Levels

### A — Fixture MVP (first target)

- Optional Install EMerge (managed venv / pinned wheels), Windows first.
- One fixed research fixture (cavity or simple waveguide), not arbitrary Design translation.
- Discover / capabilities handshake; results + provenance on disk; optional thin UI entry under Experimental solvers.
- Success: reproducible run, documented limits, tests without requiring GPU.

### B — Bounded Design subset

- Axis-aligned dielectric boxes + PEC sheets + single port (Elmer antenna-class gate).
- Explicit reject for curves, booleans, multiport, loss/dispersion (until planned).
- Map S11 (and maybe pattern) into Fairbeam result tabs; label experimental.
- Success: one documented design class; openEMS still default; qualification notes honest.

### B2 — Planar two-port microstrip (hairpin class)

- One substrate box, ground at the bottom (metal z-flat box or domain-floor PEC), z-normal copper
  polygons (or z-flat boxes) on the substrate top, exactly two microstrip ports at board edges.
- Worker rebuilds as substrate `Box` + copper traces + PEC ground + two lumped strip-to-ground
  terminals; `emerge-planar` Run option; 2 × 2 experimental S in shared Results.
- Rejects multilayer, vias, CPW, >2 ports, arbitrary PCB import; no silent geometry coercion.
- Human decision (2026-11-04): integrate the hairpin class as Level B2 (plan
  `docs/agent/plans/2026-11-04-emerge-level-b2-planar-two-port.md`).

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
