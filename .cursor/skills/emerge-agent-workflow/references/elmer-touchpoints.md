# Elmer touchpoints to mirror for EMerge

Read these before inventing new structure. Prefer parallel names (`emerge_*`) over new frameworks.

## Python

| Elmer | Role |
| --- | --- |
| `python/fairbeam_elmer.py` | Standalone opt-in CLI / discover / capabilities |
| `python/fairbeam/elmer_runtime.py` | Managed Windows download, pin URL/SHA, install status |
| `python/fairbeam/elmer_design.py` | Design → FEM snapshot (eigenmodes path) |
| `python/fairbeam/elmer_driven.py` | Driven antenna path |
| `python/fairbeam/elmer_bundle.py` | Result packaging |
| `python/fairbeam/fem_geometry.py` | Shared FEM geometry helpers |
| `python/fairbeam/research.py` / `research_plan.py` | Experimental research panel jobs |
| `python/fairbeam/server.py` | Run server hooks for experimental solvers |
| `python/tests/test_elmer_*.py` | Pattern for solver-free + bounded tests |

## UI / docs

| Path | Role |
| --- | --- |
| `src/designer/ElmerDesignRun.tsx` | Eigenmode Run UI |
| `src/designer/ElmerAntennaRun.tsx` | Driven antenna Run UI |
| `src/designer/ElmerAntennaResults.tsx` | Results tabs |
| `src/designer/elmerDomain.ts` | Domain helpers |
| `docs/EXPERIMENTAL-SOLVERS.md` | User-facing experimental docs |
| `docs/RESEARCH-SOLVERS.md` | Qualification / limits |
| `docs/ELMER-EXPERIMENT.md` | Fixed cavity fixture |

## Suggested EMerge MVP order

1. Discover / capabilities + managed install sketch (`emerge_runtime`)
2. Fixed fixture (cavity or waveguide) → shared result shape
3. Optional Design subset (reject-heavy)
4. Run dialog entry + i18n
5. Docs + qualification notes
