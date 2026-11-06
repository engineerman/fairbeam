# EMerge gaps / follow-ups

Living list of known gaps in the current EMerge experimental path.
When enough items are collected, turn them into a plan under `docs/agent/plans/`.

Last updated: 2026-11-05

## Open

### 2. Solver-scoped Simulation UI (openEMS vs EMerge) — product direction

**Context (human, 2026-11-04):** Fairbeam’s Simulation ribbon and dialogs (Mesh settings, Mesh view, Boundaries, Frequency, Monitors, Run setup, etc.) are built around **openEMS FDTD** (structured / rectangular grid). EMerge is **frequency-domain FEM** with a **tetrahedral** mesh and different controls (resolution as wavelength fraction, enclosure, lumped terminals, no FDTD cells/λ, no Yee mesh planes). Today EMerge is reached as an **experimental** Run / Research path (Elmer pattern), not as a first-class engine that retargets those menus.

**Proposal (human):** Add a **solver picker** (desktop-simulator style: Solver or Run split-button / dropdown — openEMS vs EMerge [vs Elmer]). Active solver would drive which Simulation Settings tabs and ribbon actions appear or mean. Same entry points (Mesh settings, Mesh view, Boundaries, Frequency…) stay, but the popup content becomes engine-specific. For EMerge: show EMerge parameters; Mesh view would show the **actual FEM mesh** on the model (after mesh-only or after solve), not the FDTD plane overlay.

**Related capability (already true in EMerge API, not wired in Fairbeam):** `generate_mesh()` can run **without** `run_sweep` (frequencies still needed for sizing). Fairbeam could later offer mesh-only preview + scene overlay; that needs mesh export + a non-FDTD drawer. Current bundle only stores bbox axes + node/tet counts.

**Plan:** `docs/agent/plans/2026-11-04-emerge-solver-scoped-ui.md` (Approach C).

**Status (2026-11-05):** Phases 0–5b / Tasks 1–8b **shipped** on `feat/emerge-experimental`:

| Shipped | Notes |
| --- | --- |
| Solver time on EMerge runs | §1 → Done |
| Session `activeEngine` + Simulation › Solver picker | openEMS default; EMerge labeled experimental |
| Run chrome (label + pink `--al-action-emerge`) | |
| Ribbon / Post / Optimize gating | FDTD-only controls disabled or hidden; Optimize deferred |
| EMerge Simulation Settings panels | band, points, enclosure, curated mesh knobs |
| Run dialog honors `activeEngine` | |
| Mesh-only generate | node/tet counts + exterior surface edges |
| Mid-plane E-field cut export | Post › Field plane when present |
| FEM mesh overlay (Task 9) | Mesh view draws exterior surface wireframe (thinned if large); never FDTD planes |

**Still open under this gap:**

- Surface-current export (`current_boundary`) — separate follow-on.
- Far field / efficiency / pattern export — still disabled until schema work.
- Optimize / Sweep driving EMerge — explicit non-goal of that plan.
- Optional denser FEM draw (all tets / interior edges) if exterior wireframe is not enough.

**Legal / wording:** Internal notes may compare UX metaphors; shipped UI/docs must not claim parity with proprietary EM simulators (`check:legal`). Prefer “engine” / “experimental solver” language in product copy.

## Done

### 1. Runs tab: solver time empty for EMerge

**Symptom:** After an EMerge simulation finishes, the Runs dock / Runs tab **Solver time** column stayed empty.

**Fix:** Task 1 of `docs/agent/plans/2026-11-04-emerge-solver-scoped-ui.md` — `emerge_bundle` maps `elapsed_seconds` → `run.solver_time_s` / `wall_time_s`.
