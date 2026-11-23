# Handoff — Classic CPW WavePort physics (high S11)

> Generated: 2026-11-07  
> Project: `d:\W\P\fairbeam` · branch `feat/emerge-experimental`  
> Backlog card: **O17** (see `BACKLOG-emerge-port-map.md`)  
> Session summary: O8/C2 wired classic CPW → EMerge WavePort through the Run path; human UI test shows total reflection and suspicious field cut — investigate aperture / excitation, do not treat C2 S as validated.

## Goal

Make experimental EMerge **classic CPW** `WavePort` runs produce **plausible through-line behavior** on `portmap_cpw_line` (not |S11|≈1 / |S21|≈0), without inventing openEMS S-agreement claims, without shipping `ModalPort` unless WavePort is proven insufficient + human go-ahead, and without inventing a substrate-bottom PEC on classic CPW.

End state: measured coarse S on the fixture is no longer “all reflected”; docs record honest limits; human accepts via the acceptance gate before closing the card.

## Current State

**Working (plumbing — C2):**
- Homogeneous all-`cpw` admits on unified Run path (`emerge_solver.admit` → planar).
- `accept_modal_ports` → `WavePort`; modal wins over lumped; UI preview + modal ack.
- Worker skips `PEC(diel.bottom)` when `ground_mode == "coplanar"`.
- FEM result export no longer fails openEMS “3 cells across CPW gap” preview gate (`emerge_bundle` strips microstrip/cpw ports for geometry-only preview).
- Local fixture `python/models/portmap_cpw_line.design.json` builds in designer when `mesh.refine_features: true` (regen via `_gen_portmap_designs.py`).
- Serve: repo `.venv`, port 5320; Python does not hot-reload — restart after code changes.

**Broken (physics):**
- Human + agent-measured EMerge S on CPW through-line: **almost total reflection**.
- Field-1 (auto z-cut) shows energy piled at the driven end; little propagation — matches S.
- Job evidence (do not invent numbers; re-measure if jobs are gone):

| Job | Notes |
| --- | --- |
| `.sim/jobs/20261107-010833-bccee1` | `done`, WavePort, shielded: \|S11\| min≈0.978 (−0.2 dB) @3.6 GHz, max≈0.998 @1.2 GHz; \|S21\| max≈0.033 |
| `.sim/jobs/20261107-005533-f0a559` | Same S shape; originally failed packaging (fixed in `8b2f94c`) |

Case aperture from `010833` `case.json`:
- `ground_mode=coplanar`, `enclosure=shielded`
- Term 1: `lo=[-0.015,-0.00175,0]`, `hi=[-0.015,0.00175,0.0016]` (board-edge face, **height = substrate only**)
- Traces at `z=0.0016` (top of that face)
- Air box extends to `z=0.008`

## Files in Play

| File | Why |
| --- | --- |
| `python/fairbeam/emerge_planar.py` | Builds CPW terminal `lo`/`hi`; aperture height = substrate thickness only |
| `python/fairbeam_emerge_worker.py` | `apply_planar_terminal_bc` → `WavePort(..., number_of_modes=1, impedance_definition="PV")`; LumpedPort still `direction=em.ZAX` |
| `python/fairbeam/emerge_solver.py` | Unified Run classify; must keep `cpw` in `try_planar` |
| `python/fairbeam/emerge_bundle.py` | Results packaging; do not reintroduce openEMS CPW mesh gate |
| `python/scripts/_gen_portmap_designs.py` | Fixture; `refine_features: True` required for designer preview |
| `python/models/portmap_cpw_line.design.json` | Local only (gitignored); regen from script |
| `docs/EMERGE-EXPERIMENT.md` | Stage C CPW limits; update measured notes after a real improved run |
| `.cursor/rules/human-acceptance-gate.mdc` | Do not close card / tick plan done until human Your-test ok |
| `.cursor/rules/windows-local-python.mdc` | `.venv` + `OPENEMS_INSTALL_PATH` gpu-runtime path |
| `.cursor/rules/self-verify-before-user.mdc` | Restart `fairbeam serve` after Python changes; solver claims need real export |

## What Has Been Tried (and Why It Failed / What It Taught)

1. **CLI-only smoke via `emerge_planar.admit` + `fairbeam_emerge planar`** — Passed mesh/S export early; **missed** Run path. Human could not Save and run until `emerge_solver` included `cpw` in `try_planar` (`a65a1d4`).
2. **Full S via research** — Solve succeeded but `export_emerge_bundle` → `build_preview` hit openEMS `planar mesh requires at least three cells across substrate height or each CPW gap`; job error surfaced as `research result backend identity mismatch` (unstamped `result.json`). Fixed by stripping microstrip/cpw ports in FEM geometry preview (`8b2f94c`).
3. **Designer drag-drop of CPW fixture** — Failed preview with same 3-cell gap message because fixture had `refine_features: false`. Fixed in generator (`b30ec8f`); local model regenerated.
4. **Human S + Field-1 inspection after plumbing fixed** — Run completes; **physics still wrong** (S11≈0 dB). No aperture-height change tried yet.

## Current Best Theory

Classic CPW quasi-TEM lives in the **gaps and air above** the metal plane. Fairbeam sizes the WavePort face as a board-edge plate with **height = substrate thickness only** (locked in O8 Task 2 for parity with microstrip strip-to-ground height). Metals sit on the **top edge** of that face (`z = h`). The modal port likely never sees a proper CPW mode (or picks a useless cavity/shielded mode), so the driven port reflects.

Secondary suspicions (check after aperture):
- `enclosure=shielded` PEC box interacting badly with coplanar grounds.
- Auto field cut at mid-substrate (`z≈0.8 mm`) is a poor CPW diagnostic (prefer near `z=h` or slightly above).
- Lumped CPW still uses `LumpedPort(..., direction=em.ZAX)` — vertical drive on a board with **no bottom ground**; wrong if someone tests lumped accept. Modal path is WavePort-only for the failing job.

## Next Steps

1. Read this handoff + `BACKLOG` card **O17** + Stage C CPW section in `docs/EMERGE-EXPERIMENT.md`. Load skill `emerge-agent-workflow`.
2. **Planner first:** write `docs/agent/plans/YYYY-MM-DD-emerge-o17-cpw-waveport-aperture.md` with Global Constraints unchanged (no ModalPort without human go-ahead; no silent bottom PEC; no openEMS S-agreement claim). Propose aperture experiments (ordered):
   - Extend WavePort face **into air above substrate** (e.g. fraction of `air_height_mm` or fixed mm), keep transverse span = locked strip+2×gap rule.
   - Optional A/B: `enclosure=open` vs shielded on the same aperture.
   - Optional: confirm LumpedPort direction for coplanar (transverse in-plane, not `ZAX`) as separate sub-task if in scope.
3. Implement **one** experiment at a time; self-verify with **Run path** (`emerge_solver` / research), not only `emerge_planar.admit` CLI.
4. Measure on managed EMerge **3.0.0b12**; record \|S11\|/\|S21\| vs frequency from the job `result.json` only.
5. Give human a **Your test** recipe; wait for ok/fail before ticking plan / closing O17 (`human-acceptance-gate.mdc`).
6. If WavePort still cannot drive CPW after documented aperture trials → **BLOCKED** for ModalPort; escalate to human (do not ship ModalPort).

### Reproduce (Windows)

```powershell
$env:OPENEMS_INSTALL_PATH = "C:\Users\ee\AppData\Local\org.fairbeam.desktop\gpu-runtime\openEMS"
# Designer: open python/models/portmap_cpw_line.design.json
# Solver EMerge FEM · Experimental, accept_modal_ports, shielded coarse → Save and run
# Or inspect last job:
#   d:\W\P\fairbeam\.sim\jobs\20261107-010833-bccee1\research\result.json
```

Serve restart after Python edits:

```powershell
# stop existing fairbeam serve on 5320, then:
cd d:\W\P\fairbeam\python
d:\W\P\fairbeam\.venv\Scripts\python.exe -m fairbeam serve --port 5320
```

## Key Constraints and Context

- Branch: `feat/emerge-experimental`. Never push `upstream`; never open PRs; push `origin/main` only if human asks (`main-squash-merge.mdc`).
- Human rule: **agent self-verify ≠ close**. Always Your-test + explicit approval before checkbox/card close.
- Do not use SubAgent unless human asks.
- openEMS remains default; EMerge opt-in experimental only.
- Numbers in docs only from runs (`AI_POLICY.md`).
- Do not commit `python/models/` personal fixtures.
- Related commits on this branch: `a65a1d4` (solver classify cpw), `8b2f94c` (bundle export), `b30ec8f` (fixture refine_features), `6b3ceb7` (C2 docs — written before human physics accept).

## Memory Pointers

claude-mem search timed out while writing this handoff. Re-run if available:

- `smart_search`: `CPW WavePort S11 aperture fairbeam`
- Prefer this file + backlog O17 over stale chat summaries.

## Fresh agent first message (suggested)

> Activate **O17**. Read `docs/agent/HANDOFF-cpw-waveport-physics.md` and write a plan under `docs/agent/plans/` for CPW WavePort aperture experiments. Do not implement until the plan is written. No SubAgent. Use emerge-agent-workflow + human-acceptance-gate.
