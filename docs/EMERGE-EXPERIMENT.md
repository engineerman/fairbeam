# Experimental external EMerge (waveguide fixture and Design subset)

Fairbeam includes a separate, opt-in `fairbeam-emerge` research command. It discovers an external
EMerge Python environment. Only a worker process started inside that environment imports EMerge;
the Fairbeam process does not import `emerge`, `gmsh` or `emsutil`. Normal Fairbeam projects,
runtime setup and the default openEMS simulation path are unchanged. No EMerge wheels are bundled
in the Fairbeam installer or installed without an explicit user action.

**Level A** runs one fixed, lossless, air-filled WR-90 rectangular waveguide with two waveguide
ports (no user Design). **Level B** admits a bounded Design subset (axis-aligned dielectric boxes,
PEC sheets, one discrete port) through the Run dialog option **EMerge · Experimental antenna** and
the `design` CLI subcommand. Both paths are opt-in experimental; Design results are exported as
`results_exported`, never `results_validated`.

## Run

Use Python 3.10+ from the repository, or install the Python package to obtain the separate
`fairbeam-emerge` entry point. Point `--root` (or `FAIRBEAM_EMERGE_PYTHON`) at a virtual-environment
folder that contains EMerge 3.0.0b12, or at that environment's Python executable. There is no PATH
lookup.

```powershell
python python/fairbeam_emerge.py --root $env:LOCALAPPDATA\org.fairbeam.desktop\emerge\3.0.0b12 capabilities
python python/fairbeam_emerge.py --root $env:LOCALAPPDATA\org.fairbeam.desktop\emerge\3.0.0b12 waveguide --experimental --resolution coarse --out E:/research/wr90-coarse
python python/fairbeam_emerge.py --root $env:LOCALAPPDATA\org.fairbeam.desktop\emerge\3.0.0b12 waveguide --experimental --resolution fine --out E:/research/wr90-fine
```

On Windows, **Install EMerge** in Simulation → Experimental solvers creates the managed environment
above (hash-locked `emerge==3.0.0b12` and its dependencies from PyPI). Leave the path blank to use that
copy after install. On other platforms, create your own Python 3.10–3.13 environment with
`emerge==3.0.0b12` and enter its folder, or set `FAIRBEAM_EMERGE_PYTHON`.

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
EMerge 3.0.0b12 (and the earlier 2.8.9 pin) use the same native convention for this fixture; the
adapter does not conjugate.

Native Windows managed EMerge **2.8.9**, recorded 2026-11-04 (before the 3.0.0b12 pin), produced:

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
mesh-convergence certificate. The fixture path still does not translate an arbitrary project
geometry; Design translation is the separate Level B path below.

Raw worker inputs (`case.json`), `raw.json`, `result.json`, `manifest.json` and `worker.log` remain
in each run directory. Manifests record the worker and Python SHA-256 hashes. Fixture results are
separate research files; Design runs also write a shared Results bundle (S11 / Zin, empty far field).

## Level B: bounded Design subset (driven discrete port)

Admission mirrors Elmer's driven rules for the same geometry class: axis-aligned dielectric boxes
and PEC sheets, exactly one lumped (Discrete) port, no resistors / lumped elements / transforms /
cuts / voids, no overlapping dielectrics. An ideal line feed is widened only with explicit
`accept_finite_feed` and `feed_width_mm`. Finite-conductivity metals require explicit
`approximate_metals`. Nonzero `tan_d` is admitted as EMerge's constant loss tangent (recorded as a
limitation). The air box is the parts+feed bounding box plus `padding_mm` on every side, with
second-order absorbing boundaries on all six faces (not PML). Unsupported geometry raises
`ValueError`; nothing is dropped silently.

Frozen settings (Task 5 / Task 6): resolutions `coarse` = 0.25 and `fine` = 0.15 (wavelength
fraction at `f_max`); worker timeout 1800 s; refuse before launch when the air-box volume proxy
exceeds 200000. Sweep: `f_min_hz`…`f_max_hz`, 3–21 linspace points. Schema
`fairbeam.emerge-driven-result/1`, status `results_exported`, `precision_converged: false`,
`gain_qualified: false`, no far field.

```powershell
# after emerge_design.admit → case.json
python python/fairbeam_emerge.py --root $env:LOCALAPPDATA\org.fairbeam.desktop\emerge\3.0.0b12 design --experimental --case case.json --out E:/research/patch-coarse
```

In the app, open **Run**, choose **EMerge · Experimental antenna** (shown when health `emerge` ≥ 2),
accept the finite feed, and submit. openEMS remains available in the same dialog.

### Patch class — recorded native observations (2026-11-04)

Built-in `blank_design("p", "Patch")`, `feed_width_mm=1`, `padding_mm=40`, 2.0–3.0 GHz × 11 points,
`approximate_metals` false (template metal has no conductivity). Managed EMerge **2.8.9** on Windows
(recorded 2026-11-04, before the 3.0.0b12 pin):

| Run | Resolution | Nodes / tets | Solver elapsed | S11 min (linspace) | max \|S11\| |
|---|---|---|---|---|---|
| EMerge Design | coarse (0.25) | 474 / 1975 | 11.517 s | 2.30 GHz, −7.427 dB | 0.982634 |
| EMerge Design | fine (0.15) | 1141 / 5245 | 16.469 s | 2.30 GHz, −6.349 dB | 0.984801 |

Same template through Fairbeam's normal openEMS Run path (design mesh 20 cells/wavelength, band
`f0*0.6`–`f0*1.3`, 801 frequency points): S11 minimum **2.453981250 GHz** at **−45.574 dB**,
`mesh.total_cells=112320`, solver 35.2 s, converged.

Level B does **not** claim S11 agreement between EMerge Design and openEMS for this class. The
EMerge linspace minimum sat at 2.30 GHz on both meshes (about 6.3% below the openEMS minimum
frequency); match depth was far shallower. Coarse→fine kept the same frequency bin while `|S11|`
there rose from 0.425 to 0.481. Port model and absorbing-boundary differences are expected; results
stay experimental exports.

## License and distribution

EMerge is installed only on request. The managed Windows path downloads the hash-locked dependency
set in `python/fairbeam/emerge_lock/win_amd64-cp313.txt` (50 wheels for pin `3.0.0b12`, estimated
download 418619020 bytes / about 399 MiB from PyPI wheel sizes on 2026-11-04) into the app data
folder. Managed install of pin `3.0.0b12` on 2026-11-04 measured **1421133962 bytes (1355.3 MiB)**
after an **80.9 s** install. An earlier `2.8.9` folder measured 1567317171 bytes (1494.7 MiB) after
74.7 s. Nothing from that set is shipped inside the Fairbeam installer.

Component license fields recorded from the installed packages and their upstream notices:

- EMerge 3.0.0b12: GPL-2.0-or-later (package headers; wheel LICENSE is GPL-2 text)
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
