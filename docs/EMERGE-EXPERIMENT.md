# Experimental external EMerge waveguide fixture

Fairbeam includes a separate, opt-in `fairbeam-emerge` research command. It discovers an external
EMerge Python environment and runs one fixed, lossless, air-filled WR-90 rectangular waveguide with
two waveguide ports. This standalone command does not import `fairbeam`, openEMS or CSXCAD. Only a
worker process started inside the EMerge environment imports EMerge. The same fixed fixture is
available through the [experimental research panel](RESEARCH-SOLVERS.md). Level A accepts no user
design: any other geometry, frequency list or resolution is rejected. Normal Fairbeam projects,
runtime setup and the default openEMS simulation path are unchanged. No EMerge wheels are bundled
in the Fairbeam installer or installed without an explicit user action.

## Run

Use Python 3.10+ from the repository, or install the Python package to obtain the separate
`fairbeam-emerge` entry point. Point `--root` (or `FAIRBEAM_EMERGE_PYTHON`) at a virtual-environment
folder that contains EMerge 2.8.9, or at that environment's Python executable. There is no PATH
lookup.

```powershell
python python/fairbeam_emerge.py --root $env:LOCALAPPDATA\org.fairbeam.desktop\emerge\2.8.9 capabilities
python python/fairbeam_emerge.py --root $env:LOCALAPPDATA\org.fairbeam.desktop\emerge\2.8.9 waveguide --experimental --resolution coarse --out E:/research/wr90-coarse
python python/fairbeam_emerge.py --root $env:LOCALAPPDATA\org.fairbeam.desktop\emerge\2.8.9 waveguide --experimental --resolution fine --out E:/research/wr90-fine
```

On Windows, **Install EMerge** in Simulation → Experimental solvers creates the managed environment
above (hash-locked `emerge==2.8.9` and its dependencies from PyPI). Leave the path blank to use that
copy after install. On other platforms, create your own Python 3.10–3.13 environment with
`emerge==2.8.9` and enter its folder, or set `FAIRBEAM_EMERGE_PYTHON`.

`capabilities` does not launch the solver: availability means the environment and `emerge` dist-info
were found, not that every native dependency has been exercised. `--experimental` is required for
execution. Output must be a new directory; existing cases are never overwritten. Only resolutions
`coarse` (0.25) and `fine` (0.125) — EMerge wavelength fractions at the top frequency — and the
fixed WR-90 geometry are supported. The worker runs with one OpenMP/BLAS/Numba thread, a 600-second
timeout, and no parallel sweep. Failed or interrupted manifests and `worker.log` are retained; a
successful exit that fails the analytic checks is recorded as `validation_failed` with raw output
kept.

## Physical reference and actual native Windows observations

The fixture is a straight WR-90 air-filled rectangular waveguide: broad wall a = 22.86 mm (x),
narrow wall b = 10.16 mm (y), length L = 50.0 mm (z). Walls are PEC; the fill is vacuum/air
(εr = 1, μr = 1, lossless). Ports are `RectangularWaveguide` TE10 on the z = 0 and z = L faces.
Frequencies are exactly 8.0, 9.0, 10.0, 11.0 and 12.0 GHz. TE10 cutoff is c0/(2a) = 6.557 GHz; the
next mode TE20 is at 13.11 GHz, so the band is single-mode. c0 = 299792458 m/s.

The analytic reference uses Fairbeam's `exp(+i omega t)` phasor convention with reference planes at
the port faces: k0 = 2πf/c0, β = sqrt(k0² − (π/a)²), S21 = S12 = exp(−i β L), S11 = S22 = 0.
EMerge 2.8.9 uses the same native convention for this fixture; the adapter does not conjugate.

Native Windows managed EMerge 2.8.9, recorded 2026-11-04, produced:

| Resolution | Wavelength fraction | Nodes / tetrahedra | Solver elapsed | max \|S11\| | min \|S21\| | max phase error |
|---|---|---|---|---|---|---|
| coarse | 0.25 | 163 / 397 | 160.945 s | 0.005462 | 0.999896 | 0.789° |
| fine | 0.125 | 667 / 2305 | 9.223 s | 0.000119 | 0.999993 | 0.037° |

Both runs reported `results_validated`. Wall-clock times were 164.8 s (coarse) and 11.2 s (fine);
the first (coarse) run paid a cold Numba JIT cost, and the second (fine) reused the warm cache.
Per-frequency values from the coarse `result.json`:

| f (GHz) | \|S11\| | \|S21\| | phase error (°) |
|---|---|---|---|
| 8 | 0.000151 | 0.999961 | 0.120 |
| 9 | 0.000533 | 0.999956 | 0.188 |
| 10 | 0.000629 | 0.999947 | 0.308 |
| 11 | 0.001578 | 0.999932 | 0.499 |
| 12 | 0.005462 | 0.999896 | 0.789 |

Fine-run aggregates: max \|S11\| = 0.000119, min \|S21\| = 0.999993, max phase error = 0.037°,
max passivity |S11|²+|S21|² = 0.999992 (coarse passivity max = 0.999922).

Acceptance (frozen from these runs; the coarse case is the worst case) requires:

- max over frequencies of \|S11\| ≤ 0.02
- min over frequencies of \|S21\| ≥ 0.995
- max over frequencies of wrapped \|arg(S21) − (−β L)\| ≤ 2 degrees
- \|S11\|² + \|S21\|² ≤ 1.005 at every frequency
- all values finite; frequencies exactly the fixture list in order

Pass → `status: "results_validated"`; fail → `"validation_failed"` (raw output kept).
`precision_converged` is always `false`. This is a coarse feasibility fixture, not a
mesh-convergence certificate. No antenna S-parameter bundle, driven-port Design translation,
radiation boundary, far field, lossy materials or arbitrary project geometry are supported.

Raw worker inputs (`case.json`), `raw.json`, `result.json`, `manifest.json` and `worker.log` remain
in each run directory. Manifests record the worker and Python SHA-256 hashes. Machine-readable
results are separate research files, not viewer antenna bundles.

## License and distribution

EMerge is installed only on request. The managed Windows path downloads the hash-locked dependency
set in `python/fairbeam/emerge_lock/win_amd64-cp313.txt` (52 wheels, 461988175 bytes / about
441 MiB download, measured 2026-11-04) into the app data folder. The installed managed folder for
version 2.8.9 measured 1567317171 bytes (1494.7 MiB) after a 74.7 s install on 2026-11-04. Nothing
from that set is shipped inside the Fairbeam installer.

Component license fields recorded from the installed packages and their upstream notices:

- EMerge 2.8.9: GPL-2.0-or-later (package headers; wheel LICENSE also notes Gmsh-derived parts)
- gmsh: GPLv2+ (wheel METADATA)
- emsutil 0.8.3: no license field in the wheel; the upstream repository LICENSE is MIT, while
  `material.py` and `pyvista/display.py` in the wheel carry GPL-2.0-or-later headers
- Intel MKL and its companion runtime packages (`mkl`, `intel-openmp`, `onemkl-license`, and related
  wheels in the lock): Intel Simplified Software License (proprietary; redistributable under Intel's
  terms, installed from PyPI only when the user requests Install EMerge)

Fairbeam remains GPL-3.0-or-later. This feature uses only an external optional Python environment
and ships no third-party solver binaries. The Research panel shows the EMerge and Intel MKL license
notes before the Install button.

## Tests

```powershell
$env:PYTHONPATH = "python"
$env:OPENEMS_INSTALL_PATH = "$env:LOCALAPPDATA\org.fairbeam.desktop\runtime\openEMS"
.\.venv\Scripts\python.exe -m unittest discover -s python/tests -p "test_emerge_*.py" -q
```

These solver-free tests exercise discovery, capabilities, analytic assessment, research-queue
admission, import isolation and the managed-venv installer without network. Real native runs are
separate and explicitly authorized with `--experimental` or the Research panel Install / Run flow.
