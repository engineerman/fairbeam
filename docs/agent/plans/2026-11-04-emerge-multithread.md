# EMerge multi-thread sweeps

> Implementer plan (post pin `3.0.0b12`).

**Goal:** Use EMerge 3.0 multi-threaded / distributed frequency sweeps so Fairbeam research jobs are not stuck at 1 CPU thread.

**Approach:** Pass host `auto_threads` into the emerge case; set BLAS/OMP env to that count; call
`run_sweep(nthreads=…)` **sequentially** (one frequency at a time). Keep process isolation (one
worker process).

## Global Constraints

- openEMS stays default; EMerge opt-in experimental.
- Still one Fairbeam research job at a time (queue concurrency 1).
- Do **not** use `run_sweep_distributed` for Fairbeam jobs: concurrent SuperLU factorizations OOM
  on planar hairpin-class meshes (measured job `20261104-204027-177887`:
  `Can't expand MemType` / `memory allocation … failed`, exit `3221226505`).
- Docs numbers from measured runs only.
- Branch `feat/emerge-experimental`.

## Tasks

- [x] Wire `threads` from `submit_research` (auto) → adapter → case → worker
- [x] Replace forced `*=1` thread env + `run_sweep(parallel=False…)` with 3.0 API
- [x] Update unit tests / raw solver_setup fields
- [x] Drop distributed frequency workers; keep sequential `run_sweep(nthreads=…)` only
- [ ] Restart serve; short smoke optional

---
