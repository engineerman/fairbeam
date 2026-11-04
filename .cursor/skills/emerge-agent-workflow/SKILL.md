---
name: emerge-agent-workflow
description: >-
  Plan and implement Fairbeam EMerge experimental integration with a capable
  planner model and cheaper implementer models. Use when working on
  feat/emerge-experimental, EMerge adapter, Install EMerge, or docs/agent plans.
---

# EMerge agent workflow

## When to use

Any non-trivial work on the EMerge experimental backend in this fork: fixture MVP, Design subset, Install EMerge, UI Run entries, tests, or agent plans.

## Procedure

1. **Read** `docs/agent/README.md` and the latest plan in `docs/agent/plans/` (if any).
2. **If no plan or plan is stale:** switch to / stay on a **Planner**-tier model. Produce or update a plan using `docs/agent/prompts/planner.md` and the template in `docs/agent/plans/TEMPLATE.md`. Save as `docs/agent/plans/YYYY-MM-DD-emerge-<slug>.md`.
3. **Execute tasks** with **Implementer**-tier models, one task at a time, using `docs/agent/prompts/implementer.md`. Prefer the Elmer file map in `references/elmer-touchpoints.md`.
4. After each task: run the checks listed in that task; then a **Reviewer** pass with `docs/agent/prompts/reviewer.md`.
5. Mark checkboxes in the plan file. Commit on the topic branch with `Co-Authored-By:` naming the model (`AI_POLICY.md`).
6. Stop and escalate to the human (or Planner) on BLOCKED, license doubt, or physics/validation ambiguity.

## Model tiers (Cursor)

| Tier | Use for |
| --- | --- |
| Planner / final review | Spec, architecture, Global Constraints, whole-branch review |
| Mid | Multi-file integration, adapter↔UI wiring, hard debug |
| Cheap | Single-task implementation from a complete plan step, tests that follow a clear pattern |

Never let a cheap model rewrite the plan's Global Constraints.

## Out of scope for implementers

- Replacing openEMS as default
- Full EMerge feature parity
- Bundling EMerge into the stock desktop installer
- Silent geometry coercion
