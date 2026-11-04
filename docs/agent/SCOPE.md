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

### C — Out of scope for now

- Production parity with openEMS (optimizer, arrays, thin copper sheets, full CAD).
- Bundling EMerge into the stock first-run installer.
- Silent “make it fit” geometry conversion.
- Marketing comparisons with proprietary FEM tools.

## License posture

- Fairbeam: GPL-3.0-or-later.
- EMerge: GPL-2.0 (treat as **GPL-2.0-only** until upstream says otherwise).
- Preferred: optional external install + adapter (Elmer style). Do not vendor EMerge into the Fairbeam source tree as one combined GPL-3 distribution without review.

## Reference inside Fairbeam

See `.cursor/skills/emerge-agent-workflow/references/elmer-touchpoints.md` and `docs/EXPERIMENTAL-SOLVERS.md`.
