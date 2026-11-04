# EMerge Level B2 — Planar two-port filter (hairpin class)

> **For agentic workers:** Use `.cursor/skills/emerge-agent-workflow`. Implement task-by-task with
> checkbox tracking. Planner = capable model; implementer = cheap/mid. Read **Global Constraints**,
> **Shared facts** and **your task only**.

**Goal:** A Fairbeam user can run a single-layer microstrip two-port Design (the hairpin bandpass
filter class: one substrate, ground at the bottom, z-normal copper polygons on top, two microstrip
ports at board edges) through EMerge from the Run dialog, and see experimental S11/S21/S12/S22 in
the shared Results view next to (never instead of) openEMS.

**Architecture:** A new admission module `python/fairbeam/emerge_planar.py` (sibling of
`emerge_design.py`, never imports `emerge`) turns an admitted Design into a neutral metre-based
`kind: "planar"` case. `fairbeam_emerge_worker.py` gets a `solve_planar` branch that rebuilds the
geometry the way the working RFSim script does (substrate `Box`, `XYPolygon` copper, PEC ground,
two `LumpedPort` strip-to-ground terminals). `emerge_bundle.py` gains a two-port exporter that writes
a complete 2 × 2 `results.sparams`. The Run dialog gets an `emerge-planar` option gated by health
`emerge >= 3`.

**Tech stack:** Fairbeam Python + SolidJS/TS; EMerge **2.8.9** managed venv and lock unchanged
(Task 1 gate decides whether that holds); `unittest` + `npm run check:*`.

**Scope level:** B2 (new). Level A and Level B are done and stay as they are. Level B2 widens the
admitted class from "one discrete port antenna" to "planar two-port microstrip circuit". It is still
a bounded, explicitly rejected subset, not general PCB import.

---

## Feasibility evaluation (Planner, 2026-11-04)

**Verdict: feasible, moderate risk. Proceed with a native spike first (Task 1), then implement.**

Evidence read for this evaluation (files, not model statements):

1. A working EMerge hairpin run already exists:
   `D:\WP\RFSim\results\Hairpin comparison\E-merge\run_hairpin_emerge.py` and
   `hairpin_sparams_emerge.csv`. It builds geometry from the same copper polygons as the Fairbeam
   Design (`common/hairpin_spec.json`), with `XYPolygon(...).extrude(0.035 mm)` PEC copper, a
   substrate `Box` (εr 4.34, tanδ 0.0026), `PEC(diel.bottom)`, and two
   `LumpedPort(plate, n, width=2.54 mm, height=1.6 mm, direction=ZAX, Z0=50)` strip-to-ground
   terminals at the board edge, with the domain padded 1 mm in −y so the plates are interior.
   ModalPort was tried and failed on the polygon build (its README).
2. Its recorded result (EMerge **3.0.0b9**, 15 points, 0.75–1.25 GHz): best |S21| −0.62 dB at
   **1.071 GHz**, S11 −52.0 dB there. The RFSim overlay lists Fairbeam (openEMS, pinned 71×62×13
   mesh) best S21 −2.70 dB at **1.086 GHz** on the same geometry. That is a 1.4 % passband-centre
   offset between the two solvers on this geometry. (Other solvers in that bakeoff are not cited in
   Fairbeam docs; see Global Constraints.)
3. Every EMerge API the working script uses exists in the Fairbeam-pinned **2.8.9** managed venv:
   `geo/polybased.py:221 XYPolygon` (`geo`, `extrude`), `geo/shapes.py:34 Alignment`,
   `port_bcs.py:1432 LumpedPort`, `mesher.py:574 set_boundary_size`. Two-port sweeps with
   `grid.S(2, 1)` already run in Fairbeam (Level A fixture, `fairbeam_emerge_worker.py:262-267`).
4. EMerge 2.8.9 assigns PEC to every unassigned exterior boundary
   (`physics/microwave/microwave_3d.py:585`). The working script set no other boundary, so its
   result is a **shielded** (closed PEC box, 8 mm tall) solve. This must be an explicit, recorded
   setting in Fairbeam, not an accident.
5. Fairbeam's bundle already supports an N-port `results.sparams` with a complete matrix
   (`docs/BUNDLE.md` "sparams"); the viewer plots S21 from it. No new results component is
   expected.
6. Fairbeam's hairpin Design (`python/models/hairpin_filter_cgrassin.design.json`, local, not
   committed) uses: 1 dielectric box, a z-flat metal box ground at z = 0, 5 z-normal `polygon`
   copper primitives (`exact: true`, chamfered U-turns) with σ = 5.8e7 S/m and 0.035 mm thickness,
   2 `microstrip` ports (direction y, excitation z, `feed_shift`/`measurement_shift`, 50 Ω).

What blocks the hairpin today: `emerge_design.admit` accepts exactly one lumped port, box primitives
only, and exports S11 only. Every other piece (venv, worker process, queue, bundle, Results view)
is reusable.

Main risks (owned by tasks below):

- **Version gap.** The working run is EMerge 3.0.0b9 (beta); Fairbeam pins 2.8.9 (license-reviewed,
  locked). Task 1 reproduces the run on 2.8.9. If 2.8.9 cannot, the Planner decides between a
  separate version-bump plan (license recheck, new lock, Level A/B re-runs) and stopping.
- **Port model.** Lumped strip-to-ground terminals at the board edge are not openEMS's microstrip
  port with feed/measurement planes. Magnitudes are comparable; phase reference differs. Accepted
  explicitly by the user per run and recorded.
- **Enclosure.** Shielded vs open (absorbing) boundaries change results; Task 1 measures both.
- **Mesh size.** The 0.254 mm coupling gap drives tetrahedron count and time. Task 1 freezes limits.
- **Scope creep.** Multilayer, vias, CPW, more than two ports and arbitrary PCB import stay out.

Effort: about the size of Level B (one spike, three code tasks, one UI task, native runs, docs).

---

## Global Constraints

Copy this block verbatim into implementer and reviewer prompts.

- openEMS remains the default solver. No default, menu order or first-run change in favor of
  EMerge. `emerge-planar` sits after `emerge-driven` in the Run dialog.
- EMerge is opt-in experimental only; never bundled, never installed without explicit user action.
  Reuse the Level A managed venv and lock unless Task 1's gate records a Planner decision otherwise.
- License posture: EMerge runs only in a separate Python process. No Fairbeam process imports
  `emerge`, `gmsh` or `emsutil`; only `python/fairbeam_emerge_worker.py` does. `emerge_planar.py`
  and `emerge_bundle.py` import neither. Do not copy EMerge source into this repository.
- **Reject, never coerce.** Anything outside the admitted subset raises `ValueError` with a clear
  message. The only allowed rewrites are explicit, user-accepted ones: `approximate_metals`
  (finite-conductivity copper → PEC) and `accept_lumped_terminals` (each microstrip port becomes a
  lumped strip-to-ground terminal at its board-edge face; `feed_shift`, `measurement_shift` and
  `termination` are not used). Both are recorded in the result's `limitations`.
- Do not edit Elmer files or the Level B path (`emerge_design.py`, `EmergeAntennaRun.tsx`) except
  shared lines a task names (`research.py`, `server.py`, `RunDialog.tsx`, `api.ts`,
  `fairbeam_emerge.py`, `fairbeam_emerge_worker.py`, `emerge_bundle.py`). Level A and Level B tests
  must keep passing unchanged.
- Results stay experimental: status `results_exported`, `precision_converged: false`,
  `gain_qualified: false`, `farfield: []`. Never `results_validated`.
- Phasor convention `exp(+i omega t)`, no conjugation (Level A/B evidence). If Task 1 finds
  otherwise, `BLOCKED`.
- Numbers and limits in Shared facts are Planner-owned. Implementers report `BLOCKED` instead of
  changing them.
- UI strings in both `src/i18n/en.json` and `src/i18n/tr.json`; decimal points; "Fairbeam".
- `npm run check:legal` must pass. Fairbeam docs compare EMerge only with Fairbeam's own openEMS
  run. Third-party proprietary solver results from the RFSim bakeoff are never quoted in Fairbeam
  docs, UI or commits.
- Numbers in docs come only from artifacts of reproducible runs. One simulation at a time; coarse
  first.
- Do not commit personal files from `python/models/`. The test fixture is a new file under
  `python/tests/fixtures/`.
- Branch `feat/emerge-experimental`. `Co-Authored-By:` trailer naming the model.

---

## Shared facts

**Admitted subset (`emerge_planar.admit`)** — checked in this order, first failure raises:

- `check_design` passes; parameters resolved with `resolve_names` / `resolve_parts` (same as
  `emerge_design.py`).
- Exactly **two** ports, both `type: "microstrip"`, propagation `direction` in `x`/`y`,
  `excitation_direction` `z`, real positive `reference_ohm`, conductor a metal material. Port
  numbers 1 and 2. Any other port type or count → reject ("Planar EMerge needs exactly two
  microstrip ports").
- No `resistors`, `lumped_elements`, `transforms`, `cuts`, `voids`.
- Exactly **one** dielectric part with one axis-aligned `box` primitive (the substrate), z from
  `z0` to `z0 + h`, h > 0; isotropic `eps_r`, `mu_r`, `tan_d` (requires `tan_d_freq`, as Level B).
- **Ground:** either a metal z-flat `box` at `z0` covering the full substrate footprint, or
  `simulation.boundaries[4]` (z−) is `PEC` with the substrate bottom on the domain floor. Either way
  the worker applies `PEC` on the substrate bottom face. Anything else → reject.
- **Traces:** metal primitives that are `polygon` with `normal: "z"` and `elevation` equal to the
  substrate top, or z-flat `box` at the substrate top. Polygons are simple (no holes, no arcs, ≥ 3
  vertices). Any metal elsewhere (other elevation, volume, cylinder, via) → reject.
- Finite `conductivity`/`thickness` on trace metal requires `approximate_metals: true` (PEC sheet).
- **Terminals:** for each port, the port box's face at its propagation `start` must lie on the
  substrate edge; its transverse in-plane extent is the strip width; a trace must cover that face's
  top edge across the full width. The terminal is a plate on that face from substrate bottom to
  top, width = strip width, `direction` +z, `Z0 = reference_ohm`.
- Points: int 3–41 (frozen Task 1). Band 1 MHz–100 GHz, `f_min < f_max`.

**Settings** (exact key set, anything else rejected):
`analysis: "planar_two_port"`, `accept_lumped_terminals: true`, `enclosure: "shielded" | "open"`,
`air_height_mm` (> 0, above the substrate top), `padding_mm` (> 0; only with `open`, rejected with
`shielded`), `resolution: "coarse" | "fine"`, `f_min_hz`, `f_max_hz`, `points`,
`approximate_metals` (bool, default false).

**Domain:** substrate footprint, plus `PORT_PAD_MM` beyond each terminal face (keeps the plate
interior, as the working script's 1 mm pad), plus `padding_mm` on the four side faces and the top
when `open`. Floor = substrate bottom (PEC). `shielded`: all other exterior faces are left to
EMerge's default PEC. `open`: `AbsorbingBoundary` (order 2, `"B"`, Level B defaults) on the four
sides and the top.

**Planner-owned constants (frozen Task 1, 2026-11-04):** `PORT_PAD_MM = 1.0`;
resolutions `coarse = 0.25`, `fine = 0.15` (Level B values); metal edge mesh size
`set_boundary_size(trace, METAL_EDGE_MM = 0.4 mm, growth_rate = 3.0)`; **trace model =
zero-thickness PEC `XYPolygon.geo()` sheets** (Run B vs A: sheets ~half mesh, passband still
present on short grid; extrusion kept only as spike reference, not the worker default);
timeout **3600 s** (Run D skipped; extrapolated from Run B wall 311 s × 41/5 × 1.3 ≈ 55 min,
plus Run A extruded 15-pt ~40 min headroom); resource proxy limit **400000** tetrahedra
(observed max: Run A 202258; sheet runs ~110k). Full-band / 41-pt re-measurement deferred to
after Task 6; adjust these constants only with new Evidence-log numbers.

**Result schema** `fairbeam.emerge-planar-result/1`:
`{schema, status: "results_exported", frequency_hz, s: {"1,1"|"2,1"|"1,2"|"2,2": {re, im}},
z_ref: [z1, z2], enclosure, settings, mesh: {nodes, tetrahedra}, elapsed_seconds,
phasor_convention, native_phasor_convention, precision_converged: false, gain_qualified: false,
limitations, pec_approximations}`. Checks: frequencies equal the settings linspace; all finite;
every |S_ij| ≤ 1.01; column power |S11|² + |S21|² ≤ 1.02 and |S12|² + |S22|² ≤ 1.02 (lossy
passive network); reciprocity |S21 − S12| ≤ 0.02 (reported, failure → `results_exported` refused).

**Reference design class:** the hairpin test fixture
`python/tests/fixtures/emerge_hairpin.design.json` (built from the RFSim `hairpin_spec.json`
values: 50.828 × 58 mm FR4-like substrate 1.6 mm, εr 4.34, tanδ 0.0026 at 0.95 GHz, five copper
polygons, two microstrip ports at y = −29 mm) and small dimensional edits of it.

---

## File map

| File | Responsibility |
| --- | --- |
| `python/fairbeam/emerge_planar.py` | Admission + neutral `kind: "planar"` case (metres); no `emerge` import |
| `python/tests/fixtures/emerge_hairpin.design.json` | Reference hairpin Design (two microstrip ports) |
| `python/tests/test_emerge_planar.py` | Admission tests (no EMerge) |
| `python/fairbeam_emerge_worker.py` | `solve_planar`, `build_planar_raw`, dispatch on `kind` |
| `python/fairbeam_emerge.py` | `run_planar`, `assess_planar`, CLI `planar --experimental --case --out` |
| `python/fairbeam/emerge_bundle.py` | `planar_result_bundle(design, result)` with 2 × 2 `sparams` |
| `python/fairbeam/research.py`, `python/fairbeam/server.py` | Routing; health `"emerge": 3` |
| `src/designer/EmergePlanarRun.tsx`, `src/designer/RunDialog.tsx`, `src/runner/api.ts` | Run form + option |
| `src/i18n/en.json`, `src/i18n/tr.json` | `emergePlanar.*` |
| `scripts/check-emerge-planar-ui.mjs`, `package.json` | Synthetic UI check |
| `docs/agent/SCOPE.md`, `docs/EMERGE-EXPERIMENT.md`, `docs/EXPERIMENTAL-SOLVERS.md`, `docs/tr/EXPERIMENTAL-SOLVERS.md`, `docs/RESEARCH-SOLVERS.md` | Scope + user docs |

---

## Task 1: Scope record and native spike on EMerge 2.8.9 (human-gated)

**Model tier:** mid (Integrator). **Human gate:** ask before each native run. One run at a time.

**Files:** `docs/agent/SCOPE.md` (add Level B2 under B with the human decision of 2026-11-04),
this plan (Evidence log, Shared facts constants). Spike script lives outside the repo
(`%TEMP%\fairbeam-emerge-planar-spike\spike.py`) and is not committed.

**Steps:**

- [x] SCOPE: add "B2 — planar two-port microstrip (hairpin class)" with the admitted subset
  summary and "human decision 2026-11-04: integrate the hairpin class". C stays out of scope.
- [x] Port `run_hairpin_emerge.py` to the 2.8.9 managed venv
  (`%LOCALAPPDATA%\org.fairbeam.desktop\emerge\2.8.9`) unchanged in physics: same polygons, same
  ports, `check_version` removed, raw S kept (`mw_cap_sp_single/col = False`, `mw_recip_sp =
  False` as in the worker).
- [x] Run A (shielded, extruded 0.035 mm copper, 15 points): record best |S21| frequency and dB,
  S11 there, mesh nodes/tets, wall time. Gate: best-S21 frequency within ±3 % of 1.071 GHz (the
  3.0.0b9 result). Fail → `BLOCKED` to Planner (version decision), stop the plan.
- [x] Run B: same, copper as zero-thickness `XYPolygon.geo()` + `PEC` sheets.
  (short protocol: 5 pts 0.95–1.15 GHz; full-band deferred)
- [x] Run C: run B with `open` enclosure: `padding_mm = 10`, ABC on sides/top.
  (short protocol: 5 pts 0.95–1.15 GHz; full-band deferred)
- [x] Run D: **skipped** (human 2026-11-04). Timeout/resource frozen by extrapolation from B;
  full 41-pt / full-band fine deferred to end (Task 6+ long-sim note below).
- [x] Planner (same task, capable model): freeze trace model, `PORT_PAD_MM`, `METAL_EDGE_MM`,
  point limit, timeout and resource proxy from these runs; write them into Shared facts.
- [x] Commit: `Scope EMerge planar two-port and record the 2.8.9 hairpin spike`
  (`5b599bb`; checkbox marked after that commit)

**Done when:** Shared facts constants are frozen from recorded runs, or the plan is `BLOCKED` on the
version decision.

---

## Task 2: Admission `emerge_planar.py`

**Model tier:** mid. Read `emerge_design.py` and `planar.py:30-95` (`resolved_planar`).

**Files:** `python/fairbeam/emerge_planar.py`, `python/tests/fixtures/emerge_hairpin.design.json`,
`python/tests/test_emerge_planar.py`

**Interfaces:**
- Produces: `admit(design: dict, settings: dict) -> dict` returning
  `{"kind": "planar", "substrate": {"lo", "hi", "eps_r", "mu_r", "tan_d"}, "traces": [{"xy": [[x, y], ...], "z": float}],
  "ground_z": float, "terminals": [{"number", "lo", "hi", "width", "height", "z0"}],
  "air": {"lo", "hi"}, "enclosure": "shielded"|"open", "frequencies_hz": [...], "resolution": float,
  "resolution_name": str, "metal_edge_m": float, "phasor_convention_out": "exp(+i omega t)",
  "limitations": [...], "pec_approximations": [...]}` — all lengths in metres; box traces become
  4-vertex polygons.

**Steps:**

- [x] Fixture: hairpin Design from the Reference design class values (copy polygons from the RFSim
  `hairpin_spec.json`; ports as in the local Fairbeam hairpin Design).
- [x] Tests first: fixture admitted with `approximate_metals: true`; rejected without it; terminal
  1 plate at y = −29 mm spans x −15.414…−12.874 mm and z 0…1.6 mm; air floor = substrate bottom;
  shielded domain has 1 mm pad in −y only beyond the terminals; `open` adds `padding_mm` on sides
  and top; input not mutated.
- [x] Reject tests (one each): one port, three ports, a lumped port, a cpw port, port with
  `direction: "z"`, port face not on substrate edge, terminal edge not covered by a trace, resistor,
  transform, cut, polygon at wrong elevation, polygon with `normal: "x"`, metal box with volume,
  two dielectric boxes, missing ground, `padding_mm` with `shielded`, missing `padding_mm` with
  `open`, unknown setting, `accept_lumped_terminals: false`, `points` 2 and 42, `f_min >= f_max`,
  too-large domain.
- [x] `ast` isolation test: no `emerge`, `gmsh`, `emsutil` imports.
- [x] Run `cd python && python -m unittest discover -s tests -p "test_emerge_*.py" -q` → pass.
- [x] Commit: `Admit planar two-port microstrip Designs for EMerge`
  (`92a4788`; checkbox marked after that commit)

**Done when:** admission tests pass without EMerge; Level B tests unchanged.

---

## Task 3: Worker and adapter planar path

**Model tier:** mid. Mirror `solve_design` / `run_design`; physics from the Task 1 spike.

**Files:** `python/fairbeam_emerge_worker.py`, `python/fairbeam_emerge.py`,
`python/tests/test_emerge_adapter_planar.py`

**Interfaces:**
- Consumes: Task 2 case dict.
- Produces: worker `solve_planar(case) -> dict` writing raw `{"kind": "planar", "s": {...},
  "frequency_hz", "mesh", "emerge_version", "native_phasor_convention", ...}`;
  adapter `run_planar(out, case, *, root=None, experimental=False) -> dict` and
  `assess_planar(raw, case) -> dict` returning the Shared facts result schema.

**Steps:**

- [x] Worker: `kind == "planar"` dispatch; build substrate `Box`, traces with the frozen trace
  model, `background()` air box, terminal `Plate`s; after `commit_geometry`: `PEC` on substrate
  bottom, ABC on sides/top only when `open`, PEC trace BCs (if sheets), two `LumpedPort`s
  (+z, `Z0`), `set_boundary_size` on traces; same single-process sweep and raw-S settings as
  `solve_design`. Extract all four `grid.S(i, j)`.
- [x] Adapter: `run_planar` with `run_design`'s discipline (fresh dir, manifest per status, worker
  copy + SHA-256, isolated interpreter flags, thread env, frozen timeout, `worker.log` kept).
  `assess_planar` enforces every Shared facts check. CLI `planar` subcommand.
- [x] Tests (no EMerge): opt-in required, existing out dir refused, failure/timeout keep logs;
  `assess_planar` rejects wrong frequencies, non-finite S, |S21| = 1.02, column power 1.03,
  |S21 − S12| = 0.05, wrong convention; Level A/B worker tests unchanged.
- [x] Run `-p "test_emerge_*.py"` → pass.
- [x] Commit: `Add the EMerge worker path for planar two-port Designs`
  (`8a3a4fb`; checkbox marked after that commit)

---

## Task 4: Research wiring and two-port bundle

**Model tier:** mid.

**Files:** `python/fairbeam/emerge_bundle.py`, `python/fairbeam/research.py`,
`python/fairbeam/server.py`, `python/tests/test_emerge_bundle.py`,
`python/tests/test_emerge_research.py`

**Interfaces:**
- Produces: `planar_result_bundle(design: dict, result: dict) -> dict`.

**Steps:**

- [x] `research.prepare`: `backend == "emerge"` and `settings.analysis == "planar_two_port"` →
  `emerge_planar.admit`; existing fixture and driven paths unchanged. `execute` →
  `run_planar`; `validate_result` branch for `fairbeam.emerge-planar-result/1`; bundle written like
  Level B.
- [x] `planar_result_bundle`: engine `EMerge`, method `Frequency-domain FEM (experimental)`,
  boundaries per enclosure (`PEC` floor; `PEC` or `Second-order absorbing` elsewhere), `run: None`,
  `experimental` block, `results.sparams = {ports: [1, 2], z_ref, excited: [1, 2], complete: true,
  method: "FEM driven, all ports", s: {...}}`, `results.ports["1"|"2"]` with each diagonal S and
  Zin, `farfield: []`, no conjugation.
- [x] Before writing: confirm in `src/lib/sparams.ts` and the Results view that this `sparams`
  shape plots S21 and a two-port with empty far field renders. If not, `BLOCKED`.
- [x] `server.py`: health `"emerge": 3` (Level B UI gates on `>= 2`, still shown).
- [x] Tests: bundle `sparams.s["2,1"]` equals the input; `complete` true; Zin on a known S11;
  research admits the fixture against a fake venv; health 3; Level A/B tests unchanged.
- [x] Run `-p "test_emerge_*.py"`, `-p "test_research_*.py"` → pass.
- [x] Commit: `Wire EMerge planar two-port runs into research and shared results`
  (`27cdd38`; checkbox marked after that commit)

---

## Task 5: Run dialog UI

**Model tier:** mid. Mirror `EmergeAntennaRun.tsx` and `check-emerge-antenna-ui.mjs`.

**Files:** `src/designer/EmergePlanarRun.tsx`, `src/designer/RunDialog.tsx`, `src/runner/api.ts`,
`src/i18n/en.json`, `src/i18n/tr.json`, `scripts/check-emerge-planar-ui.mjs`, `package.json`

**Steps:**

- [x] Option `emerge-planar` ("EMerge FEM · Experimental planar two-port") after `emerge-driven`,
  only when `health.emerge >= 3`.
- [x] Form: required `accept_lumped_terminals` checkbox (text: each microstrip port becomes a
  lumped strip-to-ground terminal at the board edge for this run only; feed and measurement shifts
  unused; the saved Design and openEMS settings stay unchanged), enclosure select with a one-line
  explanation of each, air height, padding (only for open), resolution, band, points,
  `approximate_metals`. Show limitations before submit: experimental, not a convergence
  certificate, reference plane at the board edge, no far field.
- [x] i18n `emergePlanar.*` in both languages.
- [x] Check script: hidden without `emerge: 3`; acceptance required; padding hidden and not sent
  with `shielded`; submitted body shape; EN and TR.
- [x] Run `npm run typecheck`, `npm run check:i18n`, `npm run check:legal`,
  `npm run check:emerge-planar`, `npm run check:emerge-antenna`, `npm run check:research`.
- [x] Commit: `Add the experimental EMerge planar two-port option to the Run dialog`
  (`79ad5c0`; checkbox marked after that commit)

---

## Task 6: Native runs through Fairbeam (human-gated)

**Model tier:** mid. One simulation at a time.

**Deferred long-sim note (human 2026-11-04):** Task 1 skipped Run D and used short B/C spikes.
After the Fairbeam planar path works, re-run **full-band** shielded/open sheet cases (15+ pts,
0.75–1.25 GHz) and optionally a **41-pt** timing case; if timeout, resource proxy, or sheet-vs-
extruded conclusions change, update Shared facts and code from those Evidence-log numbers only.

**Steps:**

- [x] Fixture through the CLI `planar` subcommand: shielded coarse, shielded fine, open coarse
  (settings from frozen Shared facts, band 0.75–1.25 GHz). Prefer short/coarse first; then the
  deferred full-band long runs above.
  (short shielded coarse + full-band shielded coarse/fine + open coarse; Evidence log Runs 1–4)
- [x] Same fixture through the normal Fairbeam openEMS Run path (default settings). Record its best
  |S21| frequency/dB from its bundle.
  (GPU runtime; Evidence log Run 5 — note non-physical |S21|>1 / port-1-only)
- [x] One end-to-end run from the Run dialog (managed venv, queue, Results view shows S21).
  (job `20261104-191921-204dbc`; Evidence log Run 6. Source-binding + project-bundle publish
  gates for `planar_two_port` were missing; fixed in `server.py` / `jobs.py` /
  `document_workspace.py` before Results publish.)
- [x] Evidence log per run from result/manifest files only: best |S21| f and dB, S11 there, max
  |S_ij|, column power max, reciprocity max, mesh, elapsed, status, leftover processes.
  (Runs 1–6 logged)
- [x] Any check failure or timeout → `BLOCKED` with logs. Do not change limits.
  (none; Run 6 exported clean)
- [x] Commit: `Record native EMerge planar two-port runs`
  (`04f3113`; checkbox marked after that commit)

---

## Task 7: Planner freeze and documentation

**Model tier:** Planner for the statement, cheap for the doc edits. Numbers from Task 6 only.

**Steps:**

- [x] Write the qualification statement for the hairpin class (e.g. passband-centre offset vs
  Fairbeam openEMS and coarse→fine shift, as measured). No `results_validated`.
  (EMerge planar peak 1.071429 GHz; coarse→fine shift 0; openEMS default path non-physical
  |S21|>1 — no S-parameter agreement claim. Written into `docs/EMERGE-EXPERIMENT.md`.)
- [x] Docs: admitted subset, rejects, settings, enclosure meaning, limitations, the recorded result
  and the Fairbeam openEMS comparison. Run `npm run check:legal`, `npm run check:links`,
  `npm run check:site`.
- [x] Commit: `Document the experimental EMerge planar two-port subset`
  (`be49670`; checkbox marked after that commit)

---

## Task 8: Whole-branch review

**Model tier:** Planner.

- [ ] Review against Global Constraints with `docs/agent/prompts/reviewer.md`; AGENTS.md pre-PR
  checks in a clean worktree (local `public/projects/*` and `python/models/*` files distort
  `check:designer` / `check:site`).
- [ ] Mark B2 done; record open qualification gaps.

---

## Review Focus

- A hairpin whose port box `start` is the inner end (ports drawn pointing outward): admission must
  pick the face on the substrate edge or reject, never place the terminal mid-board.
- Polygons that only touch (shared edge between feed and resonator at the 0.254 mm gap side) or
  overlap: gmsh fragmenting must not merge or drop a trace; Task 3 test asserts trace count in the
  raw mesh report equals the admitted count.
- Port numbering: Design port 2 with `excite: false` must still be a driven column in FEM; the
  bundle `excited` is `[1, 2]` and the UI must not suggest port 2 was a passive load.
- `shielded` box resonances inside the band can mimic filter features; the enclosure is always
  shown in the result header and limitations.
- A user's Design with mm-level parameters (expressions like `sub_h`) must evaluate exactly as the
  openEMS path does; Task 2 includes a parameterised variant of the fixture.

---

## Evidence log

Fill only with commands run and outputs observed. Date every entry.

- 2026-11-04 (Planner): Feasibility evidence above was read from files; no EMerge run was made for
  this plan. API presence in 2.8.9 checked by text search of the managed venv `site-packages`.
- 2026-11-04 Run A (managed EMerge 2.8.9, `%TEMP%\fairbeam-emerge-planar-spike\spike.py A`):
  shielded, extruded 0.035 mm copper, 15 pts 0.75–1.25 GHz. best |S21| **1.071429 GHz**,
  S21 **−0.62 dB**, S11 **−52.01 dB**; offset vs 1.071 GHz **+0.040%** (gate pass ≤3%).
  mesh nodes=34422 tetrahedra=202258; wall_seconds=2377.2; max |S21|=0.9316;
  max |S21−S12|=3.0e−5. Artifacts: `hairpin_spike_A.csv`, `hairpin_spike_A_summary.json`.
- 2026-11-04 (human): After Run A gate pass, remaining Task 1 spikes use a **short protocol**
  (B/C: 5 pts over 0.95–1.15 GHz; D: light denser sweep or extrapolated timeout). Full-band
  fine / 41-pt timing deferred until the Fairbeam planar path exists (Task 6+), then re-run
  and adjust Shared facts or code if needed. Does not change Level B2 admitted subset.
- 2026-11-04 Run B (short): sheet copper, shielded, 5 pts 0.95–1.15 GHz. On this coarse grid
  best |S21| at **1.05 GHz**, S21 **−0.86 dB**, S11 **−17.58 dB** (grid has no 1.071 sample;
  A’s peak was −0.62 dB at 1.071). mesh nodes=19197 tetrahedra=109892 (~half of A);
  wall_seconds=311. Sheets look viable for the frozen trace model. Artifacts: `hairpin_spike_B.*`.
- 2026-11-04 Run C (short): sheets + open (padding_mm=10, ABC sides/top), 5 pts 0.95–1.15 GHz.
  best |S21| **1.05 GHz**, S21 **−0.69 dB**, S11 **−26.88 dB**. mesh nodes=19427
  tetrahedra=111439; wall_seconds=382 (slightly slower than B). Both enclosures usable.
  Artifacts: `hairpin_spike_C.*`.
- 2026-11-04 (human): **Skip Run D.** Freeze timeout 3600 s and resource proxy 400000 by
  extrapolation from B (faster); defer full-band / 41-pt long sims to Task 6+. Shared facts
  frozen: sheets, PORT_PAD_MM=1.0, METAL_EDGE_MM=0.4, points 3–41, coarse=0.25, fine=0.15.
- 2026-11-04 Task 6 Run 1 (CLI `planar`, managed EMerge 2.8.9): fixture
  `emerge_hairpin.design.json`, shielded coarse sheets, short protocol 5 pts 0.95–1.15 GHz,
  air_height_mm=6.4, approximate_metals. status **results_exported**; best |S21|
  **1.050 GHz**, S21 **−0.82 dB**, S11 **−19.55 dB**; max |S_ij|=0.990; max col power=0.980;
  max |S21−S12|=3.9e−5; mesh nodes=19194 tetrahedra=109920; elapsed_seconds=338.0.
  Matches spike B shape (B: −0.86 dB / −17.58 dB at 1.05 GHz, 109892 tets, 311 s).
  Artifacts: `%TEMP%\fairbeam-emerge-planar-task6\run_shielded_coarse_short\`
  (`result.json`, `manifest.json`, `summary.csv`, `summary.json`, `sparams.png`, `worker.log`).
- 2026-11-04 Task 6 Run 2 (CLI `planar`): shielded coarse sheets, **full-band** 15 pts
  0.75–1.25 GHz. status **results_exported**; best |S21| **1.071429 GHz**, S21 **−0.63 dB**,
  S11 **−30.45 dB**; max |S_ij|=0.996; max col power=0.993; max |S21−S12|=4.2e−5;
  mesh nodes=19147 tetrahedra=109584; elapsed_seconds=971.7. Aligns with spike A peak
  frequency (1.071429 GHz) and S21 (−0.62 dB). Artifacts:
  `%TEMP%\fairbeam-emerge-planar-task6\run_shielded_coarse_fullband\`
  (`result.json`, `sparams.png`, `summary.json`, `worker.log`).
- 2026-11-04 Task 6 Run 3 (CLI `planar`): shielded **fine** sheets, full-band 15 pts
  0.75–1.25 GHz. status **results_exported**; best |S21| **1.071429 GHz**, S21 **−0.63 dB**,
  S11 **−31.27 dB**; max |S_ij|=0.996; max col power=0.993; max |S21−S12|=4.0e−5;
  mesh nodes=19164 tetrahedra=109714 (~same as coarse; metal-edge size dominates);
  elapsed_seconds=1054. Coarse→fine peak shift ≈ 0. Artifacts:
  `%TEMP%\fairbeam-emerge-planar-task6\run_shielded_fine_fullband\`
  (`result.json`, `sparams.png`, `summary.json`, `worker.log`).
- 2026-11-04 Task 6 Run 4 (CLI `planar`): **open** coarse sheets, full-band 15 pts,
  padding_mm=10. status **results_exported**; best |S21| **1.071429 GHz**, S21 **−0.51 dB**,
  S11 **−34.20 dB**; max |S_ij|=0.999; max col power=0.999; max |S21−S12|=2.0e−5;
  mesh nodes=19441 tetrahedra=111586; elapsed_seconds=1055. Same peak frequency as
  shielded; slightly lower insertion loss. Artifacts:
  `%TEMP%\fairbeam-emerge-planar-task6\run_open_coarse_fullband\`
  (`result.json`, `sparams.png`, `summary.json`, `worker.log`).
- 2026-11-04 Task 6 Run 5 (Fairbeam openEMS GPU, default design settings): fixture
  `emerge_hairpin.design.json` via `fairbeam run --engine gpu --threads auto`
  (gpu-runtime openEMS). `converged=True`, timesteps=614535, solver_time_s=107.4,
  wall_time_total_s=109.8, mesh_total_cells=145152, `sparams.complete=false`
  (excited=[1] only; design port 2 `excite: false`). From bundle: best |S21|
  **1.025625 GHz**, S21 **+5.07 dB** (non-physical; column power max reported 3.40),
  S11 there **−7.27 dB**; Fairbeam band note min S11 **−13.4 dB** @ **1.024 GHz**.
  Artifacts: `%TEMP%\fairbeam-emerge-planar-task6\run_openems_gpu\`
  (`emerge-hairpin-openems-gpu.json`, `sparams.png`, `summary.json`).
  Concern: |S21|>1 on this default one-port-excitation path; RFSim bakeoff cited
  Fairbeam openEMS best S21 −2.70 dB @ 1.086 GHz on pinned mesh — different setup.
- 2026-11-04 Task 6 Run 6 (Run dialog → emerge-planar, managed EMerge 2.8.9): fixture
  `emerge_hairpin`, shielded coarse sheets, short protocol 5 pts 0.95–1.15 GHz,
  air_height_mm=6.4, approximate_metals, accept_lumped_terminals. job
  `20261104-191921-204dbc`. First submit failed until `planar_two_port` source
  binding was allowed (`server.py` / `jobs.py`). status **results_exported**;
  best |S21| **1.050 GHz**, S21 **−0.82 dB**, S11 **−19.55 dB**; max |S_ij|=0.990;
  max col power=0.980; max |S21−S12|=3.9e−5; mesh nodes=19194 tetrahedra=109920;
  elapsed_seconds=320.0; leftover fairbeam_emerge_worker processes=0. Matches
  CLI Run 1 / spike B. Bundle has `sparams.complete=true` and `s["2,1"]` (5 pts);
  project publish initially skipped (`jobs.py` only listed driven schemas) — fixed
  to include `fairbeam.emerge-planar-result/1` (+ `document_workspace.py`), then
  published `public/projects/emerge-20261104-191921-204dbc.json`. Results load
  confirmed S21 present (engine EMerge, complete true).
  Artifacts: `.sim/jobs/20261104-191921-204dbc/` (`result.json`, `bundle.json`,
  `worker.log`, `manifest.json`);
  `public/projects/emerge-20261104-191921-204dbc.json`.
