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
| Resolutions | two fixed values `coarse` / `fine`, chosen in Task 4 from the `set_resolution` docstring and then frozen here by the Planner |

Analytic reference (`exp(+i omega t)` convention, reference planes at the port faces):
`k0 = 2 pi f / c0`, `beta = sqrt(k0^2 - (pi / a)^2)`, `S21 = S12 = exp(-i beta L)`,
`S11 = S22 = 0`. TE10 cutoff `c0 / (2a)` = 6.557 GHz; next mode TE20 at 13.11 GHz, so the band is
single-mode. `c0 = 299792458 m/s`.

**Provisional acceptance criteria** (Planner-set; Task 5 records measured values; the human
confirms or tightens them before Task 6; never loosened by an implementer):

- max over frequencies of `|S11|` ≤ 0.10
- min over frequencies of `|S21|` ≥ 0.95
- max over frequencies of wrapped `|arg(S21) − (−beta L)|` ≤ 5 degrees
- passivity: `|S11|^2 + |S21|^2` ≤ 1.02 at every frequency
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

- [ ] Write `requirements.in` containing exactly `emerge==2.8.9`.
- [ ] Generate the lock with `uv` (on PATH):
  `uv pip compile python/fairbeam/emerge_lock/requirements.in --generate-hashes --python-version 3.13 --python-platform x86_64-pc-windows-msvc --only-binary :all: --no-header -o python/fairbeam/emerge_lock/win_amd64-cp313.txt`
  No extras. If any package has no `cp313`/`py3` win_amd64 wheel, stop with `BLOCKED` and name it.
- [ ] Verify in a throwaway folder outside the repo:
  `py -3.13 -m pip download --no-deps --require-hashes --only-binary=:all: -r python/fairbeam/emerge_lock/win_amd64-cp313.txt -d $env:TEMP\emerge-lock-check`
  Record the file count and total bytes (from `Get-ChildItem | Measure-Object Length -Sum`).
- [ ] Add those two measured numbers and the command to the **Evidence log** at the bottom of this plan.
  Also list the license field of `gmsh`, `mkl` and `emsutil` wheels (from their METADATA) there.
- [ ] Delete the throwaway folder. Do not commit wheels.
- [ ] Commit: `Add hash-locked EMerge 2.8.9 dependency set for the managed venv`

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

- [ ] Implement module and tests.
- [ ] Run: `-p "test_emerge_runtime.py"` (see Shared facts) → all pass. Run `-p "test_elmer_*.py"` → still pass.
- [ ] Commit: `Add the managed EMerge virtual environment (opt-in, hash-locked)`

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

- [ ] Implement module and tests (temporarily set `RESOLUTIONS` in tests via `mock.patch.dict`).
- [ ] Run `-p "test_emerge_*.py"` → pass.
- [ ] Commit: `Add the standalone EMerge fixture adapter (solver-free)`

**Done when:** all adapter logic is tested without EMerge installed.

---

## Task 4: Worker `fairbeam_emerge_worker.py` (EMerge API)

**Model tier:** mid (Claude Sonnet 5.5). Requires reading EMerge 2.8.9 source; get it with
`py -3.13 -m pip download emerge==2.8.9 --no-deps -d $env:TEMP\emerge-src` and read inside the wheel (do not copy code into the repo).

**Files:** `python/fairbeam_emerge_worker.py`, `python/fairbeam_emerge.py` (only `RESOLUTIONS`), `python/tests/test_emerge_fixture.py` (isolation test for worker), this plan (Shared facts: resolutions, phasor note)

**Steps:**

- [ ] Read signatures/docstrings of `Simulation.__init__`, `set_resolution`, `geo.Box`, `commit_geometry`, `generate_mesh`, `RectangularWaveguide`, `mw.set_frequency_range`, `mw.run_sweep`, the sweep result's `S(i, j)`, and where EMerge writes files (`simstate.py`). Determine EMerge's time-harmonic convention from source (search `exp(`, `1j*`, port mode definitions); cite file:line in the commit message body.
- [ ] Write the worker: stdlib + `emerge` + `numpy` only; no `fairbeam` import; reads `case.json` (path from argv), builds the fixture exactly as given, sets model/output paths inside the cwd, sweeps the exact frequency list (if `set_frequency_range` cannot hit the exact five points, use the API that takes explicit frequencies; if none exists, `BLOCKED`), writes `raw.json` = `{"emerge_version", "frequency_hz", "s11_re", "s11_im", "s21_re", "s21_im", "phasor_convention": <native, from your source reading>, "mesh": {"nodes", "tetrahedra"} if available, "elapsed_seconds"}` with `allow_nan=False`. No plotting, no GUI calls.
- [ ] Choose two resolution values (`coarse`, `fine`) from the `set_resolution` docstring so that `fine` is about 2× finer. Put them into `RESOLUTIONS` and propose them in this plan's Shared facts (Planner freezes them at review).
- [ ] Add an `ast` isolation test: worker imports no `fairbeam`.
- [ ] Run `-p "test_emerge_*.py"` → pass (no native run in this task).
- [ ] Commit: `Add the EMerge worker for the WR-90 fixture`

**Done when:** worker exists, resolutions proposed, convention documented with source citation.

---

## Task 5: First native run (human-authorized)

**Model tier:** mid. **Human gate:** ask before starting — downloads the measured size from Task 1 and runs EMerge locally. Run one simulation at a time.

**Steps:**

- [ ] Install via the module (not by hand), from the repo venv:
  `.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'python'); from fairbeam import emerge_runtime as r; print(r.install())"` (with `OPENEMS_INSTALL_PATH` set as in Shared facts). Record elapsed time and final folder size.
- [ ] `python/fairbeam_emerge.py capabilities` against the managed venv → paste JSON into the evidence log.
- [ ] Run `waveguide --experimental --resolution coarse --out <fresh dir outside repo>`, then `fine`.
- [ ] Copy into the evidence log, from `result.json`/`manifest.json` only: per-frequency `|S11|`, `|S21|`, phase error; elapsed seconds; mesh size; EMerge version; native convention; status.
- [ ] If either run is `validation_failed` or errors: stop, `BLOCKED`, attach logs. Do not edit criteria.
- [ ] Note first-run vs second-run time (numba JIT cache) if visible.
- [ ] Commit only the plan's evidence log update: `Record first native EMerge fixture runs`

**Done when:** evidence log holds both runs, and the human has confirmed or tightened the criteria (Planner updates Shared facts).

---

## Task 6: Research queue + run server wiring

**Model tier:** mid. Files named below only.

**Files:** `python/fairbeam/research.py`, `python/fairbeam/server.py`, `python/pyproject.toml`, the desktop packaging step that already copies `fairbeam_elmer.py` (find it with `rg -n "fairbeam_elmer" scripts src-tauri python/pyproject.toml`), `python/tests/test_emerge_research.py`

**Steps:**

- [ ] `research.py`: `BACKENDS` += `"emerge"`; `backend_name` error text; `emerge_python(path)`: given path, else `FAIRBEAM_EMERGE_PYTHON`, else managed `emerge_runtime.home()` if installed, else path (no PATH lookup).
- [ ] `probe`: `fairbeam_emerge.capabilities(emerge_python(path))`.
- [ ] `prepare`: `design` must be `None` ("EMerge Level A runs only the fixed waveguide fixture"); settings exactly `{"resolution"}`; `validate_case`; refuse unsupported EMerge version; pins via `binary_pins((python,), extra=[worker script path, emerge dist-info RECORD])`; normalized `{"resolution": ...}`.
- [ ] `execute`: `fairbeam_emerge.run_fixture(outdir, root=spec["path"], resolution=..., experimental=True)`.
- [ ] `validate_result`: add an `emerge` branch **before** the final Elmer-cavity `else` (that `else` currently catches every other backend); check schema, five ordered frequencies, list lengths, finiteness, `precision_converged is False`, and that `status == "results_validated"` agrees with `metrics` vs `criteria` (same idea as the Elmer cavity contradiction check).
- [ ] `completed_result`: `emerge` + fixture schema + `results_validated`.
- [ ] `server.py`: `emerge_runtime_status` / `emerge_runtime_install` methods and routes `GET /api/research/emerge/runtime`, `POST /api/research/emerge/install` next to the Elmer ones; add `"emerge": 1` to the health dict (line ~697).
- [ ] `pyproject.toml`: `py-modules` += `fairbeam_emerge`, `fairbeam_emerge_worker`; script `fairbeam-emerge = "fairbeam_emerge:main"`; lock files as package data. Mirror the desktop copy step for the two new modules.
- [ ] Tests: prepare refuses design / extra settings / unknown resolution / unsupported version; probe with fake venv; validate_result accepts a synthetic validated result and rejects contradictions, wrong schema, wrong backend; health has `emerge`; Elmer research tests unchanged.
- [ ] Run full Python suite (Shared facts command) → pass.
- [ ] Commit: `Wire the EMerge fixture into the research queue and run server`

**Done when:** `POST /api/research/runs` with `{"backend": "emerge", "settings": {"resolution": "coarse"}}` is admitted against a fake venv in tests, and the full suite passes.

---

## Task 7: Research dialog UI

**Model tier:** mid. Follow existing Elmer patterns in `ResearchDialog.tsx`; no refactor of the Elmer block.

**Files:** `src/runner/api.ts`, `src/designer/ResearchDialog.tsx`, `src/designer/EmergeFixtureResults.tsx`, `src/i18n/en.json`, `src/i18n/tr.json`, `scripts/check-research-ui.mjs`

**Steps:**

- [ ] `api.ts`: `EmergeRuntime` type (status fields from Task 2), `emergeRuntime`, `emergeInstall`; `ResearchBackend` += `"emerge"`; `emerge?: number` in the health type.
- [ ] `ResearchDialog.tsx`: `<option value="emerge">` only when health reports `emerge`; runtime block for EMerge (states creating/installing/verifying shown as indeterminate progress with the estimated size; license note); resolution select (`coarse`/`fine`); fixture only (no "current design" source); submit `{backend: "emerge", path, settings: {resolution}}`; result branch for schema `fairbeam.emerge-fixture-result/1` → `EmergeFixtureResults`.
- [ ] `EmergeFixtureResults.tsx`: table per frequency (GHz, |S11| dB, |S21|, phase error °), criteria row, status block reusing existing QA classes, experimental note.
- [ ] i18n: `research.backend.emerge`, `research.emerge.scope|setup|step1|step2|pathHint|resultNote|resolution|coarse|fine`, `research.emerge.runtime.*`; Turkish per `docs/i18n-glossary.md`. Write "Fairbeam" in Turkish suffix forms by hand.
- [ ] `check-research-ui.mjs`: synthetic EMerge scenario (option visible only with health flag; install flow; validated result rendering) in both languages. Synthetic data must be labelled synthetic as the file already does.
- [ ] Run: `npm run typecheck`, `npm run check:research`, `npm run check:i18n`, `npm run check:designer`, `npm run check:legal`.
- [ ] Commit: `Add EMerge fixture to the Research dialog`

**Done when:** checks pass; option is hidden on servers without the health flag.

---

## Task 8: Documentation

**Model tier:** cheap. Numbers only from the Task 5 evidence log.

**Files:** `docs/EMERGE-EXPERIMENT.md`, `docs/EXPERIMENTAL-SOLVERS.md`, `docs/RESEARCH-SOLVERS.md`, `docs/README.md`

**Steps:**

- [ ] `EMERGE-EXPERIMENT.md` mirroring `docs/ELMER-EXPERIMENT.md`: what it is, CLI and Research panel use, fixture and analytic reference, observed results table (from evidence log, with EMerge version, resolution, date), acceptance criteria, limits (no design translation, no antenna results, `precision_converged` false), license and distribution (external optional install from PyPI per the lock; nothing shipped), tests command.
- [ ] `EXPERIMENTAL-SOLVERS.md`: short EMerge section (setup, managed install size, other platforms: own Python 3.10–3.13 env with `emerge==2.8.9`, path field / `FAIRBEAM_EMERGE_PYTHON`).
- [ ] `RESEARCH-SOLVERS.md` entry and `docs/README.md` index link.
- [ ] Run: `npm run check:legal`, `npm run check:links`, `npm run check:site`.
- [ ] Commit: `Document the experimental EMerge fixture`

**Done when:** docs pass checks and every number traces to the evidence log.

---

## Task 9: Whole-branch review + Level B plan

**Model tier:** Planner (Claude Opus 5.5).

**Steps:**

- [ ] Review the branch against Global Constraints with `docs/agent/prompts/reviewer.md`; run the AGENTS.md pre-PR checks (`typecheck`, `check:designer`, `check:exports`, `check:legal`, Python suite, `check:scenarios -- --skip-run`).
- [ ] Mark Level A done in this plan.
- [ ] Write `docs/agent/plans/YYYY-MM-DD-emerge-level-b-design-subset.md`: axis-aligned dielectric boxes + PEC sheets + one discrete port, reusing the admission rules of `elmer_driven.py` (not its mesher; EMerge meshes with gmsh), S11 into a shared bundle like `elmer_bundle.py`, explicit rejects.

**Done when:** review findings are resolved or recorded, and the Level B plan exists.

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
- 2026-11-04 (Planner): `.venv` Python 3.13.16; Elmer tests `-p "test_elmer_*.py"` → `Ran 33 tests ... OK` with `OPENEMS_INSTALL_PATH` set to the desktop runtime openEMS folder.
