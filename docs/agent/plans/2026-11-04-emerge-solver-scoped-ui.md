# EMerge solver-scoped Simulation UI — Implementation Plan

> **For agentic workers:** Use `.cursor/skills/emerge-agent-workflow`. Implement task-by-task with checkbox tracking. Planner = capable model; implementer = cheap/mid for single tasks, mid for ribbon/dialog glue.

**Goal:** Let the user pick **openEMS** or **EMerge** as the active Simulation engine so Run chrome and Simulation / Post menus show engine-appropriate controls, while openEMS stays the default and EMerge remains explicitly experimental.

**Architecture:** Introduce a session-level `activeEngine` (`openems` | `emerge`) that drives ribbon chrome (Run label + accent), which Simulation Settings sections open, and which Post / Optimize actions are enabled. Reuse existing EMerge Run forms and Research setup; do not invent a second settings framework. FEM mesh overlay and Optimize-on-EMerge are later phases. Elmer stays under Experimental solvers / Run dialog options (not co-equal in the primary picker in this plan).

**Tech Stack:** SolidJS designer ribbon (`DesignWorkspace.tsx`), Run dialog, Simulation Settings dialog, CSS design tokens, i18n `en.json`/`tr.json`, existing `emerge_*` Python adapters / worker for mesh-only later.

## Global Constraints

- openEMS remains the **default** engine on new sessions and cold start.
- EMerge stays **opt-in experimental**; product copy must say experimental / not validated; no proprietary-simulator parity claims (`npm run check:legal`).
- Do **not** rewrite the core designer around FEM (`MISSION.md` “Not the mission”); scope is engine-gated chrome + settings surfaces + honest disable/hide.
- Unsupported geometry is still rejected by EMerge admit paths; switching engine never silently coerces geometry.
- UI strings: both `src/i18n/en.json` and `src/i18n/tr.json`.
- Numbers in docs come from runs, not models.
- Branch: `feat/emerge-experimental`. Follow `AI_POLICY.md` (`Co-Authored-By`).
- Prefer Elmer-pattern touchpoints; do not replace openEMS Run / preview paths.
- Pink Run accent is a **token** (e.g. `--al-action-emerge`); do not hard-code random pinks in many files.
- Optimize for EMerge is **out of this plan’s delivery** (explicit defer); UI must disable or explain, not pretend.
- Post-processing: keep S-parameter / Smith paths that already work for EMerge exports; hide or disable monitors Fairbeam cannot fill from EMerge yet.

---

## Approaches considered

| Approach | Idea | Pros | Cons |
| --- | --- | --- | --- |
| A. Run-dialog only | Keep today’s solver `<select>` in Run; no ribbon state | Small change | Does not match human ask (chrome + menus) |
| B. Big-bang ribbon clone | One PR retargets every Simulation / Post / Optimize control | Matches mental model fast | High risk; conflicts with “don’t rewrite designer around FEM” |
| **C. Phased `activeEngine` (recommended)** | Session engine picker → chrome → gate menus → EMerge settings body → mesh-only → FEM mesh view later | Matches ask; shippable slices; openEMS default preserved | Needs discipline so mid phases don’t leave half-wired dialogs |

**Recommendation:** Approach C.

---

## Human UX decisions (locked for this plan)

1. **Primary picker:** openEMS | EMerge (experimental). Elmer + waveguide fixture remain under **Experimental solvers** and/or the Run dialog’s longer option list — not the main two-way chrome switch.
2. **EMerge analysis mode** when engine is EMerge: session remembers last used path among admitted modes the health API allows (`emerge-driven` / `emerge-planar`); Run opens that form. If none available, Run opens Research/Install.
3. **Run button:** openEMS → existing primary (copper/orange `--al-action`); EMerge → pink token `--al-action-emerge`. Label shows engine name (`openEMS` / `EMerge`) plus Run semantics.
4. **Persistence:** session-only first (store like threads/engine). Optional later: persist hint on project file — **not** in Phase 1–3.
5. **Optimize tab when EMerge active:** disable Sweep/Optimizer with a short note; revisit in a later plan.
6. **Mesh view when EMerge active (early phases):** either open an “EMerge mesh not in FDTD view yet” note + offer Generate mesh (counts), or disable until Phase 6. Do **not** show the FDTD plane as if it were the FEM mesh.

---

## Capability matrix (menus) — summary

Legend: **keep** · **retarget** · **disable** · **hide** · **later**

| Area | openEMS | EMerge (this plan) |
| --- | --- | --- |
| Frequency band / f_min–f_max | keep | retarget: band + **points** |
| Boundaries | keep (6 faces MUR/PML/PEC/PMC) | **retarget** — see §Boundaries deep-dive (not MUR/PML) |
| Mesh settings | keep | retarget: **curated EMerge mesh panel** (see §6 / Mesh knobs) — not a full dense vendor-style dump |
| Mesh convergence | keep | **disable** |
| Mesh view (no prior solve) | FDTD preview mesh | **mesh-only possible** — see §Mesh; show only after generate; never fake FDTD planes |
| Ports | keep | model edit keep; admit still rejects |
| Far field / currents / efficiency / field planes (Sim monitors) | keep | **disable** until export exists — see deep-dives |
| Solver limits (dB / timesteps) | keep | **hide** / EMerge limits note |
| Experimental solvers | keep | keep |
| Run | openEMS body | EMerge mode form |
| Optimize | keep | **disable** (defer) |
| Post: Summary / S-params / Smith | keep | **keep** when EMerge result present |
| Post: Efficiency / Pattern / Currents / Field + Play | keep | **disable** until schema+export; Play only if complex phasors present |
| Solver time in Runs | keep | populate `solver_time_s` early |

---

## Deep-dive: what EMerge actually gives (3.0.0b12) vs Fairbeam UI

Evidence from installed `emerge==3.0.0b12` (`site-packages/emerge/_emerge/…`) and current Fairbeam workers. Rule for implementers: **UI control exists only if (a) EMerge can produce the quantity and (b) Fairbeam has mapped it into a bundle the viewer understands.** Otherwise hide/disable — never show an empty Play or MUR list.

### 1. Mesh without running the solver

| Question | Answer |
| --- | --- |
| Does EMerge mesh without `run_sweep`? | **Yes.** API order: geometry → `set_frequency` / band (needed for size) → `commit_geometry` → `generate_mesh()` → mesh exists; solve is a later step. |
| What do you get? | `sim.mesh.n_nodes`, `n_tets`, `nodes`, tet connectivity (`get_nodes` / tet arrays), `plot_gmsh()`, surface triangles. |
| Can Fairbeam show it **today** after Mesh view click with no prior run? | **No.** Worker always continues to `run_sweep`. Bundle only stores bbox axis stubs + node/tet **counts**, not tet geometry. Mesh view draws **FDTD** `mesh.x/y/z` planes — wrong representation for FEM. |
| Plan implication | Phase 5: mesh-only job → counts (+ optional edge dump). Phase 6: FEM overlay. Until then Mesh view under EMerge must **not** open the FDTD plane UI as if it were the mesh. A “Generate mesh” button that returns counts is honest; claiming “show mesh on model” requires Phase 6. |

**User scenario:** *Simulation → Mesh view, no run yet, EMerge active.*  
**Honest UX:** either (A) prompt “Generate mesh (no solve)” then show counts / later overlay, or (B) disable Mesh view with “Generate mesh from Mesh settings first”. Do **not** show openEMS grid.

### 2. Surface current + Play button

| Layer | Reality |
| --- | --- |
| EMerge API | **Yes, post-solve.** `MWData.current_boundary(selection)` estimates \(J_s = n \times (H_+ - H_-)\) on a face (`microwave_data.py`). Needs a completed frequency solution + face selection. Not a pre-solve “monitor checkbox” like openEMS. |
| Fairbeam export today | **No.** EMerge antenna/planar workers do not call `current_boundary` or fill `bundle.fields`. |
| Fairbeam UI Play | `FieldPlaneControls` / current animation need **complex phasors** in the result (`hasPhasor` / `b.fields`). Play animates \(\mathrm{Re}\{J e^{j\omega t}\}\) over phase. |
| If EMerge selected and no Js export | Surface Current ribbon + Post → Currents: **disable**. No Play control. No empty currents panel. |
| If we later export Js as complex maps compatible with existing current/field viewers | Then Magnitude / Phase / Animate + Play are justified (FEM is frequency-domain; animation is meaningful). That is a **new schema task**, not chrome-only. |

**User scenario:** *Post → Surface Current, EMerge run finished (S only).*  
**Required:** disabled entry + title “This experimental EMerge run has no surface-current export.” Not a panel with a dead Play.

### 3. Field plane (E/H cut) + Play — **EMerge can give real plots; Fairbeam should show them**

Human note (2026-11-04): EMerge demos/docs show useful mid-substrate / cut-plane field figures. That is a **product goal**, not a forever-disable. Chrome phases may gate the openEMS field-plane editor until export exists; a later task must ship an EMerge → Fairbeam field cut.

| Layer | Reality (EMerge 3.0.0b12) |
| --- | --- |
| API | **Yes, post-solve.** `dataset(freq=…).cutplane(ds=…, z=…)` (or x/y) and `cutplane_normal`; also `interpolate`. Howto example: `dataset(freq=1e9).cutplane(ds=0.002, z=0.005).scalar('Ey','real')` — exactly “mid / in-board” style cuts. |
| Time vs frequency | **Frequency-domain harmonic**, not FDTD transient. Solution is stored **per frequency point** in the sweep (`MWField`: “field solution of a single frequency”). You pick `freq=…`, then sample a cut. |
| What one plot is | Complex **phasors** Ex,Ey,Ez,Hx,… on the cut grid. Display options via `scalar(..., metric)` / `vector(..., metric)`: `abs` \| `real` \| `imag` \| **`complex`**. Docs: *“For animations, make sure to select the complex metric.”* So “time-varying” in the Fairbeam Play sense = animate \(\mathrm{Re}\{E\,e^{j\omega t}\}\) over phase at **one** frequency — not a movie across the whole sweep unless the UI steps frequency separately. |
| Multi-frequency | Sweep has many freqs; each cut is **one freq at a time** (user or default: e.g. best \|S21\| or band center). |
| Fairbeam today | openEMS monitors → `bundle.field_planes`. EMerge workers: **do not** call `cutplane` / do not fill `field_planes`. |
| UI until export | Disable openEMS Field-plane **monitor editor** under EMerge (wrong lifecycle: FDTD pre-schedules samples). After export: Post / 3D field-plane view can reuse Fairbeam’s Magnitude / Phase / Animate + Play **if** complex samples are stored. |
| Plan implication | Add **Task 8b / Phase field-cut**: after a successful EMerge solve, extract one (or N) cutplanes (default mid-substrate / z = board top + ε for planar) at a chosen frequency into Fairbeam’s field-plane schema (or a thin experimental twin). Static \|E\| or Re(Ey) is enough for v1; complex + Play is v1.1 if schema allows. |

**User scenario:** *EMerge run done → show an E-field plot like the EMerge figures.*  
**Answer:** Upstream yes (per-frequency complex cut). Fairbeam must export it. Do not tell the user “EMerge has no fields.” Tell them “not wired into Fairbeam yet,” then ship the cutplane export.
### 4. Far field / efficiency / pattern

| Layer | Reality |
| --- | --- |
| EMerge API | Has `farfield` / `farfield_2d` / `farfield_3d` helpers on microwave data (and related plot code). |
| Fairbeam EMerge paths today | Explicitly **no far field** in planar/antenna limitations; status `results_exported` without NF2FF/gain certificate. |
| UI | Far field / Efficiency / Pattern / Pattern 3D: **disable** under EMerge until a planned export lands. |

### 5. Boundaries — openEMS MUR/PML vs EMerge

openEMS Fairbeam (`SimSettingsDialog`): per-face **PEC / PMC / MUR / PML_8**.

EMerge native BC types (selected): **PEC**, **PMC**, **AbsorbingBoundary** (Robin ABC, `order`, `abctype` A–E — Fairbeam planar/antenna use order=2, type B), ports (Lumped/Modal/Rect WG/…), SurfaceImpedance, ThinConductor, Floquet, etc. PML appears as **geometry aids** (`geo` PML box) and assembly mentions — **not** the same UX as “PML, 8 cells” on an FDTD face. EMerge howto: Robin ABC on **flat** surfaces.

Fairbeam EMerge **today** does **not** expose a 6-face MUR/PML picker. It uses **enclosure presets**:

| Preset | Meaning in Fairbeam EMerge |
| --- | --- |
| `shielded` | Outer box faces PEC (closed cavity-like) |
| `open` | AbsorbingBoundary on open faces + padding; planar keeps **PEC floor** (ground) |

**EMerge Boundaries UI must be retargeted**, not a copy of MUR/PML:

| Control | openEMS | EMerge (planned UI) |
| --- | --- | --- |
| Face type MUR | yes | **no** — do not list |
| Face type PML_8 | yes | **no** — do not list (would lie) |
| Face type PEC / PMC | yes | **later** optional per-face; not required for v1 |
| Enclosure shielded / open | n/a | **yes** (v1 — matches worker) |
| Open: padding_mm | n/a | **yes** |
| ABC order / abctype | n/a | hide advanced or note defaults (2 / B); no Mur label |

Opening Boundaries with EMerge active must **not** show the openEMS six-face MUR/PML diagram.

### 6. Frequency / Mesh settings (parameter mismatch)

| openEMS | EMerge |
| --- | --- |
| f_min, f_max, (Run: points, timesteps) | f_min, f_max, **points** (3–21 driven / 3–41 planar) |
| cells per λ, manual lines, design mesh | λ-fraction + optional local/trace knobs (§6b) — **not** FDTD cells/λ |
| end criteria dB, max timesteps | N/A (frequency sweep / direct FEM) — hide Solver limits |
| Mesh convergence dialog | N/A — disable (AMR is a separate optional later path) |

### 6b. EMerge mesh knobs — curated UI (keep the menu simple)

EMerge exposes a dense vendor-style mesher stack (verified on 3.0.0b12 `Mesher` / `Simulation`):

| Group | API | Notes |
| --- | --- | --- |
| Global / λ | `set_resolution(r)` — target size ≈ r·λ (e.g. 0.25 = λ/4; smaller = finer) | Already used: coarse 0.25 / fine 0.15 |
| Global cap | `mesher.set_global_max_size(size)` | Absolute ceiling everywhere |
| Local volume/face | `set_domain_size`, `set_face_size`, `set_size` | Object-scoped max size |
| Conductor / strip | `set_boundary_size`, `set_trace_refinement(...)`, `refine_conductor_edge` | Hairpin-relevant (copper edges, strip/gap) |
| PEC speed | `set_pec_face` / `set_pec_domain` | Keep PEC coarse |
| Curves | `set_curved_boundary_meshing(factor=10)` | Less relevant for axis-aligned Fairbeam subset |
| GMSH algo | `mesher.set_algorithm(Algorithm3D.…, nthreads=…)` | DELAUNAY, FRONTAL, MMG3D, HXT, RTREE, INITIAL_MESH_ONLY |
| AMR | `adaptive_mesh_refinement` knobs (`max_steps`, convergence, `max_tets`, `growth`, …) | Hairpin bakeoff: **AMR off** |

**Product decision (human, 2026-11-04):** expose a **small curated subset** in Mesh settings so the menu stays simple; do not mirror every vendor / EMerge control in v1.

**v1 Mesh settings (EMerge) — recommended:**

1. **Resolution preset:** Coarse (0.25) / Fine (0.15) / Custom λ-fraction (numeric `r`, with sane min/max clamp).
2. **Optional global max size (mm):** maps to `set_global_max_size` — off by default (empty = unset).
3. **Planar / metal assist (one checkbox):** e.g. “Refine conductor edges” → worker applies `set_boundary_size` / `set_trace_refinement` with **Fairbeam-chosen defaults** (not a full quality_factor / growth_rate form in v1).
4. **Generate mesh** (mesh-only) + node/tet readout.
5. Short note: experimental; AMR not offered in v1.

**Explicitly out of v1 Mesh UI (later / Advanced):**

- Per-object `set_domain_size` / `set_face_size` pickers
- Full `set_trace_refinement` parameter sheet
- GMSH algorithm dropdown (keep worker default)
- AMR panel — optional later; default **off** like the hairpin bakeoff
- `set_curved_boundary_meshing` until curved geometry is admitted

**v1.1+ (only if mesh quality walls):** “Advanced…” with algorithm + one AMR toggle with fixed safe defaults — still no dense vendor-style density control surface.

Worker accepts only the curated settings object; unsupported keys rejected. Do not write these into openEMS `draft.mesh.cells_per_wavelength`.

### 7. Play button rule (global)

```
Show Play / Animate  ⇔  result carries complex phasors for that view
                      ∧  active presentation is currents or field-plane (or future FEM field view)
```

EMerge S-only export ⇒ no Play anywhere for fields/currents.  
S-params charts do not use that Play control.

### EMerge physics vs Fairbeam Post (honest)

Today Fairbeam’s EMerge paths export **S** (and antenna S11/Zin) as `results_exported`. Upstream EMerge **can** produce surface current estimates, cut-plane E/H, and some far-field helpers **after** solve, but Fairbeam has **not** normalized those into `bundle.fields` / `field_planes` / NF2FF. Chrome work must gate on **Fairbeam exports**, not on “EMerge README mentions it.”

---

## File map

| File | Responsibility |
| --- | --- |
| `src/designer/activeEngine.ts` (new) | `activeEngine` signal, setters, defaults, helpers (`isEmerge`, label keys) |
| `src/designer/DesignWorkspace.tsx` | Ribbon Simulation / Run / Optimize / Post gating; Run accent class; Solver split / picker control |
| `src/designer/RunDialog.tsx` | Honor `activeEngine` (preselect openEMS vs EMerge mode); keep Elmer options |
| `src/designer/SimSettingsDialog.tsx` | Section visibility / EMerge panels or redirect |
| `src/designer/EmergeSimSettings.tsx` (new, mid) | EMerge-specific settings body (band, enclosure, resolution) shared by ribbon entries |
| `src/designer/MeshView.tsx` / `src/scene/Viewport.tsx` | Later: FEM overlay; early: refuse FDTD view for EMerge |
| `src/styles/designer.css` / tokens | `--al-action-emerge`, `.rb-primary-emerge` |
| `src/i18n/en.json`, `tr.json` | All new strings |
| `python/fairbeam_emerge_worker.py` / bundle | Solver time; later mesh-only endpoint |
| `docs/agent/GAPS.md` | Point at this plan; mark §2 in progress |
| `docs/EXPERIMENTAL-SOLVERS.md` | Short “active engine” note when shipping |

---

## Phase overview

| Phase | Delivers | Depends |
| --- | --- | --- |
| **0** | Solver time on EMerge runs (GAPS §1) | none |
| **1** | `activeEngine` + Solver picker + Run chrome (label + pink/orange) | none |
| **2** | Ribbon gate: hide/disable openEMS-only controls when EMerge | Phase 1 |
| **3** | Simulation Settings / ribbon entries open EMerge settings body | Phase 2 |
| **4** | Run wiring: EMerge Run uses active mode; openEMS unchanged | Phase 1 |
| **5** | Mesh-only generate (counts + optional download); no FEM draw yet | Phase 3 |
| **5b** | **E-field cutplane export** (post-solve → Fairbeam field-plane / experimental map; mid-substrate default for planar) | Phase 4 + solve path |
| **6** | FEM mesh overlay in scene (optional follow-on if too large) | Phase 5 |
| **7** | Post tab gating by result schema / engine (enable Field when 5b lands) | Phase 1; revisit after 5b |
| **—** | Optimize-on-EMerge | **deferred** (explicit non-goal) |

---

## Task 1: EMerge solver time on Runs (GAPS §1)

**Model tier:** cheap

**Files:**
- Modify: `python/fairbeam_emerge_worker.py` (timing already started — ensure returned)
- Modify: `python/fairbeam/emerge_bundle.py` (set `run.solver_time_s` / wall fields)
- Test: `python/tests/test_emerge_adapter_*.py` or bundle unit test

**Steps:**

- [x] Confirm worker already measures wall time; map into bundle `run.solver_time_s` (and `wall_time_s` if required by UI fallbacks).
- [x] Add/adjust unit test that a synthetic EMerge result → bundle has finite `solver_time_s > 0`.
- [x] Run: `cd python && python -m unittest discover -s tests -q -k emerge`
- [x] Commit: `fix(emerge): populate solver_time_s for Runs dock`

**Done when:** Runs dock shows a duration for a completed EMerge project/run fixture in tests; manual smoke optional.

---

## Task 2: `activeEngine` session state

**Model tier:** cheap

**Files:**
- Create: `src/designer/activeEngine.ts`
- Test: small unit test if the repo has designer pure-helper tests; else typecheck + story in Task 3

**Interfaces:**
- Produces: `activeEngine(): "openems" | "emerge"`, `setActiveEngine(e)`, `emergeMode(): "emerge-driven" | "emerge-planar" | null`, `setEmergeMode(...)`, default `openems`

**Steps:**

- [x] Implement signals + persistence in-memory for the designer session only.
- [x] Run: `npm run typecheck`
- [x] Commit: `feat(designer): session activeEngine for openEMS vs EMerge`

**Done when:** helpers exist; default is openEMS.

---

## Task 3: Solver picker + Run chrome (color + label)

**Model tier:** mid

**Files:**
- Modify: `src/designer/DesignWorkspace.tsx` (Simulation › Solver / Run groups)
- Modify: `src/styles/designer.css` (+ theme tokens if needed)
- Modify: `src/i18n/en.json`, `tr.json`

**Steps:**

- [x] Add picker UI under Simulation › Solver (next to Experimental solvers): openEMS | EMerge (experimental).
- [x] Run primary button: class `rb-primary` vs `rb-primary-emerge`; accessible name includes engine.
- [x] Do not remove Experimental solvers entry.
- [x] Run: `npm run typecheck`, `npm run check:legal`
- [x] Commit: `feat(designer): engine picker chrome for openEMS and EMerge`

**Done when:** switching picker changes Run accent + label without changing dialog contents yet (or with minimal stub).

---

## Task 4: Ribbon capability gating

**Model tier:** mid

**Files:**
- Modify: `src/designer/DesignWorkspace.tsx`
- Modify: i18n for disable titles

**Steps:**

- [x] When `activeEngine() === "emerge"`: disable Mesh convergence, Far field / Currents / Efficiency / Field plane monitor buttons; disable Optimize group actions with title explaining deferral. **Hide** Solver limits (capability matrix; not disable-in-place).
- [x] Keep Frequency, Boundaries, Mesh settings clickable (wired in Task 5).
- [x] Mesh view: disable with title that FDTD mesh view is openEMS-only (until Task 8); also gate StatusBar mesh toggle.
- [x] Run: `npm run typecheck`, `npm run check:legal`
- [x] Commit: `feat(designer): gate Simulation ribbon by activeEngine` (+ follow-up for matrix hide / StatusBar)

**Done when:** EMerge mode cannot open misleading FDTD-only dialogs from disabled controls; enabled controls still open something sensible (Task 5).

---

## Task 5: EMerge Simulation Settings surface

**Model tier:** mid

**Files:**
- Create: `src/designer/EmergeSimSettings.tsx` (or sections inside `SimSettingsDialog.tsx` if smaller)
- Modify: `SimSettingsDialog.tsx` / `openSimSettings` callers
- Reuse field semantics from `EmergePlanarRun.tsx` / `EmergeAntennaRun.tsx` (do not fork business rules)

**Steps:**

- [x] Frequency / Boundaries / Mesh settings when EMerge: show EMerge parameters (band, points, enclosure, padding, **curated mesh knobs per §6b**, approximate_metals, experimental notes). Persist into session EMerge settings object used by Run (not into openEMS `draft.mesh.cells_per_wavelength` as if they were the same).
- [x] openEMS path unchanged when `activeEngine === "openems"`.
- [x] Run: `npm run typecheck`, `npm run check:legal`
- [x] Commit: `feat(designer): EMerge panels in Simulation Settings`

**Done when:** with EMerge selected, those three ribbon entries edit EMerge run settings; openEMS selection restores classic dialog.

---

## Task 6: Run dialog follows `activeEngine`

**Model tier:** mid

**Files:**
- Modify: `src/designer/RunDialog.tsx`

**Steps:**

- [x] Opening Run with openEMS → current openEMS form.
- [x] Opening Run with EMerge → last `emergeMode` form (`EmergePlanarRun` / `EmergeAntennaRun`); health gates unchanged.
- [x] Changing solver inside Run dialog updates `activeEngine` / mode so chrome stays consistent.
- [x] Elmer options remain selectable inside Run without forcing the main chrome to “Elmer” (chrome stays openEMS or EMerge only per locked decision).
- [x] Run: `npm run typecheck`
- [x] Commit: `feat(designer): Run dialog honors activeEngine`

**Done when:** one click Run from ribbon launches the engine the chrome shows.

---

## Task 7: Post tab gating

**Model tier:** cheap/mid

**Files:**
- Modify: `src/designer/DesignWorkspace.tsx` (Post group)
- Possibly helpers next to existing `ribbonCurrents` / `ribbonFieldPlanes`

**Steps:**

- [x] If focused/latest run is EMerge experimental export: enable Summary / S-params / Smith when data exists; disable Efficiency / Pattern / Currents / Field with engine-specific titles.
- [x] openEMS runs unchanged.
- [x] Run: `npm run typecheck`, `npm run check:legal`
- [x] Commit: `feat(designer): gate Post results by engine capabilities`

**Done when:** EMerge users are not offered empty Post views as if monitors existed.

---

## Task 8: Mesh-only preview (counts first)

**Model tier:** mid

**Files:**
- Modify: worker + API research/emerge endpoint or dedicated mesh-only flag
- Modify: EMerge settings UI “Generate mesh”
- Tests: adapter/worker tests with mesh-only (no `run_sweep`)

**Steps:**

- [x] Worker path: geometry + BCs + `generate_mesh()` → return `{ nodes, tetrahedra, duration_s }` without frequency sweep.
- [x] UI shows counts; still no tet draw.
- [x] Run: targeted unittest + typecheck
- [x] Commit: `feat(emerge): mesh-only generate without solve`

**Done when:** user can mesh without solving and see node/tet counts in Fairbeam.

---

## Task 8b: E-field cutplane → Fairbeam plot (after solve)

**Model tier:** mid

**Files:**
- Modify: `python/fairbeam_emerge_worker.py` (after sweep: `data.find(freq=…).cutplane(…).scalar/vector` with complex metric)
- Modify: `python/fairbeam/emerge_bundle.py` (map into `field_planes` or documented experimental field block the existing Field plane viewer can read)
- Modify: Post / ribbon gating to **enable** Field plane when present
- Tests: synthetic or fixture asserts one cut exists with finite samples; prefer complex so Play can work

**Interfaces:**
- Consumes: solved MW dataset at chosen `freq_hz` (default: band center or peak \|S21\| / min \|S11\| — document choice)
- Produces: at least one XY (or board-parallel) cut; planar default z ≈ substrate mid or top+ε (match EMerge howto style)

**Steps:**

- [x] Confirm cutplane sample dtype is complex; store enough for Magnitude and optional Animate/Play.
- [x] Export one cut in v1; do not require openEMS-style pre-run monitor list.
- [x] UI: when bundle has the cut, Post › Field plane works; Play only if phasors present.
- [x] Run: emerge unittests + `npm run typecheck`
- [x] Commit: `feat(emerge): export mid-plane E-field cut for Results`

**Done when:** after an EMerge experimental run, the user can open a field plot in Fairbeam (not only S-params). Document that the plot is **one frequency**, harmonic (Play = phase), not a full-band FDTD time movie.

**Note:** Surface-current export (`current_boundary`) remains a separate follow-on; E-field cut is the higher-value first field plot.
---

## Task 9 (optional / split plan): FEM mesh overlay

**Model tier:** mid/capable review

**Files:** `Viewport.tsx`, mesh export from worker (surface edges or VTK→JSON), `MeshView.tsx`

**Steps:**

- [x] Only start after Task 8 and human re-approval (payload size, perf).
- [x] Draw wireframe/surface of FEM mesh; never reuse FDTD plane builder for tets.
- [x] Commit boundary separate; may become its own plan file if scope balloons.

**Done when:** Mesh view under EMerge shows the generated FEM mesh on the model.

---

## Task 10: Docs + GAPS

**Model tier:** cheap

**Files:**
- Modify: `docs/agent/GAPS.md`, `docs/EXPERIMENTAL-SOLVERS.md` (short)

**Steps:**

- [x] Mark GAPS §2 as planned → this file; tick phases as they ship.
- [x] Document: active engine is experimental chrome; openEMS default; Optimize deferred.
- [x] Commit: `docs(emerge): solver-scoped UI plan status`

**Done when:** GAPS points here; experimental doc mentions the picker.

---

## Checks (every UI task)

```
npm run typecheck
npm run check:legal
```

When Python changes:

```
cd python && python -m unittest discover -s tests -q -k emerge
```

Before claiming a phase done: smoke in the desktop/designer — switch engine, confirm Run color/label, open one retargeted dialog, run or cancel safely.

---

## Risks

| Risk | Mitigation |
| --- | --- |
| Users think EMerge is production-equal | “Experimental” in picker label + notes; pink accent as distinct cue |
| Settings written into openEMS draft fields | Separate session EMerge settings object; never alias cells/λ ↔ resolution |
| Half-gated ribbon confuses | Phase 2 disable titles must name the reason |
| FEM mesh overlay too heavy | Task 9 optional / separate plan |
| MISSION “don’t rewrite designer around FEM” | Chrome + gating only; geometry pipeline stays admit/reject |
| Legal | No proprietary-solver comparisons in UI strings |

---

## Out of scope (explicit)

- Bundling EMerge in the stock installer
- Optimize / Sweep driving EMerge
- Full Post parity (far field, currents, efficiency) without schema work
- Making Elmer a third chrome accent in this plan
- Claiming openEMS ↔ EMerge S-parameter agreement

---

## First task to run

**Task 1** (solver time) can ship independently. First UI task is **Task 2 → 3**. Do not start Task 9 without a human go.
