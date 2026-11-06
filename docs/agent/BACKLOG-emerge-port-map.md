# Backlog: EMerge port mapping (after Stage A)

**Status:** Stage A done (2026-11-06). Items below are **future work** — do not implement from chat alone; write a plan under `docs/agent/plans/` first.

**Done:** [plans/2026-11-06-emerge-port-map-stage-a.md](plans/2026-11-06-emerge-port-map-stage-a.md)  
**Design (approved):** [specs/2026-11-05-emerge-openems-port-mapping-design.md](specs/2026-11-05-emerge-openems-port-mapping-design.md)

Stage A shipped: adapter-side `emerge_port_map.resolve`, driven lumped → `LumpedPort`, planar microstrip → lumped strip-to-ground, fixture WR-90 waveguide provenance, explicit rejects for Design waveguide / coax / CPW on those paths. openEMS Design schema unchanged.

Local smoke designs (optional, under `python/models/`, not required to commit): `portmap_lumped_patch`, `portmap_microstrip_line`, `portmap_waveguide_wr90`, `portmap_coaxial_air`, `portmap_cpw_line`. Regen: `python/scripts/_gen_portmap_designs.py`.

---

## 1. Stage B — coaxial → `CoaxPort`

- Admit Design `coaxial` ports to EMerge `CoaxPort` (axis / CS, `r_i` / `r_o`, constant εr fill).
- Explicit accept / disclosure UI; reject dispersive fill and invalid radius order.
- Extend `emerge_port_map` Stage B row; worker + tests; honest docs in `EMERGE-EXPERIMENT.md`.
- **Plan file when started:** `docs/agent/plans/YYYY-MM-DD-emerge-port-map-stage-b.md`

## 2. Design waveguide admit (follow-on)

- Stage A kept waveguide as **fixture-only** (Level A WR-90). Design `waveguide` still rejects on Experimental antenna / planar.
- Bounded Design waveguide class → `RectangularWaveguide` (TE first; TM reject unless opted in later).
- Separate plan task; do not silently widen geometry.

## 3. Stage C — modal planar (`WavePort` / `accept_modal_ports`)

- Optional modal map for `microstrip` / `cpw` behind `accept_modal_ports`.
- Prefer `WavePort`; `ModalPort` only after a spike if WavePort cannot drive the admitted class.
- Conflict rule: if both lumped-terminal and modal accepts are on, **modal wins**.
- Hard fail on modal setup errors — no silent fall back to lumped.
- **Plan file when started:** `docs/agent/plans/YYYY-MM-DD-emerge-port-map-stage-c.md`

## 4. UX — suggest the right EMerge Run option from ports — superseded

- **Superseded by Level B3** (2026-11-06): one Run option **EMerge FEM · Experimental** classifies
  driven vs planar from the Design; the user no longer picks antenna vs planar two-port.
  Spec/plan: [specs/2026-11-06-emerge-unified-nport-design.md](specs/2026-11-06-emerge-unified-nport-design.md),
  [plans/2026-11-06-emerge-unified-nport-b3.md](plans/2026-11-06-emerge-unified-nport-b3.md).
- **Info-panel slice done** (2026-11-06): Run dialog shows port→BC preview for the classified path
  before Save and Run — [plans/2026-11-06-emerge-port-map-run-preview.md](plans/2026-11-06-emerge-port-map-run-preview.md).
- Do not re-open “auto-suggest which of two EMerge options” unless a future product split returns.

## 5. Housekeeping / test assets

- Decide whether `portmap_*.design.json` stay local-only or a trimmed set moves to `python/tests/fixtures/` for CI.
- Clear or commit unrelated dirty tree on `feat/emerge-experimental` before starting Stage B.
- Optional: index this backlog from `EMERGE-EXPERIMENT.md` “Port mapping” section when Stage B starts.

---

## Explicitly still out of scope (until reopened)

- Neutral Design “port intent” schema; per-solver port copies in Design JSON.
- Shared `translate_port()` used by openEMS and EMerge.
- Elmer port matrix.
- Claiming S-parameter agreement across solvers; `results_validated` for mapped Design/planar runs.
- Bundling EMerge; replacing openEMS as default.

## How to resume

1. Open this file and pick one numbered item.
2. Say **plan stage B** / **plan design waveguide** / **plan stage C** (or **continue** with that topic). Item 4 (Run UX auto-suggest) is closed by B3.
3. Planner writes `docs/agent/plans/…`; implementer runs tasks; do not code multi-file EMerge work without a plan.
