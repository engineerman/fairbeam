# Experimental solvers

openEMS is the default solver. **Elmer FEM — Experimental eigenmodes**, **Elmer FEM · Experimental antenna**, the fixed **EMerge** WR-90 waveguide fixture, and **EMerge FEM · Experimental** (unified N-port Design path: driven/lumped or planar microstrip recipes, up to 8 ports) are opt-in research paths with narrower geometry and result support. Installing a backend or completing a run does not establish numerical accuracy for your design.

## Active engine (Simulation ribbon)

In the desktop designer, **Simulation › Solver** lets you pick **openEMS** or **EMerge (experimental)** as the session’s active engine. openEMS is the default on a new session. Choosing EMerge retargets Run chrome (label and accent), Frequency / Boundaries / Mesh settings, and which Simulation / Post / Optimize actions stay enabled. It does not replace openEMS as the product default, and it does not make EMerge a validated production solver.

Elmer and the fixed EMerge waveguide fixture stay under **Experimental solvers** / the Run dialog’s longer option list — they are not a third chrome accent in this picker. **Optimize** (Sweep / Optimizer) stays disabled while EMerge is active; that path is deferred. Mesh view under EMerge draws the experimental FEM **exterior surface** wireframe after Generate mesh (or an EMerge result that exported surface edges). It never shows the openEMS FDTD grid as if it were the tetrahedral mesh.

See the agent plan [`docs/agent/plans/2026-11-04-emerge-solver-scoped-ui.md`](agent/plans/2026-11-04-emerge-solver-scoped-ui.md) for the capability matrix and remaining follow-ups.

## Setup in the desktop app

Open **Simulation › Experimental solvers**, or use **Elmer setup and history** in the Run dialog. Choose a backend and check availability before submitting a run.

On Windows, **Install Elmer** downloads the portable package pinned by Fairbeam after you request it. The package is checked and stored in the app's data folder, separately from the openEMS runtime. It is not a system-wide installation. Leave the path blank to use the managed copy. A folder you enter, `FAIRBEAM_ELMER_ROOT`, or Elmer on `PATH` takes precedence.

On macOS and Linux, install Elmer yourself. Select an installation containing `bin/ElmerSolver` and `bin/ElmerGrid`, or its binary directory. Availability checks locate the executables; they do not qualify the physical model or every native dependency. No backend is installed automatically.

If an installed app reports `No module named fairbeam_elmer` or `No module named fairbeam_emerge`, update or repair Fairbeam itself. Installing Elmer or EMerge alone does not provide Fairbeam's Python adapters. Source contributors should use the separate [research setup and evidence](RESEARCH-SOLVERS.md).

## EMerge waveguide fixture

Choose the **EMerge** backend in Simulation → Experimental solvers for the fixed WR-90 air-filled waveguide fixture only. Level A does not translate the current Design. Select `coarse` or `fine` resolution and submit; results are checked against the analytic straight-waveguide reference in the Research panel.

On Windows, **Install EMerge** creates a pinned Python 3.13 virtual environment with `emerge==3.0.0b12` from PyPI (hash-locked). The Research panel shows the EMerge GPL-2.0-or-later notice and the Intel MKL proprietary license before the Install button. The locked download set is about 399 MiB (418619020 bytes, PyPI wheel sizes 2026-11-04). A measured managed install of `3.0.0b12` on 2026-11-04 was 1421133962 bytes (1355.3 MiB) after 80.9 s. Leave the path blank to use that managed copy. A folder you enter, or `FAIRBEAM_EMERGE_PYTHON`, takes precedence. Nothing is installed system-wide, and EMerge is not bundled in the Fairbeam installer.

On macOS and Linux there is no managed installer. Create your own Python 3.10–3.13 environment with `emerge==3.0.0b12`, then enter that environment's folder (or its Python executable) in the path field, or set `FAIRBEAM_EMERGE_PYTHON`.

See [the EMerge experiment](EMERGE-EXPERIMENT.md) for the fixture definition, acceptance criteria and recorded native observations.

## EMerge FEM · Experimental (unified N-port)

When the run server reports health `emerge` ≥ 3, **Run** offers **EMerge FEM · Experimental** after
the Elmer options. One entry covers both Design recipes: driven/lumped (axis-aligned dielectric
boxes and metal sheets) and planar microstrip/Discrete (single-layer board with bottom ground and
z-normal copper on the top). Port count may be **1…8** of one homogeneous type; mixed types,
multilayer, vias, CPW, curves and unsupported geometry are rejected. Approximate maps keep the
existing `accept_*` gates. Enclosure / air / padding appear when the Design classifies as planar.
No far field and no gain certificate; status is `results_exported`. Shared Results show the
complete N×N experimental S matrix next to (never instead of) openEMS.

Resolutions are wavelength fractions at `f_max`: `coarse` = 0.25, `fine` = 0.15. Points 3–41.
Driven-class worker timeout is 1800 s with a volume proxy; planar-class timeout is 3600 s with a
tetrahedra proxy (400000). Schema `fairbeam.emerge-result/2`.

Recorded Patch and hairpin native numbers (and the honesty statements that EMerge does not claim
openEMS S-parameter agreement) stay in [EMerge experiment](EMERGE-EXPERIMENT.md).

## Eigenmodes of the current design

Save the design, open **Run**, and select **Elmer FEM — Experimental eigenmodes**. Review the enclosure bounds in millimeters, maximum cell size and target frequency. Explicitly accept the closed PEC enclosure: all six faces are conducting walls, not an open radiation boundary.

This path accepts axis-aligned box volumes with constant, positive, lossless isotropic dielectric properties or PEC. It rejects overlaps, ports, lumped elements, sheets, curves, transforms, cuts, loss and dispersion. The solver searches for two modes near the target frequency; these need not be the lowest modes.

The bounded solve allows up to 4,000 elements and 10,000 nodes, one CPU thread and 120 seconds of native execution. Results are eigenfrequencies and retained fields/logs, not antenna S parameters, gain or a radiation pattern. Completion is recorded as `results_exported`, not `results_validated`.

## Driven antenna experiments

Choose **Elmer FEM · Experimental antenna** for a design made of axis-aligned dielectric boxes and PEC sheets, with one ideal line discrete port. Accept the finite rectangular FEM terminal width and review air padding, mesh size and frequency samples. Both terminal ends must contact PEC sheets. These settings belong to the FEM snapshot; the original design and openEMS setup remain unchanged.

The open region uses first-order absorbing boundaries, not PML. Finite-conductivity metals are approximated as PEC in the FEM snapshot, so conductor loss is omitted and affected materials are recorded. Curves, transforms, cuts, additional lumped components and multiple ports are rejected.

Limits are 10,000 cells, 3–21 sweep samples plus the requested far-field frequency, one CPU thread and 180 seconds per frequency. Results include complex S11, a normalized 3D pattern and directivity cuts; gain and efficiency are not provided. Exported results are not a convergence certificate. Review the [recorded experiments and outstanding qualification](RESEARCH-SOLVERS.md) before interpreting a new model.

## Queue, results and cancellation

Experimental runs use the shared serial queue. Inspect failures, raw inputs, settings, meshes and logs in solver history. Closing the panel does not cancel a run; use the queue's cancellation control. Interrupted work is retained rather than automatically restarted.

History keeps the input snapshot and hashes with each run. Experimental results do not replace the current openEMS antenna result in the viewer. Compare mesh levels and appropriate physical references yourself before drawing an engineering conclusion.

## Other experimental workflows

**Coaxial TEM (experimental)** is an openEMS port workflow with specific geometry and release limits; see [Coaxial ports](COAXIAL-PORTS.md). It is not an Elmer installation option.

The periodic-cell experiment requires a separately built research backend. Stock openEMS and the normal GPU engine are not substitutes. Its supported scope is normal incidence, zero x/y phase shift and co-polar fundamental reflection/transmission below the first vacuum diffraction threshold. General Floquet ports, oblique incidence and higher-order modes are not implemented. See the [research notes](RESEARCH-SOLVERS.md#periodic-unit-cell) for prerequisites and retained numerical evidence.
