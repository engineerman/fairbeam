# EMerge Run dialog — port-map info panel

> **For agentic workers:** Use `.cursor/skills/emerge-agent-workflow`. One task at a time.
> Do not start coding until the human approves this plan.

**Goal:** In the Run dialog, for **EMerge FEM · Experimental antenna** and **EMerge FEM · Experimental
planar two-port**, show a short info list of how each Design port maps to an EMerge BC (or why it
is rejected) **before** Save and Run.

**In one sentence:** An informative panel in the Run dialog — not a new solver feature, not an API.

**Architecture (v1, simple):** Tiny TypeScript helper in the designer that mirrors today’s Stage A
rules and frozen strings from `python/fairbeam/emerge_port_map.py`. Shared UI block above the
accept checkbox / accept note. **No new HTTP endpoint.** A parity test locks the TS strings to the
Python constants so the panel cannot silently drift.

**Tech Stack:** SolidJS/TS Run forms + i18n; small Python unittest that reads the frozen strings;
`npm run check:legal` / `typecheck`.

**Scope:** Antenna + planar Run forms only. Slice of backlog item 4 (info panel). **Not:** Stage B
coax, Design waveguide, Stage C modal, unified N-port, auto-suggest which Run option to pick, new
API routes.

**Related:**
- Map design: `docs/agent/specs/2026-11-05-emerge-openems-port-mapping-design.md`
- Backlog item 4: `docs/agent/BACKLOG-emerge-port-map.md`
- Stage A (done): `docs/agent/plans/2026-11-06-emerge-port-map-stage-a.md`

---

## Global Constraints

Copy into implementer / reviewer prompts.

- openEMS stays default. EMerge stays opt-in experimental.
- No new `/api/...` routes for this panel.
- Reject, never silent coerce. Panel shows reject reasons; does not invent BCs.
- Ok-line approximation text must match Python `APPROX_*` **exactly** (parity test).
- No S-parameter / cross-solver equivalence claims. Follow repository “CST-compatible VBA macro” wording rules.
- UI chrome (title, reject banner, empty): `en.json` + `tr.json`. Pass `npm run check:legal`.
- Branch `feat/emerge-experimental`. `Co-Authored-By:` per `AI_POLICY.md`.
- Do not commit `python/models/portmap_*.design.json`.

---

## Shared facts

1. Antenna form → path `driven`. Planar form → path `planar`.
2. Preview assumes the accepts the form will send: driven `accept_finite_feed: true`, planar
   `accept_lumped_terminals: true`.
3. Frozen strings (copy into TS constants; parity-tested against Python):
   - driven lumped: `finite-width lumped feed plate`
   - planar microstrip: `microstrip → lumped strip-to-ground terminal; feed_shift/measurement_shift unused`
4. Line format:
   - ok: `Port {n} · {type} → LumpedPort ({approx})`
   - fail: `Port {n} · {type} → {short reject reason}`
5. Reject reasons for v1 (keep short, honest; English technical body is fine — chrome is i18n):
   - driven + microstrip → does not admit microstrip
   - planar + lumped → does not admit lumped
   - waveguide / coax / cpw / unknown → not supported on this path (match Stage A spirit)
6. Placement: **above** antenna accept checkbox / planar accept note. Warn on rejects; do not
   soft-disable Save and Run solely for preview (admit still rejects at submit).

---

## File map

| File | Responsibility |
| --- | --- |
| `src/designer/emergePortMapPreview.ts` | **New.** Stage A mirror + `previewPorts(ports, path)`. |
| `src/designer/EmergePortMapPreviewView.tsx` | **New.** Renders the list / warn (name avoids Windows clash with `emergePortMapPreview.ts`). |
| `src/designer/EmergeAntennaRun.tsx` | Mount preview above accept. |
| `src/designer/EmergePlanarRun.tsx` | Mount preview above accept note. |
| `src/i18n/en.json`, `tr.json` | Title / reject / empty chrome only. |
| `python/tests/test_emerge_port_map_preview_parity.py` | **New.** Asserts TS constants == Python `APPROX_*` / `MAPPED_LUMPED`. |
| `docs/agent/BACKLOG-emerge-port-map.md` | Item 4: preview done; auto-suggest still open. |

---

## Task 1: TS mirror + parity test

**Model tier:** cheap

**Files:** create `src/designer/emergePortMapPreview.ts`; create
`python/tests/test_emerge_port_map_preview_parity.py`

**Steps:**

- [x] Add `previewPorts(ports, path: "driven" | "planar")` returning
  `{ ok, ports: [{ number, type, ok, line }], error? }`.
- [x] Export frozen string constants used in ok lines.
- [x] Parity test opens the TS file (or a tiny exported JSON sidecar if easier) and asserts the
  approximation strings equal `APPROX_DRIVEN_LUMPED` / `APPROX_PLANAR_MICROSTRIP` and BC name
  `LumpedPort`. Prefer reading named constants from the `.ts` file with a simple regex/ast-free
  scrape already used elsewhere in the repo if one exists; otherwise keep constants in a small
  shared `emergePortMapPreview.strings.ts` that the test can parse.
- [x] Unit-style cases in the TS module via a small node/vitest **or** (if the repo has no front
  unit runner for designer helpers) cover outcomes in the Python parity file by importing a
  minimal JSON fixture of expected lines — **simplest acceptable gate:** Python parity on strings
  + one pure function test if the project already has a pattern; do not add a new test framework.
- [x] Run: `cd python && python -m unittest tests.test_emerge_port_map_preview_parity -v`
- [x] Commit: `feat(emerge): client port-map preview helper with string parity`

**Done when:** Helper produces correct lines for lumped/driven, microstrip/planar, and wrong-path;
parity test fails if someone edits the TS approx string without updating Python (or vice versa).

---

## Task 2: UI panel + wire both forms + i18n

**Model tier:** mid

**Files:** `EmergePortMapPreviewView.tsx`, `EmergeAntennaRun.tsx`, `EmergePlanarRun.tsx`, i18n

**Steps:**

- [x] Chrome keys (en + tr), e.g. `emergePortMap.title`, `emergePortMap.reject`, `emergePortMap.empty`.
- [x] Component reads `draft.ports`, calls `previewPorts`, lists `line`s; warn style when `!ok`.
- [x] Antenna: above accept checkbox. Planar: above accept note. `data-testid="emerge-port-map-preview"`.
- [x] Run: `npm run typecheck` and `npm run check:legal`
- [x] Commit: `feat(emerge): show port→BC info in experimental Run dialog`

**Done when:** Both forms show the info panel; legal + typecheck pass.

---

## Task 3: Backlog note

**Model tier:** cheap

- [x] Update backlog item 4: info-panel slice done; auto-suggest still open. Point at this plan.
- [x] Commit: `docs(agent): note Run port-map info panel on backlog item 4`

---

## Explicitly dropped (human decision 2026-11-06)

- `preview_ports` in Python for the UI
- `POST /api/research/emerge/port-map`
- `api.emergePortMapPreview`

(Those two commits were reset; do not reintroduce.)

---

## First task after approval

**Task 1** — TS mirror + parity test.
