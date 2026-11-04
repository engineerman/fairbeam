# Mission (this fork)

**Primary goal:** Integrate **EMerge** (open-source frequency-domain FEM, PyPI `emerge`) into **Fairbeam** as an **optional experimental solver backend**, following the existing Elmer experimental pattern — not replacing openEMS.

## One-liner for agents

When the human says **start**, **continue**, or **go** on branch `feat/emerge-experimental` with no other topic: you are working on **Fairbeam ← EMerge experimental integration** (Level A first: discover/install + fixed fixture; then Level B: bounded Design subset). Read `docs/agent/SCOPE.md`, then the newest plan under `docs/agent/plans/`. If no plan exists, run the Planner flow before coding.

## Success looks like

- User can opt in to EMerge from Fairbeam (Install / path), run a bounded case, and see results in Fairbeam’s experimental/results flow.
- openEMS remains the default production path.
- Geometry outside the accepted subset is rejected explicitly.
- Limits and qualification are documented honestly.

## Not the mission

- Full solver parity with openEMS
- Shipping EMerge inside the default first-run installer
- Rewriting Fairbeam’s core designer around FEM
