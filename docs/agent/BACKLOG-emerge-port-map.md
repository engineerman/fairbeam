# EMerge backlog (resume card board)

> **Only resume file** for this track. No separate `HANDOFF.md`.  
> Active plans: `docs/agent/plans/` (delete when done). North star: `MISSION.md` / `SCOPE.md`.  
> Living port-map policy: [openEMS ↔ EMerge port mapping](specs/2026-11-05-emerge-openems-port-mapping-design.md).

**Branch:** `feat/emerge-experimental` · **Updated:** 2026-11-07  
**Next open ID:** O18 · **Next closed ID:** C5  
(IDs are stable within their prefix; never renumber or reuse.)

Do not implement multi-file EMerge work from chat alone — write a plan first. Prefer in-session
implement; no SubAgent unless asked.

**ID scheme**

| Prefix | Meaning | Example |
| --- | --- | --- |
| **O** | Open (Ready / Parked / Active) | `O3`, `card O3` |
| **C** | Closed (shipped / dropped / superseded) | `C1` |

**Referencing:** prefer the ID (`O16`). Titles alone are ambiguous when similar. Agents resolve by
**ID** first.

---

## 30-second dashboard

Multiple cards may be **Active** at once (parallel agents / tracks). Do not demote another Active card to work on yours.

| Now | **O7** Active · **O17 BLOCKED** |
| --- | --- |
| Plans | O7: [2026-11-07-emerge-o7-run-progress-fem-labels.md](plans/2026-11-07-emerge-o7-run-progress-fem-labels.md) · O17: [2026-11-07-emerge-o17-cpw-waveport-aperture.md](plans/2026-11-07-emerge-o17-cpw-waveport-aperture.md) (evidence) |
| Waiting on you | O7 in flight · O17: ModalPort go-ahead or pick another Ready |

**Open / parked:**

| ID | Card | Status | One-liner |
| --- | --- | --- | --- |
| O1 | [Tools · Filter Designer](#card-o1) | Parked | Parametric filter toolbox (AWR iFilter-like); extendable Tools menu |
| O2 | [EMerge path · Optimize](#card-o2) | Parked | Drive Optimize (and later Sweep) with EMerge, not only openEMS |
| O4 | [EMerge multi-frequency field planes](#card-o4) | Ready | One auto freq today; user-picked / multi freq without re-solving FEM |
| O5 | [Field plane vs geometry z-fight](#card-o5) | Ready | Zoom in → solids win; zoom out → plane wins (coplanar depth) |
| O6 | [Remember last solver on refresh / load](#card-o6) | Ready | Refresh / project load resets to openEMS; keep last choice |
| O7 | [EMerge run progress & FEM labels](#card-o7) | Active | Stages say FDTD after Mesh; need FEM wording + real progress |
| O9 | [Finer coax mesh & excitation](#card-o9) | Parked | Coax path exists; mesh too coarse for credible coax S |
| O10 | [Richer board geometry](#card-o10) | Parked | Stackup / vias / multilayer — not started |
| O11 | [Design rectangular waveguide → EMerge](#card-o11) | Parked | Run your WG Design in EMerge (not only Research fixture) |
| O12 | [Port-map test fixtures housekeeping](#card-o12) | Ready | What to keep local vs CI |
| O13 | [Surface-current export](#card-o13) | Ready | `current_boundary` → Post / results |
| O14 | [Far-field / efficiency / pattern export](#card-o14) | Parked | Needs schema work; UI stays disabled |
| O15 | [Denser FEM mesh draw](#card-o15) | Ready | Optional all-tets / interior edges if exterior wireframe is thin |
| O17 | [Classic CPW WavePort physics](#card-o17) | **Blocked** | WavePort trials done; S still not plausible TL; ModalPort needs human go-ahead |

**Closed (index):**

| ID | Card | Closed | Note |
| --- | --- | --- | --- |
| C1 | [Modal microstrip WavePort](#card-c1) | 2026-11-06 | Stage C microstrip; CPW follow-on shipped as C2 |
| C2 | [Modal CPW ports](#card-c2) | 2026-11-07 | Admit/UI/worker path; S physics → O17 |
| C3 | [EMerge “Not converged” honesty](#card-c3) | 2026-11-07 | No FDTD timestep badge; Header “Mesh not certified” |
| C4 | [Simplify EMerge port-map UX](#card-c4) | 2026-11-07 | Per-port map dropdown/label + tooltips; default Lumped |

---

## How to read a card

Every open item uses the same fields:

| Field | Meaning |
| --- | --- |
| **ID** | Stable `ON` — use when naming work (“do O3”). Never reuse after close/remove. |
| **Status** | `Ready` · `Parked` · `Active` (several cards may be Active together) |
| **In plain words** | What a human should understand without scope codes |
| **Outcome** | What “done” looks like |
| **Not in scope** | Explicit non-goals |
| **Plan** | Existing plan link, or “write plan before coding” |

**Adding an open card:** take **Next open ID** (`ON`), put it in the dashboard + heading +
anchor `card-oN`, then bump **Next open ID** to O(N+1).

**Closing a card:** assign **Next closed ID** (`CN`), move a short summary under **Closed cards**,
add a Closed-index row, remove the open card body, bump **Next closed ID**. Do not reuse the old
`O` number. Leave gaps in the open series.

---

## Open cards

<a id="card-o1"></a>

### O1 · Tools · Filter Designer

| | |
| --- | --- |
| **ID** | O1 |
| **Status** | Parked (human filed 2026-11-06 — product idea; not EMerge-only) |
| **In plain words** | Drawing filter geometry by hand in the Designer is hard. Want an AWR **iFilter**-like path: a **Tools** menu (new toolbox surface — not the existing Modeling › Tools boolean group) with a first tool **Filter Designer**. User picks a topology (e.g. hairpin, later others), enters specs (center frequency, bandwidth, …), and Fairbeam builds the Design (geometry + ports + materials) automatically. More tools can hang under the same menu later. |
| **Outcome** | Bounded first topology generates a real editable Design; clear experimental/approx labeling where synthesis is rule-of-thumb; menu structured so more synthesizers can be added without a one-off UI. Generated Designs remain runnable under openEMS (and EMerge when admitted). |
| **Not in scope** | Full AWR/iFilter parity; every filter class on day one; proprietary cookbook IP; silent “perfect response” claims. |
| **Note** | Broader Designer product work tracked here so it is not lost; unpark when the human wants a plan (may deserve its own docs track later). Local hairpin experiments already exist in this fork as a natural first candidate. |
| **Plan** | Write plan when unparked (IA + first topology + Design schema write). |

---

<a id="card-o2"></a>

### O2 · EMerge path · Optimize

| | |
| --- | --- |
| **ID** | O2 |
| **Status** | Parked (human filed 2026-11-06 — separate item; not next) |
| **In plain words** | Today Optimize (and Sweep) drive openEMS only. Want an eventual path where an admitted EMerge experimental Design can be driven by Optimize the same way — goals, variables, run loop — without making EMerge the default solver. |
| **Outcome** | Bounded Optimize → EMerge experimental runs (admit + worker + result hooks), honest experimental labeling; Sweep only if it falls out cleanly or as a follow-on. |
| **Not in scope** | Production optimizer parity with openEMS; claiming validated optima; replacing openEMS Optimize. |
| **Plan** | Write plan when unparked; depends on stable single-run admit/export first. |

---

<a id="card-o4"></a>

### O4 · EMerge multi-frequency field planes

| | |
| --- | --- |
| **ID** | O4 |
| **Status** | Ready (human filed 2026-11-06) |
| **In plain words** | After an EMerge solve, Field map / Field plane shows **one** frequency (auto: max \|S21\|, else min \|S11\|, else band center). Want: see more than one frequency, ideally with a user frequency pick when drawing the plane. |
| **Cost note (eval, not measured)** | Extra frequencies should **not** re-run the FEM solve. Today the worker already solves the S sweep, then post-samples one `MWField.cutplane` at the picked freq (`export_efield_cut`). N maps ≈ N × cutplane interpolate + larger `field_planes` / result size — usually **much smaller** than mesh+solve time, but not free (RAM/JSON grow; openEMS already caps 1–4 freqs/plane for the same reason). Prefer user-selected freqs (and/or a small capped multi-export) over exporting the whole sweep by default. |
| **Outcome** | User can choose which solved frequency(ies) to export/show for EMerge field planes (bounded, honest cost copy); Post / 3D switch among stored maps. Default can stay one auto pick. |
| **Not in scope** | Re-solving FEM per field frequency; claiming openEMS dump parity; unbounded all-freq export. |
| **Evidence** | `fairbeam_emerge_worker.export_efield_cut` / `_pick_efield_cut_freq`; `emerge_field_cut.py` single-freq note; openEMS `monitors.field_planes` already 1–4 freqs. |
| **Plan** | Write plan (worker multi-cut + UI freq picker + size caps) before coding. |

---

<a id="card-o5"></a>

### O5 · Field plane vs geometry z-fight

| | |
| --- | --- |
| **ID** | O5 |
| **Status** | Ready (human filed 2026-11-06) |
| **In plain words** | When the field plane sits on the same plane as a solid surface (typical board-parallel cut), zoom **in** often shows geometry, zoom **out** often shows only the field plane — classic coplanar depth fighting. |
| **Fix directions (eval)** | Prefer a small normal offset and/or `depthTest: false` while the plane is shown (other overlays already do); strengthen `polygonOffset` / `renderOrder`; optionally dim/hide coplanar solid faces when Field plane is on. Measure in Viewport, not guess. |
| **Outcome** | At common zoom ranges, both the field map and the model silhouette stay readable without flicker or one fully occluding the other. |
| **Not in scope** | Changing physics cut height to “fix” display; inventing a second mesh. |
| **Evidence** | `src/scene/fieldPlanes.ts` already uses `depthWrite: false` + mild `polygonOffset`; still fights solids that share the plane. EMerge cut z is substrate mid (`_efield_cut_z_m`) — often coplanar with copper/substrate faces. |
| **Plan** | Small UI/scene plan; verify with a microstrip field-plane view. |

---

<a id="card-o6"></a>

### O6 · Remember last solver on refresh / load

| | |
| --- | --- |
| **ID** | O6 |
| **Status** | Ready (human filed 2026-11-06) |
| **In plain words** | After a browser Refresh (e.g. Vite/Cypher HMR or hard reload) or when reopening a project, the Run solver selection resets to openEMS. You have to pick **EMerge FEM · Experimental** again every time. |
| **Outcome** | Last chosen solver sticks across refresh and project load (session and/or project preference), until the user changes it. Default for brand-new sessions can stay openEMS. |
| **Not in scope** | Changing the product default away from openEMS; auto-switching solvers based on geometry. |
| **Plan** | Write a small UI/prefs plan before coding. |

---

<a id="card-o7"></a>

### O7 · EMerge run progress & FEM labels

| | |
| --- | --- |
| **ID** | O7 |
| **Status** | Active (2026-11-07) |
| **In plain words** | EMerge runs show little or no useful progress. The stage strip still looks FDTD-shaped (e.g. after Mesh it still says **FDTD**). For EMerge that label should be FEM (or an honest FEM-stage name), and the UI should surface real progress when the worker can report it. |
| **Outcome** | EMerge Run UI uses FEM-appropriate stage labels (not FDTD); progress updates appear when available (mesh/build/solve), with honest fallbacks if EMerge only emits coarse milestones. |
| **Not in scope** | Fake fine-grained %; claiming openEMS-parity progress UX; changing openEMS FDTD stage names. **Deferred (human 2026-11-07):** per-frequency progress (Fairbeam-owned freq loop / worker streaming) — keep monolithic `run_sweep`; revisit later if wanted. |
| **Plan** | [2026-11-07-emerge-o7-run-progress-fem-labels.md](plans/2026-11-07-emerge-o7-run-progress-fem-labels.md) |

---

<a id="card-o9"></a>

### O9 · Finer coax mesh & excitation

| | |
| --- | --- |
| **ID** | O9 |
| **Status** | Parked (2026-11-06) |
| **In plain words** | Coaxial Designs can already enter EMerge Experimental, but the mesh is not fine enough around the inner conductor / gap to trust results. Mesh view also only draws the outer box. |
| **Outcome** | Local mm-scale mesh control (gap/edges), honest UI; optional better Mesh overlay; optional S smoke after mesh is credible. Still `results_exported` only. |
| **Not in scope** | openEMS S-agreement claims; inventing “validated” coax numbers. |
| **Evidence** | Job `20261106-223255-d090c5`: 1614 nodes / 9032 tets, `coarse` @ 1–2 GHz → ~37 mm target size vs 2 mm coax gap. Worker has no conductor-edge refine. |
| **Plan** | Write a new plan when reopened (not chat-only). |

---

<a id="card-o10"></a>

### O10 · Richer board geometry

| | |
| --- | --- |
| **ID** | O10 |
| **Status** | Parked (human: implement later) |
| **In plain words** | Today’s EMerge Design recipes are single-layer / simple solids. This card widens geometry (stackup, vias, richer PCB-like shapes) without silent coercion. |
| **Outcome** | Bounded new geometry class(es) on the unified Experimental Run, with reject rules and docs. |
| **Not in scope** | Full CAD parity; bundling EMerge; replacing openEMS. |
| **Plan** | Write plan under `docs/agent/plans/` before coding. |

---

<a id="card-o11"></a>

### O11 · Design rectangular waveguide → EMerge

| | |
| --- | --- |
| **ID** | O11 |
| **Status** | Parked (skipped 2026-11-06 — no current sim need) |
| **In plain words** | Your Design already has openEMS-shaped `waveguide` ports. openEMS runs them today. EMerge does **not** — only the fixed Research WR-90 fixture does. This card would let an all-waveguide Design run under **EMerge FEM · Experimental** as analytic `RectangularWaveguide` (TE first). |
| **Outcome** | Admit + worker + accept UI + docs; Research WR-90 fixture stays. |
| **Not in scope** | Remapping one openEMS port type to another. TM on first pass. Curved guides. |
| **Plan** | Write plan when reopened. |

---

<a id="card-o12"></a>

### O12 · Port-map test fixtures housekeeping

| | |
| --- | --- |
| **ID** | O12 |
| **Status** | Ready |
| **In plain words** | Decide which local `portmap_*.design.json` files stay personal vs become trimmed CI fixtures. |
| **Outcome** | Clear policy + optional CI fixtures; backlog stays indexed from experiment docs. |
| **Not in scope** | Committing personal full models under `python/models/` by accident. |
| **Plan** | Small chore plan or fold into another card’s docs task. |

---

<a id="card-o13"></a>

### O13 · Surface-current export

| | |
| --- | --- |
| **ID** | O13 |
| **Status** | Ready |
| **In plain words** | EMerge can expose boundary currents; Fairbeam does not yet export them into Post / results. |
| **Outcome** | Experimental surface-current (or equivalent) artifact + UI path when present; honest limits. |
| **Not in scope** | Claiming validated current density vs measurement. |
| **Plan** | Write plan before coding (`current_boundary` / worker export spike first). |

---

<a id="card-o14"></a>

### O14 · Far-field / efficiency / pattern export

| | |
| --- | --- |
| **ID** | O14 |
| **Status** | Parked |
| **In plain words** | Post far-field / efficiency / pattern actions stay disabled for EMerge until a result schema and exporter exist. |
| **Outcome** | Bounded export + UI enablement with experimental labeling. |
| **Not in scope** | openEMS far-field parity claims; Optimize/Sweep driving EMerge (still deferred). |
| **Plan** | Write plan when schema approach is chosen. |

---

<a id="card-o15"></a>

### O15 · Denser FEM mesh draw

| | |
| --- | --- |
| **ID** | O15 |
| **Status** | Ready |
| **In plain words** | Mesh view today draws a thinned exterior surface wireframe. Optional denser draw (all tets / interior edges) if that is not enough. |
| **Outcome** | Toggle or setting for denser FEM overlay without confusing it with FDTD planes. |
| **Not in scope** | Showing openEMS Yee mesh as if it were tetrahedral. |
| **Plan** | Write plan when needed. |

---

## Closed cards

<a id="card-c1"></a>

### C1 · Modal microstrip WavePort — shipped (2026-11-06)

| | |
| --- | --- |
| **ID** | C1 |
| **Closed** | 2026-11-06 |
| **Was** | Stage C microstrip modal port map (open ID retired; do not reuse O-series for this work) |
| **Summary** | Microstrip planar Designs may opt into EMerge `WavePort` via `accept_modal_ports` (modal wins over lumped; hard fail on WavePort errors; UI + preview). Default accept path remains lumped terminals. |
| **Docs** | [EMERGE-EXPERIMENT.md](../EMERGE-EXPERIMENT.md) Stage C; design matrix Stage C microstrip row. |
| **Follow-on** | Classic CPW shipped as [C2](#card-c2). |

---

<a id="card-c2"></a>

### C2 · Modal CPW ports — shipped (2026-11-07)

| | |
| --- | --- |
| **ID** | C2 |
| **Closed** | 2026-11-07 |
| **Was** | O8 Modal CPW ports (open ID retired; do not reuse O8) |
| **Summary** | Classic all-`cpw` planar Designs admit to EMerge `WavePort` via `accept_modal_ports` (or coplanar gap `LumpedPort` via `accept_lumped_terminals`; modal wins if both). Worker skips substrate-bottom PEC. GCPW detected and rejected. Run UI modal accept + preview. |
| **Docs** | [EMERGE-EXPERIMENT.md](../EMERGE-EXPERIMENT.md) Stage C CPW; design matrix CPW row. Measured mesh_only **5453** nodes / **27377** tets (~1.0 s); coarse 3-pt S → `results_exported` (~8.1 s) on managed 3.0.0b12. |
| **Follow-on** | Physics/S credibility → [O17](#card-o17). GCPW still out of scope. |

---

<a id="card-c3"></a>

### C3 · EMerge “Not converged” honesty — shipped (2026-11-07)

| | |
| --- | --- |
| **ID** | C3 |
| **Closed** | 2026-11-07 |
| **Was** | O16 EMerge “Not converged” vs openEMS criteria (open ID retired; do not reuse O16) |
| **Summary** | Timing-only EMerge `run` no longer scores as openEMS FDTD timestep-limit. `runQuality` / `cli.run_quality` return no FDTD verdict for EMerge; Header shows **Mesh not certified** (not green Converged). `precision_converged` stays false. |
| **Docs** | [EMERGE-EXPERIMENT.md](../EMERGE-EXPERIMENT.md) “Results UI honesty (convergence)”. Commits `f39293e`, `0e7fcd8`, `99ea528`. |
| **Follow-on** | None; O7 still owns live FEM progress labels. |

---

<a id="card-c4"></a>

### C4 · Simplify EMerge port-map UX — shipped (2026-11-07)

| | |
| --- | --- |
| **ID** | C4 |
| **Closed** | 2026-11-07 |
| **Was** | O3 Simplify EMerge port-map UX (open ID retired; do not reuse O3) |
| **Summary** | Run **Port mapping to EMerge** is compact: per-port row with shared map control (dropdown when LumpedPort/WavePort both admitted; label when one option). Honesty copy in tooltips; default **LumpedPort** so empty-ack / “not admitted” warn does not fire on open. Global accept flags unchanged (no Design `ports[].emerge`). |
| **Docs** | Plan deleted after human accept. UI: `EmergePortMapPreviewView`, `EmergeRun`, `emergePortMapPreview` helpers; en+tr `emergePortMap.intro` / `mapLabel`. |
| **Follow-on** | None for UX; physics still O17 / admit cards. |

---

<a id="card-o17"></a>

### O17 · Classic CPW WavePort physics

| | |
| --- | --- |
| **ID** | O17 |
| **Status** | **Blocked** (2026-11-07) — WavePort path exhausted; waiting on human ModalPort go-ahead (or drop) |
| **In plain words** | C2 admits classic CPW → WavePort, but through-line S stays implausible after aperture / enclosure / Z-terminal / lumped A/B. Microstrip sanity (hairpin, portmap line) still healthy — not a general engine break. |
| **Outcome (WavePort)** | **BLOCKED.** Air aperture (`CPW_AIR_APERTURE_FRACTION=1.0`) opens a path (field through; mid-band S21 can peak ~−0.7 dB) but band-low stays highly reflective (~S21 −7 dB / S11 ~−1 dB). Human rejected as through-line. Open enclosure helps slightly, not enough. `set_terminals` enables PV Z0 (~70 Ω) but S unchanged. Lumped (`ZAX`) worse (S21 ~−50…−64 dB). |
| **Evidence jobs** | Baseline total-reflect `20261107-010833-bccee1`; human FAIL shielded `20261107-013032-d9b825`; open `.sim/o17-cpw-open-0767a65d`; full-air `.sim/o17-cpw-fullair-33f82b34`; Z-term `.sim/o17-cpw-zterm-52ee1a3d`; lumped `.sim/o17-cpw-lumped-dfa274d9`. Engine OK: `.sim/o17-sanity-ms-lumped-*`, `.sim/o17-sanity-hairpin-lumped-*`. |
| **Not in scope** | openEMS S-agreement; inventing bottom PEC; shipping `ModalPort` without explicit human go-ahead; GCPW. |
| **Next** | Human names ModalPort trial card / go-ahead, or leaves O17 blocked and picks another Ready card. |
| **Plan** | [2026-11-07-emerge-o17-cpw-waveport-aperture.md](plans/2026-11-07-emerge-o17-cpw-waveport-aperture.md) |
| **Handoff** | [HANDOFF-cpw-waveport-physics.md](HANDOFF-cpw-waveport-physics.md) |
| **Related** | [C2](#card-c2) plumbing. |

---

## Out of scope (until someone reopens)

- Neutral Design “port intent” schema · `ports[].emerge` side-car  
- Shared `translate_port()` with openEMS · Elmer port matrix  
- S-parameter agreement / `results_validated` for mapped EMerge runs  
- Bundling EMerge · replacing openEMS as default  
- Optimize / Sweep driving EMerge — tracked as parked [O2 EMerge path · Optimize](#card-o2); still deferred until unparked

---

## Session notes (agents)

**Dirty tree — keep out of feature commits unless asked:**
- `public/projects/index.json`, unrelated `README.md` / landing gif  
- Uncommitted Mesh Generate coax accept fix: `src/designer/EmergeSimSettings.tsx`  
- `.cursor/rules/main-squash-merge.mdc`, `.impeccable/`

**Constraints:** reject never silent remap; only worker imports `emerge`/`gmsh`/`emsutil`;
`en.json`+`tr.json` + `check:legal`; `Co-Authored-By:` per `AI_POLICY.md`; Windows Python via
`.cursor/rules/windows-local-python.mdc`. Push `origin/main` only when human asks; never
`upstream` or topic-branch push.

Local smoke (do not commit): `portmap_*` under `python/models/`. Regen:
`python/scripts/_gen_portmap_designs.py`.

### How to resume

1. Read the **dashboard**.  
2. Human names a card by **ID** (`O3`, `card O3`) — title alone is optional backup. Or set **Status: Active**.  
3. Write/open its **Plan**, then implement task-by-task.  
4. When the plan is finished, **delete** the plan file; **close** the card as the next `CN` (do not renumber open IDs).  
5. Say **continue** / **go** only after a card is active.
