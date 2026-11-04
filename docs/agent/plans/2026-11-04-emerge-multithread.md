# EMerge multi-thread sweeps

> Implementer plan (post pin `3.0.0b12`).

**Goal:** Use EMerge 3.0 multi-threaded / distributed frequency sweeps so Fairbeam research jobs are not stuck at 1 CPU thread.

**Approach:** Pass host `auto_threads` into the emerge case; set BLAS/OMP env to that count; call `run_sweep(nthreads=…)` or `run_sweep_distributed` when several frequencies and threads allow. Keep process isolation (one worker process); no EMerge process-pool by default (`worker_type="thread"`).

## Global Constraints

- openEMS stays default; EMerge opt-in experimental.
- Still one Fairbeam research job at a time (queue concurrency 1).
- Cap workers to limit memory (each distributed worker holds a factorization).
- Docs numbers from measured runs only.
- Branch `feat/emerge-experimental`.

## Tasks

- [x] Wire `threads` from `submit_research` (auto) → adapter → case → worker
- [x] Replace forced `*=1` thread env + `run_sweep(parallel=False…)` with 3.0 API
- [x] Update unit tests / raw solver_setup fields
- [ ] Restart serve; short smoke optional

---
