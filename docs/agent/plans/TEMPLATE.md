# EMerge … Implementation Plan

> **For agentic workers:** Use `.cursor/skills/emerge-agent-workflow`. Implement task-by-task with checkbox tracking. Planner = capable model; implementer = cheap/mid.

**Goal:** One sentence.

**Architecture:** 2–3 sentences (Elmer-parallel adapters, opt-in install, result schema).

**Tech Stack:** Fairbeam Python + SolidJS/TS; EMerge via managed venv; unittest + npm checks.

## Global Constraints

- openEMS remains the default solver.
- EMerge is opt-in experimental only; no stock-installer bundle in level A/B.
- GPL posture: external optional EMerge; do not vendor EMerge sources into Fairbeam without review.
- Unsupported geometry is rejected, never silently dropped.
- UI strings: `en.json` + `tr.json`. Pass `npm run check:legal`.
- Docs numbers require reproducible runs.
- Branch: `feat/emerge-experimental` (or named topic branch). Follow `AI_POLICY.md` trailers.

---

## File map

| File | Responsibility |
| --- | --- |
| `python/fairbeam/emerge_runtime.py` | … |

---

## Task 1: …

**Model tier:** cheap | mid

**Files:** …

**Steps:**

- [ ] …
- [ ] Run: `…`
- [ ] Commit: `…`

**Done when:** …
