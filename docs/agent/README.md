# Agent development setup (fork)

This fork (`engineerman/fairbeam`, branch `feat/emerge-experimental`) uses a **split-brain** agent workflow:

1. A **capable model** writes the plan and Global Constraints.
2. **Cheaper models** implement one plan task at a time.
3. A **mid / capable model** reviews before the next task.

Upstream Fairbeam rules still apply: [AGENTS.md](../../AGENTS.md), [AI_POLICY.md](../../AI_POLICY.md), [CONTRIBUTING.md](../../CONTRIBUTING.md).

## Quick start (Cursor)

1. Open this repo (`D:\W\P\fairbeam`) on branch `feat/emerge-experimental`.
2. Start a chat with a **Planner-tier** model.
3. Say: *Use the emerge-agent-workflow skill. Write or update the EMerge plan.*
4. Approve the plan under `docs/agent/plans/`.
5. Start a **new** chat (or subagent) on a **cheap** model: *Implement task N from `<plan-file>`. Use the emerge-agent-workflow skill.*
6. After each task, run the plan's checks; then a short reviewer pass.
7. Commit on the topic branch; name the model in `Co-Authored-By:`.

Cursor loads:

- `.cursor/rules/agent-roles.mdc` (always)
- `.cursor/rules/emerge-experimental.mdc` (when EMerge paths are in play)
- `.cursor/skills/emerge-agent-workflow/` (when the skill matches)

## Layout

```
docs/agent/
  README.md                 ← this file
  SCOPE.md                  ← A / B / C integration scope
  prompts/planner.md
  prompts/implementer.md
  prompts/reviewer.md
  plans/TEMPLATE.md
  plans/YYYY-MM-DD-*.md     ← living plans (checkboxes)

.cursor/rules/              ← persistent role + EMerge constraints
.cursor/skills/emerge-agent-workflow/
```

## Cost control

| Do | Don't |
| --- | --- |
| Plan once on a strong model | Re-plan every implementer turn |
| One task, one cheap agent | Paste the whole repo into a cheap model |
| Mid-tier for multi-file glue | Cheapest model on license/architecture calls |
| Strong model for final branch review | Skip checks because the model "looks fine" |

## Human gates

Stop and ask before: shipping EMerge in the default installer, widening geometry beyond the plan, claiming validation, or combining EMerge source into the Fairbeam tree in a way that conflicts with GPL-2.0-only vs GPL-3.0-or-later.
