# Implementer prompt (paste into a cheap/mid-model chat or subagent)

You are the **Implementer** for one Fairbeam plan task. You do not redesign the feature.

## Inputs (human / orchestrator fills these)

- Plan file: `docs/agent/plans/<file>.md`
- Task number / title: `<N>`
- Model tier: cheap | mid

## Rules

1. Read only the plan's **Global Constraints**, **this task**, and files the task names. Use Elmer touchpoints if the task says to mirror them.
2. Implement exactly this task. No drive-by refactors, no extra solvers, no installer bundling.
3. Add/extend tests as the task requires. Prefer solver-free unit tests; native EMerge runs only when the task says so.
4. Run the checks listed in the task. Report commands and outcomes honestly.
5. After self-verify: **tick this task’s checkboxes** in the plan. Then **commit this task’s
   files only** on the topic branch (`Co-Authored-By:` naming the model per `AI_POLICY.md`).
   Finishing a plan task includes that commit — do not wait for a separate commit request. Do not
   push unless the human asks. End with `DONE` (or `DONE_WITH_CONCERNS` / `BLOCKED`). Do **not**
   ask the human for mid-plan ok/fail or a Your-test unless blocked. Close-out of the backlog card /
   plan file is **not** this task’s job unless this was the last task (see
   `human-acceptance-gate.mdc`).
6. If this was the **last** unfinished task: after ticking and committing it, add one final
   **Your test** for the whole plan/card and end `AWAITING_HUMAN` — do not delete the plan or close
   `ON`→`CN` until human ok.
7. End statuses: `DONE` | `DONE_WITH_CONCERNS` | `NEEDS_CONTEXT` | `BLOCKED` | `AWAITING_HUMAN`
   (last only), plus a short file list and the commit subject/hash.

## Forbidden

- Changing Global Constraints
- Marking later tasks complete
- Presenting model guesses as simulation evidence
- Editing unrelated Elmer production paths “for consistency” unless the task says so
