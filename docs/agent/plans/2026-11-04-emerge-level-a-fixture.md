# EMerge Level A — Managed install + fixed waveguide fixture

> **For agentic workers:** Use `.cursor/skills/emerge-agent-workflow`. Implement task-by-task with
> checkbox tracking. Planner = capable model; implementer = cheap/mid. Read **Global Constraints**,
> **Shared facts** and **your task only**.

**Goal:** A Fairbeam user can opt in to EMerge (managed install on Windows or their own Python
environment elsewhere), run one fixed WR-90 waveguide fixture through the research queue, and see
S-parameters checked against the analytic reference in the Research panel.

**Architecture:** Mirror the Elmer research path. `emerge_runtime.py` (like `elmer_runtime.py`)
creates a pinned, hash-locked virtual environment in the app data folder on request.
`fairbeam_emerge.py` (like `fairbeam_elmer.py`) is a standalone adapter that discovers that
environment and launches `fairbeam_emerge_worker.py` **in a separate EMerge Python process**; only
the worker imports `emerge`. Results go through `research.py` (new `emerge` backend) into the
existing research job queue, history and Research dialog.

**Tech stack:** Fairbeam Python (CPython 3.13 runtime) + SolidJS/TS; EMerge 2.8.9 from PyPI in a
managed venv; `unittest` + `npm run check:*`.

**Scope level:** A (fixture MVP). Level B (bounded Design subset) gets its own plan in Task 9.

---

## Global Constraints

Copy this block verbatim into implementer and reviewer prompts.

- openEMS remains the default solver. No default, menu order or first-run flow changes in favor of EMerge.
- EMerge is opt-in experimental only. It is never bundled in the installer and never installed
  without an explicit user action (Install button, CLI call or a path the user enters).
- License posture: EMerge runs only as an external, optionally installed package in a **separate
  Python process**. No Fairbeam process imports `emerge`, `gmsh` or `emsutil`; only
  `python/fairbeam_emerge_worker.py` does, and it runs under the EMerge venv's interpreter. Do not
  copy EMerge source into this repository.
- Level A accepts **no user design**. Only the fixed fixture defined in "Shared facts" runs. Any
  other geometry, frequency list or resolution is rejected with a clear error, never coerced.
- Acceptance criteria and fixture constants in "Shared facts" are owned by the Planner. An
  implementer must not change them to make a run pass; report `BLOCKED` instead.
- Fairbeam result frames use the `exp(+i omega t)` phasor convention (as openEMS and the shared RF
  plots do). Any native EMerge convention difference is converted once, at the adapter boundary,
  and recorded in the result.
- UI strings need entries in both `src/i18n/en.json` and `src/i18n/tr.json`. Numbers in inputs and
  files use a decimal point. Product name is "Fairbeam".
- `npm run check:legal` must pass. No comparisons with proprietary solvers.
- Numbers in docs come only from artifacts of a reproducible run (Task 5). A model's statement is
  never evidence.
- Simulations: one at a time; coarse first.
- Branch `feat/emerge-experimental`. Commit with a `Co-Authored-By:` trailer naming the model, e.g.
  `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- Don't touch Elmer production files except the exact lines a task names (`research.py`,
  `server.py`, `ResearchDialog.tsx`, `api.ts`).

---

## Shared facts (verified 2026-11-04 by the Planner)

**EMerge package (from the 2.8.9 wheel metadata, inspected with pip):**

- PyPI `emerge` 2.8.9, pure-Python wheel `emerge-2.8.9-py3-none-any.whl`.
- `Requires-Python: >=3.10,<3.14`. Fairbeam's desktop runtime is CPython 3.13.15
  (python-build-standalone, see `scripts/licenses/inventory.json`), so the managed venv can be
  created from Fairbeam's own `sys.executable`.
- Heavy dependencies: `gmsh>=4.13,<4.15`, `numba>=0.60`, `mkl` (x86_64/AMD64), `numpy>=2.2,<2.5`,
  `scipy>=1.14`, `pyvista>=0.45.2` (pulls VTK), `matplotlib>=3.8`, `emsutil>=0.8.3,<0.9`,
  `joblib`, `loguru`, `msgpack`, `msgpack-numpy`, `psutil`. Optional GPU extras (`cudss`) are
  **not** installed.
- License: source headers say GPL-2.0 **or (at your option) any later version**; the wheel LICENSE
  preamble says Gmsh-derived parts are GPL-2.0+ with the Gmsh additional permission, and `lib.py`
  is CC0. Human decision (2026-11-04): use this GPL-2.0-or-later reading, recorded in
  `docs/agent/SCOPE.md`. New fork code stays GPL-3.0-or-later. The external-process posture above
  still applies.
- Public API used by the worker (names found in the wheel; Task 4 reads signatures):
  `emerge.Simulation`, `emerge.geo.Box` (`_emerge/geo/shapes.py:52`),
  `Simulation.commit_geometry`, `Simulation.generate_mesh`, `Simulation.set_resolution`,
  `sim.mw.set_frequency_range(fmin, fmax, Npoints)`, `sim.mw.run_sweep(...)`
  (`physics/microwave/microwave_3d.py:1284`), `RectangularWaveguide` port BC
  (`physics/microwave/bcs/port_bcs.py:862`), `PEC` BC, result `.S(i, j)`
  (`physics/microwave/microwave_data.py:1519`), `export_touchstone`.
- `import emerge` sets thread variables with `setdefault` (OMP 1, MKL 4, NUMBA 4) and logs through
  loguru. The worker environment sets all of them to `1` explicitly before import.

**Fixture: WR-90 straight air-filled rectangular waveguide, two waveguide ports**

| Quantity | Value |
| --- | --- |
| Broad wall `a` | 22.86 mm (x) |
| Narrow wall `b` | 10.16 mm (y) |
| Length `L` | 50.0 mm (z, ports on z = 0 and z = L faces) |
| Walls | PEC |
| Fill | vacuum/air, eps_r = 1, mu_r = 1, lossless |
| Frequencies | exactly 8.0, 9.0, 10.0, 11.0, 12.0 GHz |
| Ports | `RectangularWaveguide` TE10, port 1 at z = 0, port 2 at z = L |
| Resolutions | **frozen after Task 5:** `coarse` = 0.25, `fine` = 0.125, EMerge wavelength fractions at the top frequency (`Simulation.set_resolution`: lower is finer, default 0.33, warns above 0.334) |

Analytic reference (`exp(+i omega t)` convention, reference planes at the port faces):
`k0 = 2 pi f / c0`, `beta = sqrt(k0^2 - (pi / a)^2)`, `S21 = S12 = exp(-i beta L)`,
`S11 = S22 = 0`. TE10 cutoff `c0 / (2a)` = 6.557 GHz; next mode TE20 at 13.11 GHz, so the band is
single-mode. `c0 = 299792458 m/s`.

**Acceptance criteria** (frozen by the Planner after Task 5 from the recorded EMerge 2.8.9 runs;
never loosened by an implementer). The coarse run is the worst case. Each threshold leaves at
least 2.5× headroom over it, and is tight enough to catch a wrong port orientation, a phasor sign
error or a broken mesh:

- max over frequencies of `|S11|` ≤ 0.02 (coarse measured 0.0055)
- min over frequencies of `|S21|` ≥ 0.995 (coarse measured 0.99990)
- max over frequencies of wrapped `|arg(S21) − (−beta L)|` ≤ 2 degrees (coarse measured 0.79)
- passivity: `|S11|^2 + |S21|^2` ≤ 1.005 at every frequency (coarse measured 0.99992)
- all values finite; frequencies exactly the fixture list in order

Pass → `status: "results_validated"`; fail → `"validation_failed"` (raw output kept). Same status
vocabulary as the Elmer cavity benchmark. `precision_converged` is always `false`.

**Local test command (this Windows machine):** `fairbeam/__init__.py` imports CSXCAD, so point it
at the desktop runtime's openEMS DLLs:

```powershell
$env:PYTHONPATH = "python"
$env:OPENEMS_INSTALL_PATH = "C:\Users\ee\AppData\Local\org.fairbeam.desktop\runtime\openEMS"
.\.venv\Scripts\python.exe -m unittest discover -s python/tests -q
```

(33 Elmer tests passed with this setup on 2026-11-04.) Use `-p "test_emerge_*.py"` for one family.

---

## File map

| File | Responsibility |
| --- | --- |
| `python/fairbeam/emerge_lock/requirements.in` | Top-level pin: `emerge==2.8.9` |
| `python/fairbeam/emerge_lock/win_amd64-cp313.txt` | Hash-locked full dependency set for the managed venv |
| `python/fairbeam/emerge_runtime.py` | Managed venv: status, install (blocking), start_install (thread), home, python path |
| `python/fairbeam_emerge.py` | Standalone adapter (no `fairbeam` import): discover, capabilities, fixture constants, `assess`, `run_fixture`, CLI |
| `python/fairbeam_emerge_worker.py` | Runs **inside the EMerge venv**: reads `case.json`, builds the fixture with EMerge, writes `raw.json` |
| `python/fairbeam/research.py` | `emerge` backend in probe / prepare / execute / validate_result / completed_result |
| `python/fairbeam/server.py` | `/api/research/emerge/runtime`, `/api/research/emerge/install`, health flag |
| `python/pyproject.toml` | `py-modules`, `fairbeam-emerge` script, lock file as package data |
| `src/runner/api.ts` | `EmergeRuntime`, `emergeRuntime`, `emergeInstall`, `ResearchBackend` += `"emerge"` |
| `src/designer/ResearchDialog.tsx` | Backend option, runtime block, resolution select, results branch |
| `src/designer/EmergeFixtureResults.tsx` | Results table for the waveguide fixture |
| `src/i18n/en.json`, `src/i18n/tr.json` | `research.backend.emerge`, `research.emerge.*` |
| `scripts/check-research-ui.mjs` | Synthetic EMerge scenario |
| `python/tests/test_emerge_runtime.py` | Managed venv tests (no network) |
| `python/tests/test_emerge_fixture.py` | Adapter tests (no EMerge) |
| `python/tests/test_emerge_research.py` | Research/server integration tests (no EMerge) |
| `docs/EMERGE-EXPERIMENT.md` | Fixture, how to run, measured observations from Task 5 |
| `docs/EXPERIMENTAL-SOLVERS.md`, `docs/RESEARCH-SOLVERS.md`, `docs/README.md` | User docs and index |

---

## Task 1: Hash-locked dependency set

**Model tier:** mid (Claude Sonnet 5.5). Needs network.

**Files:** `python/fairbeam/emerge_lock/requirements.in`, `python/fairbeam/emerge_lock/win_amd64-cp313.txt`, `python/fairbeam/emerge_lock/README.md` (3–6 lines: how it was generated)

**Steps:**

- [x] Write `requirements.in` containing exactly `emerge==2.8.9`.
- [x] Generate the lock with `uv` (on PATH):
  `uv pip compile python/fairbeam/emerge_lock/requirements.in --generate-hashes --python-version 3.13 --python-platform x86_64-pc-windows-msvc --only-binary :all: --no-header -o python/fairbeam/emerge_lock/win_amd64-cp313.txt`
  No extras. If any package has no `cp313`/`py3` win_amd64 wheel, stop with `BLOCKED` and name it.
- [x] Verify in a throwaway folder outside the repo:
  `py -3.13 -m pip download --no-deps --require-hashes --only-binary=:all: -r python/fairbeam/emerge_lock/win_amd64-cp313.txt -d $env:TEMP\emerge-lock-check`
  Record the file count and total bytes (from `Get-ChildItem | Measure-Object Length -Sum`).
- [x] Add those two measured numbers and the command to the **Evidence log** at the bottom of this plan.
  Also list the license field of `gmsh`, `mkl` and `emsutil` wheels (from their METADATA) there.
- [x] Delete the throwaway folder. Do not commit wheels.
- [x] Commit: `Add hash-locked EMerge 2.8.9 dependency set for the managed venv`

**Done when:** the lock installs-by-download with `--require-hashes` and the evidence log has the measured size.

---

## Task 2: `emerge_runtime.py` managed venv

**Model tier:** cheap (Composer 2.5 fast or Gemini 3.5 Flash). Mirror `python/fairbeam/elmer_runtime.py` and `python/tests/test_elmer_runtime.py` closely.

**Files:** `python/fairbeam/emerge_runtime.py`, `python/tests/test_emerge_runtime.py`

**Behavior:**

- `PIN = {"version": "2.8.9", "platform": "win32", "python": (3, 13), "lock": "win_amd64-cp313.txt", "lock_sha256": <sha256 of the committed lock file>, "source": "https://github.com/FennisRobert/EMerge", "license": "GPL-2.0-or-later (see the installed package's LICENSE)"}`.
- `home()` = `appstate.state_dir() / "emerge" / PIN["version"]`; `python()` = `home()/"Scripts"/"python.exe"`.
- `installed()` is true only if `python()` exists **and** `home()/"fairbeam-emerge.json"` exists with matching `version` and `lock_sha256`. The marker is written last.
- `status()` returns `supported, installed, path, version, license, source, state, error` and `estimated_bytes` (constant = the total measured in Task 1).
- `install()` (blocking):
  1. Refuse on unsupported platform (`OSError`, text like Elmer's: install EMerge yourself into a Python 3.10–3.13 environment and enter its folder).
  2. Refuse if `sys.version_info[:2] != PIN["python"]` (`OSError`, say which Python is required).
  3. Refuse if the shipped lock file's SHA-256 differs from `PIN["lock_sha256"]` (`ValueError`).
  4. If already installed: state `done`, return.
  5. If `home()` exists without a valid marker: remove it (partial earlier attempt).
  6. State `creating`: `subprocess.run([sys.executable, "-m", "venv", str(home())], check=True, ...)`.
  7. State `installing`: `[python(), "-I", "-m", "pip", "install", "--no-deps", "--require-hashes", "--only-binary=:all:", "--no-input", "--disable-pip-version-check", "-r", <lock path>]`, output to `home()/"install.log"`, timeout 1800 s.
  8. State `verifying`: read `home()/"Lib/site-packages"` for `emerge-2.8.9.dist-info/METADATA` (no execution of EMerge).
  9. Write the marker JSON, state `done`.
  On any exception: state `failed` with message, remove `home()` (keep nothing), re-raise.
  Create the venv **in place** (venvs are not relocatable), not in a staging folder.
- `start_install()` = same single-thread guard as Elmer (`creating`/`installing`/`verifying` count as busy).
- All subprocesses: `stdin=DEVNULL`, `creationflags=CREATE_NO_WINDOW` on Windows, env without `PYTHONPATH`/`PYTHONHOME`.

**Tests (no network, `mock.patch("subprocess.run")` with a fake that creates `Scripts/python.exe` and the dist-info):** happy path writes marker and `installed()` is true; pip failure leaves no `home()` and state `failed`; wrong Python minor refused; lock hash mismatch refused; other platform refused; second install is a no-op; folder without marker is not "installed" and is replaced; `start_install` while busy does not start a second thread; status shape keys.

**Steps:**

- [x] Implement module and tests.
- [x] Run: `-p "test_emerge_runtime.py"` (see Shared facts) → all pass. Run `-p "test_elmer_*.py"` → still pass.
- [x] Commit: `Add the managed EMerge virtual environment (opt-in, hash-locked)`

**Done when:** tests pass without network or EMerge.

---

## Task 3: Standalone adapter `fairbeam_emerge.py` (no worker yet)

**Model tier:** cheap. Mirror `python/fairbeam_elmer.py` structure (discover → capabilities → validate_case → inputs → assess → run → main). It must import nothing from `fairbeam`, `emerge`, `numpy`; stdlib only.

**Files:** `python/fairbeam_emerge.py`, `python/tests/test_emerge_fixture.py`

**Behavior:**

- Constants from Shared facts: `A_M = 0.02286`, `B_M = 0.01016`, `L_M = 0.05`, `FREQUENCIES_HZ = (8e9, 9e9, 10e9, 11e9, 12e9)`, `RESOLUTIONS = {"coarse": None, "fine": None}` (placeholders filled in Task 4), `SUPPORTED_EMERGE = ("2.8.9",)`, `CRITERIA = {...}` exactly the provisional criteria.
- `discover(root=None)`: `root` or env `FAIRBEAM_EMERGE_PYTHON`. Accept a venv folder (`Scripts/python.exe` or `bin/python`) or a python executable. No PATH lookup. Return `(python_path, site_packages)`; site-packages found via `Lib/site-packages` (Windows) or `lib/python3.*/site-packages`. Raise `FileNotFoundError` with a clear message otherwise.
- `emerge_version(site_packages)`: parse `emerge-*.dist-info/METADATA` `Version:`; `None` if absent. No execution.
- `capabilities(root=None)`: `{"backend": "emerge-experimental", "physics": ["wr90_waveguide_fixture"], "driven_ports": False, "design_translation": False, "probe_executes_solver": False, "probe_executes_interpreter": False, ...}` plus `available`, `python`, `emerge_version`, `version_supported`, `python_sha256`, or `available: False, reason`.
- `validate_case(resolution)`: only keys of `RESOLUTIONS`; reject placeholders still `None` with "fixture resolutions not yet frozen".
- `case(resolution)`: the JSON dict handed to the worker (geometry in metres, frequencies, port faces, resolution value, `phasor_convention_out: "exp(+i omega t)"`).
- `analytic(f)`: complex S21 per Shared facts.
- `assess(raw)`: validate `raw` shape (`frequency_hz` equals the fixture list; `s11_re/s11_im/s21_re/s21_im` lists of finite floats, same length; `phasor_convention` is `"exp(+i omega t)"` or `"exp(-i omega t)"`). Conjugate if native is `exp(-i omega t)`. Compute per-frequency `|S11|`, `|S21|`, phase error in degrees (wrapped to ±180), passivity sum; compare with `CRITERIA`. Return `{"schema": "fairbeam.emerge-fixture-result/1", "status": ..., "frequency_hz", "s11_re", "s11_im", "s21_re", "s21_im", "analytic_s21_re", "analytic_s21_im", "metrics": {...}, "criteria": CRITERIA, "phasor_convention": "exp(+i omega t)", "native_phasor_convention": ..., "precision_converged": False, "qualifies_driven_antenna": False, "limitations": [...]}`.
- `run_fixture(out, *, root=None, resolution="coarse", experimental=False)`: same discipline as `fairbeam_elmer.run_cavity` — explicit opt-in; fresh output dir (`exist_ok=False`); manifest `schema: "fairbeam-emerge-fixture-1"` saved at each status (`inputs_generated`, `solver_started`, `solver_returned`, then result status / `failed` / `interrupted`); copy `fairbeam_emerge_worker.py` into the case folder and record its SHA-256 plus `case.json` and `python_sha256`; launch `[python, "-I", "fairbeam_emerge_worker.py", "case.json"]` with `cwd=case`, env without `PYTHONPATH`/`PYTHONHOME`, and `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `NUMBA_NUM_THREADS` = `"1"`, `MPLBACKEND=Agg`, `PYVISTA_OFF_SCREEN=true`; `timeout=600`; write `worker.log` on success, failure and timeout; require exit 0 and `raw.json`; then `assess`, write `result.json`, raise `ValueError` if `validation_failed` (raw kept).
- `main()`: `capabilities` and `waveguide --experimental --out DIR --resolution coarse|fine`, `--root`, exit code 2 with `fairbeam-emerge: <msg>`.

**Tests (no EMerge):** discover with fake venv folder / missing python / env var; `emerge_version` parse; capabilities unavailable reason; `assess` passes on synthetic raw built from `analytic()`; fails on `|S11|`=0.3; fails on phase sign flip unless `native_phasor_convention` says `exp(-i omega t)` (then passes after conjugation); rejects non-finite, wrong frequency list, unequal lengths, unknown convention; `run_fixture` requires `experimental`, refuses an existing out dir, keeps `worker.log` and `failed` manifest on non-zero exit and on `TimeoutExpired` (mock `subprocess.run`); import isolation via `ast` scan: `fairbeam_emerge.py` imports no `fairbeam`, `emerge`, `numpy`, `gmsh`.

**Steps:**

- [x] Implement module and tests (temporarily set `RESOLUTIONS` in tests via `mock.patch.dict`).
- [x] Run `-p "test_emerge_*.py"` → pass.
- [x] Commit: `Add the standalone EMerge fixture adapter (solver-free)`

**Done when:** all adapter logic is tested without EMerge installed.

---

## Task 4: Worker `fairbeam_emerge_worker.py` (EMerge API)

**Model tier:** mid (Claude Sonnet 5.5). Requires reading EMerge 2.8.9 source; get it with
`py -3.13 -m pip download emerge==2.8.9 --no-deps -d $env:TEMP\emerge-src` and read inside the wheel (do not copy code into the repo).

**Files:** `python/fairbeam_emerge_worker.py`, `python/fairbeam_emerge.py` (only `RESOLUTIONS`), `python/tests/test_emerge_fixture.py` (isolation test for worker), this plan (Shared facts: resolutions, phasor note)

**Steps:**

- [x] Read signatures/docstrings of `Simulation.__init__`, `set_resolution`, `geo.Box`, `commit_geometry`, `generate_mesh`, `RectangularWaveguide`, `mw.set_frequency_range`, `mw.run_sweep`, the sweep result's `S(i, j)`, and where EMerge writes files (`simstate.py`). Determine EMerge's time-harmonic convention from source (search `exp(`, `1j*`, port mode definitions); cite file:line in the commit message body.
- [x] Write the worker: stdlib + `emerge` + `numpy` only; no `fairbeam` import; reads `case.json` (path from argv), builds the fixture exactly as given, sets model/output paths inside the cwd, sweeps the exact frequency list (if `set_frequency_range` cannot hit the exact five points, use the API that takes explicit frequencies; if none exists, `BLOCKED`), writes `raw.json` = `{"emerge_version", "frequency_hz", "s11_re", "s11_im", "s21_re", "s21_im", "phasor_convention": <native, from your source reading>, "mesh": {"nodes", "tetrahedra"} if available, "elapsed_seconds"}` with `allow_nan=False`. No plotting, no GUI calls.
- [x] Frequencies: `assess()` compares frequencies exactly. EMerge may compute its own grid (e.g. `linspace`), so verify each EMerge frequency is within 1e-9 relative of the case value, then write the **case values** into `raw.json`. Any larger mismatch → raise and let the worker fail.
- [x] Reference planes and port orientation: confirm from source that `RectangularWaveguide` S-parameters refer to the port faces (no de-embedding offset), and how the port-2 mode's field orientation is defined. Record both in the commit body. Never add a phase offset or sign flip to make the fixture match. If Task 5 shows a constant ~180° S21 error, that is `BLOCKED` for the Planner.
- [x] No extra processes: configure EMerge to solve in the worker process itself (no joblib/multiprocessing parallel sweep), because `run_fixture`'s timeout kills only the direct child. Cite the setting you used.
- [x] Choose two resolution values (`coarse`, `fine`) from the `set_resolution` docstring so that `fine` is about 2× finer. Put them into `RESOLUTIONS` and into this plan's Shared facts as **provisional**. Task 5 runs with them; the Planner freezes them after Task 5, together with the criteria.
- [x] Add an `ast` isolation test: worker imports no `fairbeam`.
- [x] Run `-p "test_emerge_*.py"` → pass (no native run in this task).
- [x] Commit: `Add the EMerge worker for the WR-90 fixture`

**Done when:** worker exists, resolutions proposed, convention documented with source citation.

---

## Task 5: First native run (human-authorized)

**Model tier:** mid. **Human gate:** ask before starting — downloads the measured size from Task 1 and runs EMerge locally. Run one simulation at a time.

**Steps:**

- [x] Install via the module (not by hand), from the repo venv:
  `.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'python'); from fairbeam import emerge_runtime as r; print(r.install())"` (with `OPENEMS_INSTALL_PATH` set as in Shared facts). Record elapsed time and final folder size.
- [x] `python/fairbeam_emerge.py capabilities` against the managed venv → paste JSON into the evidence log.
- [x] Run `waveguide --experimental --resolution coarse --out <fresh dir outside repo>`, then `fine`.
- [x] Copy into the evidence log, from `result.json`/`manifest.json` only: per-frequency `|S11|`, `|S21|`, phase error; elapsed seconds; mesh size; EMerge version; native convention; status.
- [x] If either run is `validation_failed` or errors: stop, `BLOCKED`, attach logs. Do not edit criteria.
- [x] Note first-run vs second-run time (numba JIT cache) if visible.
- [x] After each run, check Task Manager (or `Get-Process python`) for leftover processes started from the managed venv path; record the result.
- [x] Commit only the plan's evidence log update: `Record first native EMerge fixture runs`

**Done when:** evidence log holds both runs, and the human has confirmed or tightened the criteria (Planner updates Shared facts).

---

## Task 6: Research queue + run server wiring

**Model tier:** mid. Files named below only.

**Files:** `python/fairbeam/research.py`, `python/fairbeam/server.py`, `python/pyproject.toml`, the desktop packaging step that already copies `fairbeam_elmer.py` (find it with `rg -n "fairbeam_elmer" scripts src-tauri python/pyproject.toml`), `python/tests/test_emerge_research.py`

**Steps:**

- [x] `research.py`: `BACKENDS` += `"emerge"`; `backend_name` error text; `emerge_python(path)`: given path, else `FAIRBEAM_EMERGE_PYTHON`, else managed `emerge_runtime.home()` if installed, else path (no PATH lookup).
- [x] `probe`: `fairbeam_emerge.capabilities(emerge_python(path))`.
- [x] `prepare`: `design` must be `None` ("EMerge Level A runs only the fixed waveguide fixture"); settings exactly `{"resolution"}`; `validate_case`; refuse unsupported EMerge version; pins via `binary_pins((python,), extra=[worker script path, emerge dist-info RECORD])`; normalized `{"resolution": ...}`.
- [x] `execute`: `fairbeam_emerge.run_fixture(outdir, root=spec["path"], resolution=..., experimental=True)`.
- [x] `validate_result`: add an `emerge` branch **before** the final Elmer-cavity `else` (that `else` currently catches every other backend); check schema, five ordered frequencies, list lengths, finiteness, `precision_converged is False`, and that `status == "results_validated"` agrees with `metrics` vs `criteria` (same idea as the Elmer cavity contradiction check).
- [x] `completed_result`: `emerge` + fixture schema + `results_validated`.
- [x] `server.py`: `emerge_runtime_status` / `emerge_runtime_install` methods and routes `GET /api/research/emerge/runtime`, `POST /api/research/emerge/install` next to the Elmer ones; add `"emerge": 1` to the health dict (line ~697).
- [x] `pyproject.toml`: `py-modules` += `fairbeam_emerge`, `fairbeam_emerge_worker`; script `fairbeam-emerge = "fairbeam_emerge:main"`; lock files as package data. Mirror the desktop copy step for the two new modules.
- [x] Tests: prepare refuses design / extra settings / unknown resolution / unsupported version; probe with fake venv; validate_result accepts a synthetic validated result and rejects contradictions, wrong schema, wrong backend; health has `emerge`; Elmer research tests unchanged.
- [x] Run full Python suite (Shared facts command) → **DONE_WITH_CONCERNS** (scoped EMerge/Elmer/research/CLI families all OK; full discover not clean — see below).
- [x] Commit: `Wire the EMerge fixture into the research queue and run server` (`6e4d960`)

**Status:** `DONE_WITH_CONCERNS`

**Concern (Task 6, 2026-11-04):** The Done-when clause asks for a clean full suite. Scoped checks for this task all passed (`test_emerge_*.py` 74, `test_elmer_*.py` 33, `test_research_*.py` 27, `test_cli_entry_points.py` 3). Full `unittest discover -s python/tests -q` ran 3014 tests with **2 failures + 9 errors** that are **not caused by this wiring**: Windows symlink privilege `WinError 1314` (`test_static`, `test_jobs`, `test_simdata`); local untracked/committed-elsewhere `public/projects/hairpin-filter-*.json` with `microstrip` ports failing `test_bundles`; one `test_document_workspace` concurrent-publish flake. Reviewer: **APPROVE** Task 6 / Global Constraints; full-suite cleanliness is deferred for Planner/human (environment or local project files), not a Task 6 code fix.

**Done when:** `POST /api/research/runs` with `{"backend": "emerge", "settings": {"resolution": "coarse"}}` is admitted against a fake venv in tests, and the full suite passes.

---

## Task 7: Research dialog UI

**Model tier:** mid. Follow existing Elmer patterns in `ResearchDialog.tsx`; no refactor of the Elmer block.

**Files:** `src/runner/api.ts`, `src/designer/ResearchDialog.tsx`, `src/designer/EmergeFixtureResults.tsx`, `src/i18n/en.json`, `src/i18n/tr.json`, `scripts/check-research-ui.mjs`

**Steps:**

- [x] `api.ts`: `EmergeRuntime` type (status fields from Task 2), `emergeRuntime`, `emergeInstall`; `ResearchBackend` += `"emerge"`; `emerge?: number` in the health type.
- [x] `ResearchDialog.tsx`: `<option value="emerge">` only when health reports `emerge`; runtime block for EMerge (states creating/installing/verifying shown as indeterminate progress with the estimated size; license note shown **before** the Install button: EMerge GPL-2.0-or-later, plus Intel MKL and its runtime packages under Intel's own proprietary license, downloaded from PyPI); resolution select (`coarse`/`fine`); fixture only (no "current design" source); submit `{backend: "emerge", path, settings: {resolution}}`; result branch for schema `fairbeam.emerge-fixture-result/1` → `EmergeFixtureResults`.
- [x] `EmergeFixtureResults.tsx`: table per frequency (GHz, |S11| dB, |S21|, phase error °), criteria row, status block reusing existing QA classes, experimental note.
- [x] i18n: `research.backend.emerge`, `research.emerge.scope|setup|step1|step2|pathHint|resultNote|resolution|coarse|fine`, `research.emerge.runtime.*`; Turkish per `docs/i18n-glossary.md`. Write "Fairbeam" in Turkish suffix forms by hand.
- [x] `check-research-ui.mjs`: synthetic EMerge scenario (option visible only with health flag; install flow; validated result rendering) in both languages. Synthetic data must be labelled synthetic as the file already does.
- [x] Run: `npm run typecheck`, `npm run check:research`, `npm run check:i18n`, `npm run check:designer`, `npm run check:legal`.
- [x] Commit: `Add EMerge fixture to the Research dialog`

**Status:** `DONE_WITH_CONCERNS`

**Concern (Task 7, 2026-11-04):** `npm run check:designer` failed in `check-nav-tree` with `every committed bundle is an example: got 19, want 21` because of two local untracked `public/projects/hairpin-filter-*.json` files (same environment issue noted in Task 6). Task 7 UI checks that ran clean: `typecheck`, `check:i18n`, `check:legal`, `check:research` (EN/TR including health gate, install, synthetic validated results).

**Done when:** checks pass; option is hidden on servers without the health flag.

---

## Task 8: Documentation

**Model tier:** cheap. Numbers only from the Task 5 evidence log.

**Files:** `docs/EMERGE-EXPERIMENT.md`, `docs/EXPERIMENTAL-SOLVERS.md`, `docs/RESEARCH-SOLVERS.md`, `docs/README.md`

**Steps:**

- [x] `EMERGE-EXPERIMENT.md` mirroring `docs/ELMER-EXPERIMENT.md`: what it is, CLI and Research panel use, fixture and analytic reference, observed results table (from evidence log, with EMerge version, resolution, date), acceptance criteria, limits (no design translation, no antenna results, `precision_converged` false), license and distribution (external optional install from PyPI per the lock; nothing shipped; component licenses: EMerge and gmsh GPL-2.0-or-later, emsutil per the evidence log, Intel MKL group under the Intel Simplified Software License), tests command.
- [x] `EXPERIMENTAL-SOLVERS.md`: short EMerge section (setup, managed install size, other platforms: own Python 3.10–3.13 env with `emerge==2.8.9`, path field / `FAIRBEAM_EMERGE_PYTHON`).
- [x] `RESEARCH-SOLVERS.md` entry and `docs/README.md` index link.
- [x] Run: `npm run check:legal`, `npm run check:links`, `npm run check:site`.
- [x] Commit: `Document the experimental EMerge fixture`

**Status:** `DONE_WITH_CONCERNS`

**Concern (Task 8, 2026-11-04):** `npm run check:site` fails in this workspace when local untracked `public/projects/hairpin-filter-*.json` entries inflate `index.json` (home still says 19 examples). With `index.json` at HEAD, `check:site` passed. Same environment issue as Tasks 6–7. Task 8 docs checks that ran clean against that HEAD index: `check:legal`, `check:links` (after matching `docs/tr/EXPERIMENTAL-SOLVERS.md` heading depths), `check:site`.

**Done when:** docs pass checks and every number traces to the evidence log.

---

## Task 9: Whole-branch review + Level B plan

**Model tier:** Planner (Claude Opus 5.5).

**Steps:**

- [x] Review the branch against Global Constraints with `docs/agent/prompts/reviewer.md`; run the AGENTS.md pre-PR checks (`typecheck`, `check:designer`, `check:exports`, `check:legal`, Python suite, `check:scenarios -- --skip-run`).
- [x] Mark Level A done in this plan.
- [x] Write `docs/agent/plans/YYYY-MM-DD-emerge-level-b-design-subset.md`: axis-aligned dielectric boxes + PEC sheets + one discrete port, reusing the admission rules of `elmer_driven.py` (not its mesher; EMerge meshes with gmsh), S11 into a shared bundle like `elmer_bundle.py`, explicit rejects.

**Status:** `DONE`. **Level A is done.** Next plan: `2026-11-04-emerge-level-b-design-subset.md`.

**Review (Task 9, Claude Opus 5.5) of Tasks 6–8 (`6e4d960`, `690f046`, `f7ab5be`): APPROVE** after three fixes made in the Task 9 commit:

- Important (fixed): `EmergeFixtureResults.tsx` rendered the word "passivity" as hardcoded English in both languages. Now `research.emerge.passivity` in `en.json`/`tr.json`.
- Important (fixed): `docs/EMERGE-EXPERIMENT.md` Tests block carried a personal path (`C:\Users\ee\...`); now `$env:LOCALAPPDATA\...`.
- Minor (fixed): the same doc's PowerShell block used cmd syntax `%LOCALAPPDATA%`; now `$env:LOCALAPPDATA`.
- Minor (recorded, not changed): `validate_result` for `emerge` flags `results_validated` contradicting the metrics but not the reverse (`validation_failed` with passing metrics); same as the Elmer cavity check. The Turkish docs say "fikstür" while the UI says "test durumu"; the glossary has no entry for fixture.
- Global Constraints: no Fairbeam module imports `emerge`; openEMS stays default; the EMerge option is health-gated and after Elmer; license note precedes Install; Level A rejects a design, extra settings and unknown resolutions; Elmer production changes are limited to the named shared lines. Docs numbers match the Task 5 evidence log entries.
- Cancellation risk: research jobs start through `procutil.popen_group` (Windows job object) and cancel uses `kill_tree` (`taskkill /T /F`), so the EMerge worker grandchild is in the job's tree. Structural reading only; not exercised with a native run.
- The full-suite and `check:designer`/`check:site` concerns of Tasks 6–8 came from local untracked `public/projects/hairpin-filter-*.json` files and a modified `public/projects/index.json`: all of them pass in a clean worktree of `f7ab5be` (evidence log).

---

## Risks

- **Install size and time:** MKL, VTK, numba and gmsh are large; Task 1 measures it. The UI must show the size before the user clicks Install.
- **Python pin:** the managed venv requires Fairbeam's runtime to stay on CPython 3.13. A runtime upgrade to 3.14 breaks it (`Requires-Python <3.14`) until EMerge supports 3.14; `install()` refuses clearly.
- **Numba JIT cold start** may dominate the first run; the 600 s worker timeout may need Planner review after Task 5.
- **Cancellation:** the worker is a grandchild of the research job process. Task 5 should check that cancelling a queued EMerge run leaves no EMerge-venv `python.exe` alive; if it does, the fix is a Planner decision.
- **EMerge API churn:** pinned to 2.8.9; upgrading is a new Planner task (new lock, rerun Task 5).
- **License:** EMerge 2.8.9 is GPL-2.0-or-later (decided 2026-11-04, see SCOPE). A future pin must recheck its license; process isolation stays regardless.

---

## Evidence log

Fill only with commands run and outputs observed. Date every entry.

- 2026-11-04 (Planner): `pip index versions emerge` → latest 2.8.9. Wheel METADATA: `Requires-Python <3.14,>=3.10`; dependencies as listed in Shared facts. `emerge/__init__.py` header: GPL-2.0 or any later version.
- 2026-11-04 (Task 1, Claude Sonnet 5.5): `uv 0.9.13`, `uv pip compile python/fairbeam/emerge_lock/requirements.in --generate-hashes --python-version 3.13 --python-platform x86_64-pc-windows-msvc --only-binary :all: --no-header -o python/fairbeam/emerge_lock/win_amd64-cp313.txt` → exit 0; 52 pinned packages, every one resolved as a wheel (no `BLOCKED`).
- 2026-11-04 (Task 1): `py -3.13 -m pip download --no-deps --require-hashes --only-binary=:all: -r python/fairbeam/emerge_lock/win_amd64-cp313.txt -d $env:TEMP\emerge-lock-check` → exit 0, `Successfully downloaded` 52 packages. `Get-ChildItem ... | Measure-Object Length -Sum` → **Count 52, Sum 461988175 bytes (about 441 MiB)** of wheels. This is the download size only; the installed size is measured in Task 5. Throwaway folder deleted afterwards; no wheels committed.
- 2026-11-04 (Task 1): License fields from wheel METADATA: `gmsh-4.14.1` → `License: GPLv2+` (classifier GPLv2+). `mkl-2026.2.0` → `License: Intel Simplified Software License` (classifier `License :: Other/Proprietary License`, `LICENSE.txt` in wheel). `emsutil-0.8.3` → **no license field, no classifier and no LICENSE file in the wheel** (METADATA only has name, summary, URLs and requirements). Open for the human/Planner: `mkl` (and its `intel-openmp`, `onemkl-license` companions) is proprietary-but-redistributable-by-Intel and is only installed on user request from PyPI; `emsutil` licensing needs checking upstream before Task 8 states a license posture.
- 2026-11-04 (Planner review of Tasks 1–3): `-p "test_e*.py"` → `Ran 172 tests ... OK`. Accepted deviations: Task 2 keeps the pip log tail in the status error, and adds a 300 s venv timeout. Task 3's `CRITERIA` key names are accepted as the contract for Task 6.
- 2026-11-04 (Planner): emsutil upstream `https://github.com/FennisRobert/emsutil` (same author as EMerge). The GitHub license API returns `LICENSE` = "MIT License, Copyright (c) 2026 Robert Fennis" on `main`. In the 0.8.3 wheel, `emsutil/material.py` and `emsutil/pyvista/display.py` carry GNU license headers (Task 8 reads which version). Both MIT and GPL-2.0+ are GPL-3-compatible.
- 2026-11-04 (Planner): EMerge 2.8.9 `_emerge/solver.py:67-70` sets `_PARDISO_AVAILABLE = True` on any non-ARM CPU without loading MKL. `solve_interfaces/pardiso_interface.py:142` loads `mkl_rt` only when a `PardisoInterface` is created. `solver.py:2295-2311` picks SuperLU (SciPy) for matrices under 10,000 unknowns, and Pardiso first for larger ones in the default "SI" mode. MKL-related wheels in the lock: `mkl`, `intel-openmp`, `intel-cmplr-lib-ur`, `onemkl-license`, `tbb`, `tcmlib`, `umf`.
- 2026-11-04 (Human decision): keep Intel MKL in the managed environment, as EMerge ships it, for Pardiso speed on larger models. The Install UI and docs state its proprietary license before install. The lock stays unchanged.
- 2026-11-04 (Planner): `.venv` Python 3.13.16; Elmer tests `-p "test_elmer_*.py"` → `Ran 33 tests ... OK` with `OPENEMS_INSTALL_PATH` set to the desktop runtime openEMS folder.
- 2026-11-04 (Task 4, Claude Sonnet 5.5): source read from `pip download emerge==2.8.9 --no-deps` (wheel only, nothing copied). Paths below are inside `emerge/_emerge/`. **Native time-harmonic convention is `exp(+i omega t)`:** `physics/microwave/assembly/assembler.py:494` uses `er*(1 - 1j*tand) - 1j*cond/(W0*EPS0)` (loss is a negative imaginary part); `physics/microwave/bcs/port_bcs.py:1006` (`RectangularWaveguide.get_gamma`) is `1j*beta` and `physics/microwave/bcs/boundary_conditions.py:186` (absorbing boundary) is `1j*k0*neff`; `physics/microwave/adaptive_mesh.py:1067` uses the outgoing Green's function `exp(-1j*k0*R)`; `bc.py:264` periodic phase is `exp(-1j*k0*(u.d))`. The worker therefore reports `exp(+i omega t)` and `assess()` does no conjugation. **Reference planes:** `physics/microwave/microwave_3d.py:2251-2419` (`_post_process`) computes `S[i,j]` as a mode-projection ratio over the port-face triangles (`_compute_s_data` at :2490, `physics/microwave/sparam.py`), with no phase factor or offset, so S refers to the port faces. **Port-2 orientation:** `port_bcs.py:940` (`align_modes`) sets the mode polarization sign from `cs.yax . axis`; the local port axes come from a min-area-rectangle fit (`selection.py:121`) whose axis signs are not fixed, so the worker calls `port.align_modes(em.YAX)` on both ports (E along +y at both). That is EMerge's documented way to fix the positive E direction, not a trim; a constant ~180 degree S21 error in Task 5 is still `BLOCKED` for the Planner. **Single process:** `microwave_3d.py:1284` `run_sweep(parallel=False, multi_processing=False)` takes the in-process loop (`if not parallel:` at :1454); `ThreadPoolExecutor` and `mp.Pool` are only reached with `parallel=True`. **Exact frequencies:** `set_frequency_range` is `np.linspace` (:494); the worker uses `set_frequency(list)` (:473) with the five case values and checks the result axis (`data.scalar.axis("freq")`) within 1e-9 relative. **Other facts the worker relies on:** `set_resolution` is a wavelength fraction (`simmodel.py:796`, `microwave_3d.py:504`; default 0.33), and `set_frequency` scales the mesh size with the resolution current at that time (:485), so the resolution is set first. Face selections must be made after `commit_geometry()` (`selection.py:109`, `bc.py:71` reject earlier ones). `Box(width=x, depth=y, height=z)`, faces `bottom` = -Z and `top` = +Z (`geo/shapes.py:52`). `Simulation(save_file=False, write_log=False)` writes nothing; `settings.auto_save` is `False` (`settings.py:59`); the only network call in the package is the explicit `Simulation.ping` (`simmodel.py:350`). **S-parameter post-processing:** by default EMerge caps each `|S|` at 1 and power-normalizes columns (`settings.py:41-47`, applied in `microwave_3d.py:2391-2407`), which would hide a passivity violation, so the worker sets `mw_cap_sp_single`, `mw_cap_sp_col` and `mw_recip_sp` to `False` and records this in `raw.json` (`solver_setup`).
- 2026-11-04 (Task 4): resolutions chosen from the `set_resolution` docstring (`microwave_3d.py:504-522`, wavelength fraction, lower is finer, 0.33 default, >0.334 warns): `coarse` = 0.25, `fine` = 0.125 (exactly 2x finer). Provisional until the Planner freezes them after Task 5. At 12 GHz the wavelength is 25 mm, so the target element sizes are about 6.2 mm and 3.1 mm. This is arithmetic from the constants, not a mesh measurement.
- 2026-11-04 (Task 4): `-p "test_emerge_*.py"` → `Ran 66 tests ... OK` (EMerge not installed, nothing solved; the worker's EMerge calls are untested until Task 5).
- 2026-11-04 (Task 5, Composer): managed install via `.\.venv\Scripts\python.exe -c "… emerge_runtime.install()"` with `OPENEMS_INSTALL_PATH` set → status `done`, path `C:\Users\ee\AppData\Local\org.fairbeam.desktop\emerge\2.8.9`, version `2.8.9`. Wall time **74.7 s**. Installed folder `Get-ChildItem -LiteralPath …\emerge\2.8.9 -Recurse -File | Measure-Object Length -Sum` → **Count 13331, Sum 1567317171 bytes (1494.7 MiB)**. No leftover `python` processes from that path after install.
- 2026-11-04 (Task 5): `python\fairbeam_emerge.py --root …\emerge\2.8.9 capabilities` → JSON: `available: true`, `emerge_version: "2.8.9"`, `version_supported: true`, `python: …\Scripts\python.exe`, `python_sha256: "21bba195c88bcc007c8fd8e99603e9c0d82be1e08cff2f23bd5b2264f3148289"`, `physics: ["wr90_waveguide_fixture"]`, `driven_ports: false`, `design_translation: false`.
- 2026-11-04 (Task 5): coarse waveguide first attempt `--out C:\Users\ee\AppData\Local\Temp\fairbeam-emerge-coarse-20261104-123714` → exit 2, wall **10.2 s**, manifest `status: "failed"`, `worker_exit_code: 1`. Mesh completed (`#tets = 397`) then crash in EMerge numba first-compile notify: `emerge/_emerge/mth/_cache_check.py:40` `print(_COMPILE_MESSAGE)` → `UnicodeEncodeError: 'charmap' codec can't encode character '\u26a0'` under cp1252. No `raw.json` / `result.json`. After the run: no leftover emerge-venv `python` processes.
- 2026-11-04 (Task 5): confirmed `python -I` ignores `PYTHONUTF8`/`PYTHONIOENCODING` (utf8_mode 0, cp1252); `python -I -X utf8` sets utf8_mode 1. Second coarse attempt with those env vars set in the parent still failed the same way (out `…-123800`, wall 2.2 s) because `run_fixture` launches `[python, "-I", worker, …]` without `-X utf8`. **BLOCKED** (cleared below): native solve never started. Fix applied: `run_fixture` now launches `[python, "-I", "-X", "utf8", worker, …]`. Criteria unchanged. `-p "test_emerge_*.py"` → `Ran 66 tests ... OK`.
- 2026-11-04 (Task 5, after `-X utf8`): coarse `--out C:\Users\ee\AppData\Local\Temp\fairbeam-emerge-coarse-20261104-125136` → exit 0, wall **164.8 s**, `manifest.status` / `result.status` = `results_validated`, EMerge **2.8.9**, native convention `exp(+i omega t)`, mesh **163 nodes / 397 tets**, `result.elapsed_seconds` **160.945**, `manifest.worker_seconds` **164.738**. Metrics from `result.json`: GHz `[8,9,10,11,12]`; `|S11|` `[0.000151, 0.000533, 0.000629, 0.001578, 0.005462]`; `|S21|` `[0.999961, 0.999956, 0.999947, 0.999932, 0.999896]`; phase_error_deg `[0.120, 0.188, 0.308, 0.499, 0.789]`; aggregates `s11_max=0.005462`, `s21_min=0.999896`, `phase_error_deg_max=0.789`, `passivity_max=0.999922`. After run: no leftover emerge-venv `python` processes.
- 2026-11-04 (Task 5): fine `--out C:\Users\ee\AppData\Local\Temp\fairbeam-emerge-fine-20261104-125430` → exit 0, wall **11.2 s**, `results_validated`, EMerge **2.8.9**, native `exp(+i omega t)`, mesh **667 nodes / 2305 tets**, `result.elapsed_seconds` **9.223**, `manifest.worker_seconds` **11.122**. Metrics: `|S11|` `[2.74e-5, 4.11e-5, 5.02e-5, 9.06e-6, 1.19e-4]`; `|S21|` `[0.999996, 0.999996, 0.999995, 0.999994, 0.999993]`; phase_error_deg `[0.008, 0.011, 0.017, 0.025, 0.037]`; aggregates `s11_max=0.000119`, `s21_min=0.999993`, `phase_error_deg_max=0.037`, `passivity_max=0.999992`. First-run (coarse, cold numba) ~161 s solve vs second-run (fine, warm cache) ~9 s solve — JIT cache dominates. After fine: no leftover emerge-venv `python` processes. Human/Planner still needs to confirm or tighten provisional criteria before Task 6.
- 2026-11-04 (Planner review of Tasks 4–5): Recomputed `|S11|`, `|S21|` and phase error independently from both `raw.json` files against `exp(-i beta L)`; the values match the entries above. `arg(S21)` follows the dispersive reference across the band, from 84.8° at 8 GHz to 116.6° at 12 GHz after wrapping. Phase error falls from 0.789° to 0.037° at 12 GHz between coarse and fine. The worker reads S from `data.scalar.grid.S(i, j)`, with EMerge's capping, column normalization and reciprocity post-processing off. Accepted `f407f03` (`-X utf8`). Froze resolutions 0.25 / 0.125 and tightened the criteria to 0.02 / 0.995 / 2° / 1.005 in `fairbeam_emerge.CRITERIA` and Shared facts. `assess()` on both recorded `raw.json` files with the new criteria → `results_validated` for both. `-p "test_emerge_*.py"` → `Ran 66 tests ... OK`. Timeout note: the cold-numba coarse run took 161 s of the 600 s worker limit.
- 2026-11-04 (Task 6, Composer): Wired `emerge` into `research.py` / `server.py` / `pyproject.toml` / desktop copy (`tauri.conf.json`, `build-windows-preview.mjs`). Commit `6e4d960`. **Status `DONE_WITH_CONCERNS`.** Scoped: `-p "test_emerge_*.py"` → `Ran 74 tests ... OK`; `-p "test_elmer_*.py"` → `Ran 33 tests ... OK`; `-p "test_research_*.py"` → `Ran 27 tests ... OK`; `-p "test_cli_entry_points.py"` → `Ran 3 tests ... OK`. Full `unittest discover -s python/tests -q` → `Ran 3014 tests` with **2 failures + 9 errors unrelated to this task** (Windows symlink privilege WinError 1314 in `test_static`/`test_jobs`/`test_simdata`; local `public/projects/hairpin-filter-*.json` microstrip port schema in `test_bundles`; one `test_document_workspace` concurrent publish flake). Admission HTTP test posts `{"backend":"emerge","settings":{"resolution":"coarse"}}` against a fake venv with `autostart=False`. Reviewer APPROVE for Task 6; full-suite cleanliness left for Planner/human.
- 2026-11-04 (Task 7, Composer): Research dialog UI for EMerge fixture. `npm run typecheck` → OK. `npm run check:i18n` → `5465 keys, en and tr agree`. `npm run check:legal` → ok. `npm run check:research` → EN/TR passed (health gate hides option without `emerge`; install license-before-button; synthetic validated `fairbeam.emerge-fixture-result/1` table). `npm run check:designer` → failed only on pre-existing local hairpin project files in nav-tree (19 vs 21 examples); unrelated to Task 7.
- 2026-11-04 (Task 9, Claude Opus 5.5): clean `git worktree` of `f7ab5be` (no untracked projects; `node_modules` junctioned; `FAIRBEAM_PYTHON` = repo `.venv`). `npm run typecheck` → OK. `npm run check:legal` → ok. `npm run check:exports` → ok. `npm run check:designer` → exit 0. `npm run check:scenarios -- --skip-run` → `PASSED: 326 steps, 0 failing, 534 s`. `check:research` → EN/TR passed incl. EMerge. `check:i18n` → `5465 keys, en and tr agree`. `check:links` → `5706 relative links … OK`. `check:site` → passed. Python `unittest discover -s python/tests -q` → `Ran 3014 tests`, `FAILED (errors=9, skipped=41)`, 0 failures: 8 are `WinError 1314` symlink privilege (`test_static` ×6, `test_simdata`, `test_jobs.RawSimData`), 1 is `test_python_design.ConvertScript.test_a_slow_script_is_stopped`, which passes when run alone (timing under load). No EMerge, Elmer or research test failed.
- 2026-11-04 (Task 8, Composer): Documented EMerge fixture from Task 5 evidence only. `npm run check:legal` → ok. `npm run check:links` → `5706 relative links … OK` after aligning `docs/tr/EXPERIMENTAL-SOLVERS.md` heading depths. `npm run check:site` → passed with `public/projects/index.json` at HEAD; fails in this workspace when local hairpin entries inflate the index (pre-existing). emsutil 0.8.3 installed headers: `material.py` and `pyvista/display.py` GPL-2.0-or-later; wheel still has no LICENSE file (matches Task 1/Planner notes).
