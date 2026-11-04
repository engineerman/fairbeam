# EMerge Level B — Bounded Design subset (one driven discrete port)

> **For agentic workers:** Use `.cursor/skills/emerge-agent-workflow`. Implement task-by-task with
> checkbox tracking. Planner = capable model; implementer = cheap/mid. Read **Global Constraints**,
> **Shared facts** and **your task only**.

**Goal:** A Fairbeam user can run the current Design through EMerge when it is made only of
axis-aligned dielectric boxes, PEC sheets and one discrete port, and see the experimental S11 in the
shared Results view, next to (never instead of) openEMS.

**Architecture:** Mirror the Elmer driven path. `python/fairbeam/emerge_design.py` (like
`elmer_driven.py` without its mesher) admits the Design and turns it into a neutral, metre-based
case JSON; it never imports `emerge`. `fairbeam_emerge.py` gains a `run_design` path that hands that
case to `fairbeam_emerge_worker.py` in the EMerge venv, exactly like `run_fixture`. EMerge meshes
with gmsh inside the worker. `python/fairbeam/emerge_bundle.py` (like `elmer_bundle.py`) exports S11
and Zin into the shared Results bundle. The Run dialog gets an `emerge-driven` option (like
`elmer-driven`).

**Tech stack:** Fairbeam Python + SolidJS/TS; EMerge 2.8.9 in the Level A managed venv (lock
unchanged); `unittest` + `npm run check:*`.

**Scope level:** B. Level A (`2026-11-04-emerge-level-a-fixture.md`) is done and stays as is.

---

## Global Constraints

Copy this block verbatim into implementer and reviewer prompts.

- openEMS remains the default solver. No default, menu order or first-run flow changes in favor of
  EMerge. The `emerge-driven` Run option sits after the Elmer options.
- EMerge is opt-in experimental only. It is never bundled in the installer and never installed
  without an explicit user action. Level B reuses the Level A managed venv and lock unchanged.
- License posture: EMerge runs only in a **separate Python process**. No Fairbeam process imports
  `emerge`, `gmsh` or `emsutil`; only `python/fairbeam_emerge_worker.py` does. `emerge_design.py`
  and `emerge_bundle.py` live in the `fairbeam` package and import neither. Do not copy EMerge
  source into this repository.
- **Reject, never coerce.** Anything outside the admitted subset in "Shared facts" raises
  `ValueError` with a clear message. Never drop a part, property, port or element silently. The
  only allowed rewrite is the explicit, user-accepted `approximate_metals` (same as Elmer) and the
  explicit, user-accepted finite feed width.
- Do not edit Elmer production files (`elmer_driven.py`, `elmer_bundle.py`, `fem_geometry.py`,
  `ElmerAntennaRun.tsx`, `ElmerAntennaResults.tsx`). Shared lines named by a task are the
  exception (`research.py`, `server.py`, `RunDialog.tsx`, `api.ts`).
- Results stay experimental: status `results_exported`, `precision_converged: false`,
  `gain_qualified: false`, no far field in Level B. Never `results_validated` for a Design run.
- Phasor convention in Fairbeam frames is `exp(+i omega t)`. EMerge 2.8.9 is natively
  `exp(+i omega t)` (Level A evidence log), so `emerge_bundle.py` does **not** conjugate. Record the
  convention in the bundle. If a task finds otherwise, `BLOCKED`.
- Acceptance numbers and limits in "Shared facts" are owned by the Planner. An implementer must not
  change them to make a run pass; report `BLOCKED` instead.
- UI strings need entries in both `src/i18n/en.json` and `src/i18n/tr.json` (glossary:
  `docs/i18n-glossary.md`; Discrete port = Ayrık port, Solid = Katı). Numbers use a decimal point.
  Product name is "Fairbeam". No hardcoded English in TSX.
- `npm run check:legal` must pass. No comparisons with proprietary solvers. Comparing with
  Fairbeam's own openEMS run is allowed and expected.
- Numbers in docs come only from artifacts of a reproducible run. A model's statement is never
  evidence. Simulations: one at a time; coarse first.
- Branch `feat/emerge-experimental`. Commit with a `Co-Authored-By:` trailer naming the model.

---

## Shared facts (verified 2026-11-04 by the Planner)

**EMerge 2.8.9 API used (read in the managed venv, `Lib/site-packages/emerge/_emerge/`):**

- `LumpedPort(face, port_number, width, height, direction, power=1, Z0=50)`
  (`physics/microwave/bcs/port_bcs.py:1432`). Uniform E along `direction`; `width`/`height` in
  metres; `height` is the extent along `direction`.
- `AbsorbingBoundary(face, order=2, origin=None, abctype="B")`
  (`physics/microwave/bcs/boundary_conditions.py:125`). The docstring says only first order is
  supported while the default is `order=2`. **Task 2 (2026-11-04):** assembler applies the
  second-order correction when `bc.order == 2` (`assembler.py:668-675`, `:1025-1030`,
  `:1268-1273`). Level B therefore runs the constructor defaults (`order=2`, `abctype="B"`).
- `PEC(face)` (`boundary_conditions.py:39`), `geo.Box` (`geo/shapes.py:52`), `geo.Plate(origin, u,
  v)` (`geo/shapes.py:233`), `XYPlate` (`:193`), `GeoObject.set_material(Material)`
  (`geometry.py:911`), `emsutil.Material` (`emsutil/material.py:335`).
- Overlap resolution uses per-object priorities (`geometry.py:596-617`, `_base_priority` 10,
  `_priority = base + sub/2`). **Task 2:** highest `_priority` wins per tag
  (`simstate.py:114-123`); air uses `background()` (`geometry.py:978-980`) so dielectric boxes at
  default priority 10 keep their material. PEC/port `Plate` surfaces are registered GeoObjects and
  are fragmented with volumes inside `mesher.submit_objects` (`mesher.py:227-264`); no separate
  embed call is required before `commit_geometry`.
- Loss: the assembler uses a constant loss tangent, `er*(1 - 1j*tand)`
  (`physics/microwave/assembly/assembler.py:494`).

**Admitted subset** (same admission rules as `elmer_driven.prepare` lines 26–110, not its mesher):

- `check_design` passes; parameters resolved with `resolve_names`/`resolve_parts`.
- Exactly one port, `type` lumped (Discrete port), `excite` not false, real positive `R`, no `X`;
  port keys within the Elmer allowed set; an ideal line feed (zero transverse extent) widened by the
  explicit `feed_width_mm`; both feed ends touch PEC sheets across the full width; no PEC sheet
  crosses the gap.
- No `resistors`, no `lumped_elements`, no `transforms`, `cuts` or `voids` on any part.
- Primitives are axis-aligned `box` only (no `_matrix`). Metal → exactly one flat axis (PEC sheet).
  Dielectric → full volume.
- Materials: metal (PEC; finite `conductivity`/`thickness` only with `approximate_metals: true`,
  recorded), or isotropic dielectric with `eps_r`, `mu_r`, `tan_d`, `tan_d_freq` (same allowed key
  set as Elmer). At least one dielectric box and one PEC sheet. Overlapping dielectric boxes are
  rejected.
- A nonzero `tan_d` is admitted as EMerge's constant loss tangent and recorded as a limitation
  ("constant loss tangent; Elmer maps tan_d to a conductivity at tan_d_freq"). `tan_d_freq` stays
  required when `tan_d > 0`, as in Elmer. Rejecting loss would reject the built-in Patch reference
  design. Frozen with Task 6.
- Outer boundary: air box = bounding box of all parts and the feed, plus `padding_mm` on every side,
  with `AbsorbingBoundary` on all six faces. No PML.

**Settings** (exact key set, anything else rejected):
`analysis: "driven"`, `accept_finite_feed: true`, `feed_width_mm` (> 0), `padding_mm` (> 0),
`resolution: "coarse" | "fine"`, `f_min_hz`, `f_max_hz` (1 MHz–100 GHz, `f_min < f_max`),
`points` (int 3–21, linspace, exact values passed with `set_frequency(list)`),
`approximate_metals` (bool, default false). Resolutions are wavelength fractions at `f_max`,
**frozen** `coarse` = 0.25, `fine` = 0.15 (Task 5 Patch meshes 1975 / 5245 tets; not tightened).

**Resource limits (frozen Task 5):** worker timeout 1800 s for the whole sweep; reject before
launch if `(air-box volume) / (lambda_min * resolution)^3 > 200000` (a cheap tetrahedron-count
proxy, not a mesh measurement). The worker records the real node and tetrahedron counts. Task 5
Design walls were ~18–19 s with a warm Numba cache; 1800 s keeps headroom for cold JIT.

**Reference design class:** the built-in `Patch` template, `blank_design("p", "Patch")` (2.45 GHz
patch on `eps_r` 3.38, `tan_d` 0.0027, the same design `test_elmer_driven.py` uses). Level B claims
one documented design class only: this template and small edits of its dimensions.

**Loss (frozen):** nonzero `tan_d` is admitted as EMerge's constant loss tangent and recorded as a
limitation. `tan_d_freq` stays required when `tan_d > 0`.

**Patch class qualification (Task 5 evidence only; no `results_validated` for Design):** Design
runs stay `results_exported`. They do **not** claim S11 agreement with Fairbeam's openEMS run of
the same template. Recorded under `feed_width_mm=1`, `padding_mm=40`, 2.0–3.0 GHz × 11 points:
openEMS S11 minimum **2.453981250 GHz** at **−45.574 dB**; EMerge coarse and fine both place their
linspace S11 minimum at **2.30 GHz** (**−7.427 dB** coarse, **−6.349 dB** fine). Coarse→fine kept
the same frequency bin; `|S11|` at that bin rose from 0.425 to 0.481. Relative frequency offset of
the EMerge bin vs openEMS minimum is about **−6.3%**. Open gaps: no padding pair; 11-point sweep
may miss a finer resonance; port/ABC model mismatch expected (see Risks).

**Result schema** `fairbeam.emerge-driven-result/1`:
`{schema, status: "results_exported", frequency_hz, s11_re, s11_im, z_ref, settings, mesh: {nodes,
tetrahedra}, elapsed_seconds, phasor_convention: "exp(+i omega t)", native_phasor_convention,
precision_converged: false, gain_qualified: false, limitations: [...], pec_approximations: [...]}`.
Checks: frequencies equal the settings linspace, finite traces, `|S11| <= 1.01` (Elmer's bound).

---

## File map

| File | Responsibility |
| --- | --- |
| `python/fairbeam/emerge_design.py` | Admission + neutral case JSON (metres); no `emerge` import |
| `python/fairbeam_emerge.py` | `design_case_ok`, `run_design`, `assess_design`, CLI `design` subcommand |
| `python/fairbeam_emerge_worker.py` | `kind: "design"` branch: build geometry, BCs, sweep, `raw.json` |
| `python/fairbeam/emerge_bundle.py` | Shared Results bundle (S11, Zin; no far field) |
| `python/fairbeam/research.py` | `emerge` + design in prepare / execute / validate_result / bundle |
| `python/fairbeam/server.py` | Health `"emerge": 2` |
| `src/runner/api.ts` | Health type comment, result type if needed |
| `src/designer/RunDialog.tsx` | `emerge-driven` option, health-gated |
| `src/designer/EmergeAntennaRun.tsx` | Run form (mirror `ElmerAntennaRun.tsx`) |
| `src/i18n/en.json`, `src/i18n/tr.json` | `emergeAntenna.*` |
| `scripts/check-emerge-antenna-ui.mjs` | Synthetic UI check (mirror `check-elmer-antenna-ui.mjs`) |
| `python/tests/test_emerge_design.py` | Admission + parity with Elmer rules (no EMerge) |
| `python/tests/test_emerge_bundle.py` | Bundle contract (no EMerge) |
| `docs/EMERGE-EXPERIMENT.md`, `docs/EXPERIMENTAL-SOLVERS.md`, `docs/RESEARCH-SOLVERS.md` (+ `docs/tr/EXPERIMENTAL-SOLVERS.md`) | User docs |

---

## Task 1: Admission `emerge_design.py`

**Model tier:** mid (Claude Sonnet 5.5). Read `elmer_driven.py:26-172` and `settings_mesh` (:384).

**Files:** `python/fairbeam/emerge_design.py`, `python/tests/test_emerge_design.py`

**Steps:**

- [x] `admit(design, settings) -> dict`: validate settings (exact key set above), then the admitted
  subset rules in the same order and with the same wording as Elmer where the rule is the same.
  Do not deep-modify the input (copy first, as Elmer does).
- [x] Output case (metres, floats): `{"kind": "design", "boxes": [{"lo", "hi", "eps_r", "mu_r",
  "tan_d"}], "sheets": [{"lo", "hi", "normal_axis"}], "port": {"lo", "hi", "direction_axis",
  "sign", "width", "height", "z0"}, "air": {"lo", "hi"}, "frequencies_hz": [...], "resolution":
  <value>, "phasor_convention_out": "exp(+i omega t)", "limitations": [...],
  "pec_approximations": [...]}`.
- [x] Resource-limit proxy (Shared facts) raises before launch.
- [x] Tests: Patch template admitted; feed width applied on the right axis; input unchanged;
  rejects for two ports, resistor, lumped element, transform, cut, curved/rotated primitive,
  metal box with volume, flat dielectric, overlapping dielectrics, missing `tan_d_freq`, conductive
  metal without `approximate_metals`, unknown setting, `points` 2 and 22, `f_min >= f_max`, feed
  not touching PEC, PEC crossing gap, too-large domain.
- [x] **Parity test:** a list of at least 10 designs (accepted and rejected variants of the Patch
  template). For each, `elmer_driven.prepare(d, cell_mm=40, padding_mm=40)` and
  `emerge_design.admit(d, settings)` must both accept or both reject. Skip only Elmer's
  10000-cell limit (use a large `cell_mm`).
- [x] `ast` isolation test: `emerge_design.py` imports no `emerge`, `gmsh`, `emsutil`.
- [x] Run `-p "test_emerge_*.py"` and `-p "test_elmer_*.py"` (Level A plan's command) → pass.
- [x] Commit: `Admit a bounded Design subset for the EMerge driven port` (`1cdbc09`)

**Done when:** admission and parity tests pass without EMerge.

---

## Task 2: Worker and adapter design path

**Model tier:** mid (Claude Sonnet 5.5). Read EMerge 2.8.9 source in the managed venv; do not copy
code into the repo.

**Files:** `python/fairbeam_emerge_worker.py`, `python/fairbeam_emerge.py`,
`python/tests/test_emerge_fixture.py` (or a new `test_emerge_adapter_design.py`), this plan
(Shared facts notes)

**Steps:**

- [x] Read and cite (file:line in the commit body): `LumpedPort` voltage direction and sign, how
  `AbsorbingBoundary` `order`/`abctype` are used in assembly, how priorities resolve a dielectric
  box inside the air box and a PEC `Plate` on a dielectric face, and whether `Plate` surfaces need
  fragmenting with the volumes before `commit_geometry`.
- [x] Worker: branch on `case["kind"]`; keep the Level A fixture branch byte-for-byte in behavior.
  Design branch builds the air box, dielectric boxes (`Material(er, ur, tand)`), PEC plates, the
  port plate with `LumpedPort(width, height, direction, Z0)`, `AbsorbingBoundary` on the six air
  faces, then the same single-process sweep and S post-processing settings as Level A (capping,
  column normalization and reciprocity off). Writes `raw.json` with `s11_re/s11_im`, mesh counts,
  `native_phasor_convention`.
- [x] Adapter: `run_design(out, case, *, root=None, experimental=False)` with the same discipline
  as `run_fixture` (fresh dir, manifest per status, worker copy + SHA-256, `-I -X utf8`, thread env,
  timeout from Shared facts, `worker.log` always). `assess_design(raw, case)` checks the result
  schema rules and returns `results_exported`. CLI `design --experimental --case case.json --out
  DIR`. Stdlib only.
- [x] Tests (no EMerge): `run_design` opt-in, existing out dir refused, failure and timeout keep
  logs; `assess_design` rejects wrong frequencies, non-finite values, `|S11| > 1.01`, wrong
  convention; worker isolation test still passes.
- [x] Run `-p "test_emerge_*.py"` → pass.
- [x] Commit: `Add the EMerge worker path for admitted Designs`

**Done when:** adapter is tested without EMerge and the source citations are in the commit body.

---

## Task 3: Research wiring and bundle

**Model tier:** mid. Files named below only.

**Files:** `python/fairbeam/emerge_bundle.py`, `python/fairbeam/research.py`,
`python/fairbeam/server.py`, `python/tests/test_emerge_bundle.py`,
`python/tests/test_emerge_research.py`

**Steps:**

- [x] `research.prepare`: for `backend == "emerge"` with a design, call `emerge_design.admit`
  (Level A fixture path unchanged when `design` is `None`). Store the case in the snapshot.
- [x] `execute`: design → `fairbeam_emerge.run_design`. `validate_result`: new branch for
  `fairbeam.emerge-driven-result/1` before the fixture check. `completed_result`: `emerge` + that
  schema + `results_exported`.
- [x] `emerge_bundle.result_bundle(design, result)` mirroring `elmer_bundle.py`: engine `EMerge`,
  method `Frequency-domain FEM (experimental)`, boundaries `Second-order absorbing` (Task 2:
  AbsorbingBoundary order=2), `run: None`, `experimental` block with limitations and settings, port
  widened by `feed_width_mm`, S11 not conjugated, `zin = z_ref (1+S11)/(1-S11)` with the singular
  check, `farfield: []`.
- [x] Before writing the bundle, find every consumer of `bundle.results.farfield` in `src/` and
  confirm an empty list renders (no crash, no pattern tab claim). If a non-empty far field is
  required, stop with `BLOCKED`.
- [x] `execute` writes `bundle.json` + `bundle_sha256` for the new schema, like Elmer driven.
- [x] `server.py`: health `"emerge": 2`.
- [x] Tests: bundle preserves the design, `run is None`, no conjugation, Zin value on a known S11,
  empty far field; research admits the Patch template against a fake venv and rejects a two-port
  design; health is 2; Level A fixture tests unchanged.
- [x] Run `-p "test_emerge_*.py"`, `-p "test_elmer_*.py"`, `-p "test_research_*.py"` → pass.
- [x] Commit: `Wire EMerge Design runs into the research queue and shared results`

**Done when:** a synthetic driven result becomes a valid shared bundle in tests.

---

## Task 4: Run dialog UI

**Model tier:** mid. Mirror `ElmerAntennaRun.tsx` and `check-elmer-antenna-ui.mjs`; no refactor of
the Elmer components.

**Files:** `src/runner/api.ts`, `src/designer/RunDialog.tsx`, `src/designer/EmergeAntennaRun.tsx`,
`src/i18n/en.json`, `src/i18n/tr.json`, `scripts/check-emerge-antenna-ui.mjs`, `package.json`
(script entry)

**Steps:**

- [x] `RunDialog.tsx`: `<option value="emerge-driven">` after the Elmer options, only when
  `health.emerge >= 2`.
- [x] `EmergeAntennaRun.tsx`: finite-feed acceptance checkbox (required), feed width, padding,
  resolution `coarse`/`fine`, band and points, `approximate_metals`, EMerge path/managed runtime
  hint, submit to the research queue with `backend: "emerge"` and the design. Show the
  limitations before submit: experimental, absorbing boundary not PML, no far field, no gain,
  not a convergence certificate, constant loss tangent.
- [x] Results reuse the shared Results view through the bundle; no new results component unless
  Task 3 found one is required.
- [x] i18n `emergeAntenna.*` in both languages, no hardcoded English.
- [x] Check script: option hidden without `emerge: 2`; acceptance required; submitted body shape;
  synthetic result labelled synthetic; EN and TR.
- [x] Run `npm run typecheck`, `npm run check:i18n`, `npm run check:legal`,
  `npm run check:emerge-antenna`, `npm run check:research`, `npm run check:designer`.
- [x] Commit: `Add the experimental EMerge antenna option to the Run dialog`

**Done when:** checks pass and the option is hidden on servers without `emerge: 2`.

---

## Task 5: Native runs (human-authorized)

**Model tier:** mid. **Human gate:** ask before starting. One simulation at a time.

**Steps:**

- [x] Patch template, 2.0–3.0 GHz, 11 points, `approximate_metals: true` if the template metal
  has conductivity, `feed_width_mm` 1, `padding_mm` 40: run `coarse`, then `fine` through the CLI
  `design` subcommand (case from `emerge_design.admit`).
- [x] Run the same template once with openEMS (the normal Run path, coarse settings), and record
  its S11 minimum frequency and depth from its result files.
- [x] Record per run in the evidence log, from result/manifest files only: S11 minimum frequency and
  |S11| dB there, mesh nodes/tetrahedra, elapsed seconds, max `|S11|`, status, leftover processes.
- [x] If a run fails, times out, or `|S11| > 1.01`: `BLOCKED`, attach logs. Do not change limits.
- [x] Commit only the evidence log: `Record first native EMerge Design runs`

**Done when:** evidence log holds both EMerge runs and the openEMS reference run.

---

## Task 6: Planner freeze

**Model tier:** Planner.

**Steps:**

- [x] Freeze resolutions, the resource proxy and the timeout from Task 5.
- [x] Decide the documented qualification statement for the Patch class (for example: EMerge fine
  S11 minimum within a stated percentage of the openEMS minimum, and coarse→fine shift). Numbers
  from Task 5 only. Record it in Shared facts. No automatic `results_validated` is added.
- [x] Commit: `Freeze EMerge Design limits from recorded runs`

---

## Task 7: Documentation

**Model tier:** cheap. Numbers only from the evidence log.

**Files:** `docs/EMERGE-EXPERIMENT.md`, `docs/EXPERIMENTAL-SOLVERS.md`,
`docs/tr/EXPERIMENTAL-SOLVERS.md`, `docs/RESEARCH-SOLVERS.md`

**Steps:**

- [x] Admitted subset, rejects, settings, limitations, the Patch class result and the openEMS
  comparison (Fairbeam's own solver only).
- [x] Run `npm run check:legal`, `npm run check:links`, `npm run check:site`.
- [x] Commit: `Document the experimental EMerge Design subset`

---

## Task 8: Whole-branch review

**Model tier:** Planner.

- [x] Review against Global Constraints with `docs/agent/prompts/reviewer.md`; run the AGENTS.md
  pre-PR checks in a clean worktree (local untracked projects distort `check:designer`/`check:site`).
- [x] Mark Level B done; record open qualification gaps.

**Level B status:** done on `feat/emerge-experimental` through commit `0c0a149` (docs). Open
qualification gaps (do not block Level B close):

1. Patch EMerge S11 does not match Fairbeam openEMS (2.30 GHz / ≈−7 dB vs 2.454 GHz / −45.6 dB);
   no padding-pair or denser frequency study yet.
2. 11-point linspace may miss the true EMerge resonance; coarse→fine did not move the bin.
3. Pre-PR: `check:designer` / `check:site` / `check:run-summary` fail when untracked local
   `public/projects/hairpin-filter-*.json` are present — use a clean worktree before opening a PR.
4. Deferred Task 1 minors (gap-crossing centre-only, parity gaps) remain non-blocking.
5. `npm run check:scenarios -- --skip-run` not re-run in this Task 8 pass (optional before PR).

---

## Risks

- **Port model mismatch:** EMerge's `LumpedPort` imposes a uniform field over the finite plate;
  Elmer and openEMS model the feed differently. Expect a resonance shift; Task 6 documents it
  instead of tuning it away.
- **Absorbing boundary quality:** first-order ABC with 40 mm padding at 2.45 GHz is under half a
  wavelength. S11 near resonance may move with padding; Task 5 may need a padding pair (Planner
  decides, not the implementer).
- **Mesh size / time:** gmsh tetrahedra for a thin substrate can grow fast at `fine`; the proxy
  limit exists to refuse before a long run. Cold numba JIT added about 150 s in Level A.
- **Shared viewer and empty far field:** if the Results view requires a pattern, Task 3 is
  `BLOCKED` and the Planner decides (far field moves into scope, or a results-only view).
- **Loss decision:** constant `tan_d` admitted and frozen after Task 5 (required for the Patch
  template).
- **Admission drift from Elmer:** rules are re-implemented, not shared, to keep Elmer files
  untouched; the parity test is the guard. Extracting a shared admission module is a later,
  separate refactor with its own review.

---

## Evidence log

Fill only with commands run and outputs observed. Date every entry.

- 2026-11-04 (Planner): API names and lines in Shared facts were read from the installed managed
  venv `%LOCALAPPDATA%\org.fairbeam.desktop\emerge\2.8.9\Lib\site-packages` (EMerge 2.8.9). No
  EMerge run was made for this plan.
- 2026-11-04 (Task 5, Composer): Patch template metal is `{name: copper, kind: metal}` with no
  conductivity/thickness → `approximate_metals` left false. Admitted cases with
  `accept_finite_feed=true`, `feed_width_mm=1`, `padding_mm=40`, `f_min_hz=2e9`, `f_max_hz=3e9`,
  `points=11` → temp
  `C:\Users\ee\AppData\Local\Temp\fairbeam-emerge-design-cases-20261104-145705\patch-{coarse,fine}.case.json`
  (coarse resolution 0.25, fine 0.15; 1 box, 2 sheets, 11 frequencies).
- 2026-11-04 (Task 5): EMerge Design **coarse**
  `--root %LOCALAPPDATA%\org.fairbeam.desktop\emerge\2.8.9 design --experimental --case …\patch-coarse.case.json
  --out C:\Users\ee\AppData\Local\Temp\fairbeam-emerge-design-coarse-20261104-145716` → exit 0, wall
  **18.6 s**. `manifest.status` / `result.status` = `results_exported`, EMerge **2.8.9**,
  `phasor_convention` / `native_phasor_convention` = `exp(+i omega t)`, mesh **474 nodes / 1975 tets**,
  `result.elapsed_seconds` **11.517**, `manifest.worker_seconds` **18.414**. From `result.json`:
  S11 min at **2.30 GHz**, `|S11|=0.425269` (**−7.427 dB**); `max_|S11|=0.982634` (< 1.01);
  `|S11|` all `[0.983, 0.961, 0.836, 0.425, 0.912, 0.963, 0.976, 0.980, 0.982, 0.982, 0.979]`.
  After run: no leftover emerge-venv `python` processes. `pec_approximations: []`.
- 2026-11-04 (Task 5): EMerge Design **fine**
  `--out C:\Users\ee\AppData\Local\Temp\fairbeam-emerge-design-fine-20261104-145753` → exit 0, wall
  **18.5 s**. `results_exported`, mesh **1141 nodes / 5245 tets**, `result.elapsed_seconds` **16.469**,
  `manifest.worker_seconds` **18.411**. From `result.json`: S11 min at **2.30 GHz**,
  `|S11|=0.481434` (**−6.349 dB**); `max_|S11|=0.984801`;
  `|S11|` all `[0.985, 0.972, 0.925, 0.481, 0.786, 0.940, 0.967, 0.975, 0.978, 0.979, 0.978]`.
  After run: no leftover emerge-venv `python` processes. Warm numba (Level A cache); both Design
  solves finished well under the 1800 s provisional timeout.
- 2026-11-04 (Task 5): openEMS reference — wrote `blank_design("p","Patch")` to
  `%TEMP%\fairbeam-patch-ref.design.json` (design mesh `cells_per_wavelength: 20`, band
  `f0*0.6`–`f0*1.3`). `python -m fairbeam run … --out
  C:\Users\ee\AppData\Local\Temp\fairbeam-openems-patch-20261104-145846 --sim-root …-sim-…
  --engine cpu --threads auto` → exit 0, wall **38.1 s**. Bundle `p.json`: `run.converged=True`,
  `run.solver_time_s=35.2`, `run.wall_time_total_s=37.72`, `run.timesteps=15252`,
  `mesh.total_cells=112320`, `mesh.auto.settings.cells_per_wavelength=20`. From
  `results.sparams.s["1,1"]` vs `results.frequency` (801 pts): S11 min at **2.453981250 GHz**,
  `|S11|=0.005264` (**−45.574 dB**); `max_|S11|=0.998555`. Band record:
  `s11_min_db=-45.574` @ `f_center=2453981250`. No leftover emerge/openEMS python processes after.
- 2026-11-04 (Task 6, Composer): Froze resolutions 0.25 / 0.15, proxy 200000, Design timeout
  1800 s; Patch qualification = experimental export only, no openEMS S11 agreement claim. Commit
  `0d9efcd`.
- 2026-11-04 (Task 7, Composer): Documented Design subset in `EMERGE-EXPERIMENT.md`,
  `EXPERIMENTAL-SOLVERS.md`, `tr/EXPERIMENTAL-SOLVERS.md`, `RESEARCH-SOLVERS.md`.
  `npm run check:legal` → ok; `check:links` → 5711 OK; `check:site` → passed after restoring
  `public/projects/index.json` to HEAD (local hairpin entries had inflated the example count).
  Commit `0c0a149`.
- 2026-11-04 (Task 8, Composer): Global Constraints review APPROVE for Level B scope.
  `-p test_emerge_*.py` → 113 OK; `test_elmer_*.py` → 33 OK; `test_research_*.py` → 27 OK
  (one transient ConnectionAbortedError log from parallel serve, suite still OK).
  `npm run typecheck` → OK; `check:legal` → ok; `check:emerge-antenna` → PASS; `check:research` →
  PASS. `check:run-summary` / designer chain fails on untracked
  `hairpin-filter-cgrassin-20261104-114535-32fd0c.json` (`suspicious` vs `converged`) — local dirt,
  not EMerge. Level B marked done with open gaps listed under Task 8.
