# Agent development setup (fork)

## Why this fork exists

**Mission:** integrate **EMerge** into **Fairbeam** as an optional experimental solver (frequency-domain FEM), using the Elmer experimental pattern. openEMS stays default. Details: [MISSION.md](MISSION.md), [SCOPE.md](SCOPE.md).

If you are told only **start** / **continue** / **go** on `feat/emerge-experimental`, that mission is the task — pick the next card from [BACKLOG-emerge-port-map.md](BACKLOG-emerge-port-map.md).

This fork (`engineerman/fairbeam`, branch `feat/emerge-experimental`) also uses a **split-brain** agent workflow:

1. A **capable model** writes the plan and Global Constraints.
2. **Cheaper models** implement one plan task at a time.
3. A **mid / capable model** reviews before the next task.

Upstream Fairbeam rules still apply: [AGENTS.md](../../AGENTS.md), [AI_POLICY.md](../../AI_POLICY.md), [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Quick start (Cursor)

1. Open this repo (`D:\W\P\fairbeam`) on branch `feat/emerge-experimental`.
2. Read the backlog dashboard; human names (or activates) one card.
3. Start a chat with a **Planner-tier** model: *Write the plan for card \<title\>.*
4. Approve the plan under `docs/agent/plans/`.
5. Start a **new** chat (or subagent) on a **cheap** model: *Implement task N from `<plan-file>`. Use the emerge-agent-workflow skill.*
6. After each task, run the plan's checks; then a short reviewer pass.
7. Commit on the topic branch; name the model in `Co-Authored-By:`.
8. When the plan is fully done, **delete** the plan file (keep only active/open plans under `plans/`).

Cursor loads:

- `.cursor/rules/agent-roles.mdc` (always)
- `.cursor/rules/emerge-experimental.mdc` (when EMerge paths are in play)
- `.cursor/skills/emerge-agent-workflow/` (when the skill matches)

## Layout

```
docs/agent/
  README.md                      ← this file
  MISSION.md / SCOPE.md          ← fork goal + current / out-of-scope
  BACKLOG-emerge-port-map.md     ← only resume board (open / parked cards)
  HANDOFF-*.md                   ← optional one-shot briefs for a fresh chat (delete when O-card closes)
  specs/                         ← living designs still in use
  prompts/planner.md
  prompts/implementer.md
  prompts/reviewer.md
  plans/TEMPLATE.md
  plans/YYYY-MM-DD-*.md          ← active plans only (delete when done)

.cursor/rules/                   ← persistent role + EMerge constraints
.cursor/skills/emerge-agent-workflow/
```

## Cost control

| Do | Don't |
| --- | --- |
| Plan once on a strong model | Re-plan every implementer turn |
| One task, one cheap agent | Paste the whole repo into a cheap model |
| Mid-tier for multi-file glue | Cheapest model on license/architecture calls |
| Strong model for final branch review | Skip checks because the model "looks fine" |
| Delete finished plans/specs | Keep shipped history in `docs/agent/` |

## Human gates

Stop and ask before: shipping EMerge in the default installer, widening geometry beyond the plan, claiming validation, or vendoring EMerge source or binaries into the Fairbeam tree (see the license posture in [SCOPE.md](SCOPE.md)).
