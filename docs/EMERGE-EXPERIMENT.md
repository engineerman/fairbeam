# Experimental external EMerge (waveguide fixture and Design subset)

Fairbeam includes a separate, opt-in `fairbeam-emerge` research command. It discovers an external
EMerge Python environment. Only a worker process started inside that environment imports EMerge;
the Fairbeam process does not import `emerge`, `gmsh` or `emsutil`. Normal Fairbeam projects,
runtime setup and the default openEMS simulation path are unchanged. No EMerge wheels are bundled
in the Fairbeam installer or installed without an explicit user action. The desktop bundle still
ships Fairbeam's standalone adapters `fairbeam_emerge.py` and `fairbeam_emerge_worker.py` and
copies them into the managed Python app directory on runtime install/update (same pattern as
`fairbeam_elmer.py`). If an installed app reports `No module named fairbeam_emerge`, update or
repair Fairbeam; reinstalling the EMerge environment alone does not repair the missing adapter.

**Level A** runs one fixed, lossless, air-filled WR-90 rectangular waveguide with two waveguide
ports (no user Design). **Level B3** is the Design Run path: one option
**EMerge FEM · Experimental** (`analysis: "emerge_nport"`, health `emerge` ≥ 3) admits **1…8**
ports of one type under today’s bounded geometry recipes — driven/lumped (Level B class),
planar microstrip/Discrete/classic CPW (Level B2 class), or all-coaxial TEM (port-map Stage B,
`geometry_kind: "coaxial_tem"`) — and exports a full experimental N×N S-matrix
(`fairbeam.emerge-result/2`). Geometry remains bounded (no multilayer, vias, curves, or silent
coercion). The `design` and `planar` CLI subcommands still target the driven/planar recipes.
Historical Level B / B2 sections below keep the earlier one-port / two-port measurements and
qualification notes. All Design paths are opt-in experimental; results are `results_exported`,
never `results_validated`.

## Port mapping (Stage A)

Experimental openEMS-shaped Design ports are mapped to EMerge boundary conditions in
`fairbeam.emerge_port_map` (`resolve`). Policy source:
[docs/agent/specs/2026-11-05-emerge-openems-port-mapping-design.md](agent/specs/2026-11-05-emerge-openems-port-mapping-design.md).
Stage A consolidates Level B lumped → `LumpedPort`, Level B2 microstrip → lumped
strip-to-ground `LumpedPort` (default planar accept), and Level A fixture `RectangularWaveguide`
maps into that matrix without Design waveguide admit. Admission still rejects unsupported
types; approximate maps keep the existing `accept_*` gates. Provenance
(`design_port_type`, `mapped_bc`, `approximations`, `accept_used`) is recorded on the case and on
experimental results / bundles. On the planar path, homogeneous Discrete/`lumped` ports also map to
`LumpedPort` behind `accept_finite_feed` (same board-edge plate geometry as microstrip terminals;
all ports must share one type—mixed Discrete and microstrip is rejected). The unified Run dialog
preview and accept checkboxes follow the classified path and draft port types. Stage B coax and
Stage C optional microstrip / classic-CPW `WavePort` are documented below. Deferred follow-ons
(Design waveguide, grounded CPW, richer geometry):
[docs/agent/BACKLOG-emerge-port-map.md](agent/BACKLOG-emerge-port-map.md).
Level B3 superseded the backlog item that auto-suggested antenna vs planar Run options.

## Port mapping (Stage B — coaxial → CoaxPort)

When every Design port is `coaxial`, the unified Run classifier admits
`geometry_kind: "coaxial_tem"` (worker `kind: "coax"`). `emerge_port_map.resolve` on path
`"coax"` maps each port to analytic EMerge `CoaxPort` TEM only when
`accept_coaxial_tem: true`. The Run dialog shows that accept checkbox and a port-map preview
line (`Port N · coaxial → CoaxPort`).

**Limits (honest):**
- Axis-aligned centerline (`direction` x|y|z); `0 < r_i < r_o` with Design shield outer `r_os`
  as already checked for openEMS coax.
- Constant εr fill (air or nondispersive dielectric). Dispersive fill, invalid radii, missing
  accept, mixed port types, Design waveguide, TM/non-TEM coax modes, and port groups are
  rejected — never silently remapped.
- Geometry MVP synthesises inner PEC cylinder, outer shield tube, dielectric, and a padded
  domain from the ports; Design `parts` are not admitted on this path.
- Homogeneous **1…8** coaxial ports; full experimental N×N S via the same result schema
  (`fairbeam.emerge-result/2`). Status stays `results_exported` only.
- No openEMS S-parameter agreement claim; no invented native S-numbers in this section.

Coax mesh quality follow-up: [docs/agent/BACKLOG-emerge-port-map.md](agent/BACKLOG-emerge-port-map.md) (Finer coax mesh & excitation).

## Port mapping (Stage C — microstrip → WavePort)

When every Design port is `microstrip`, the planar path may map each port to EMerge `WavePort`
at the same board-edge plate used for lumped terminals, only when
`accept_modal_ports: true`. The Run dialog shows a separate modal accept checkbox beside the
existing lumped-terminal accept. At least one of the two accepts is required. If both are set,
**modal wins** (`mapped_bc: "WavePort"`, `accept_used: ["accept_modal_ports"]`). Preview lines
follow the same rule. WavePort setup failure is a hard error — there is no silent fall back to
`LumpedPort`. Prefer `WavePort`; do not ship `ModalPort` without a documented trial and human
go-ahead.

**Limits (honest):**
- Homogeneous all-`microstrip` ports. Classic CPW uses the same accept flags on a separate
  geometry class (below).
- Feed/measurement shifts remain unused (same plate class as the lumped map).
- Default accept path when only lumped is checked stays strip-to-ground `LumpedPort`.
- No openEMS S-parameter agreement claim; no invented Stage C S-numbers here.
- Measured 2026-11-06 on managed EMerge **3.0.0b12** (Windows Install EMerge): hairpin fixture
  admitted with `accept_modal_ports` only, `mesh_only`, shielded coarse, `approximate_metals`
  — worker attached `WavePort` to both terminal faces and exported
  `fairbeam.emerge-mesh-result/1` (**19435** nodes / **111428** tets, mesh wall **~3.0 s**).
  That run did not sweep S-parameters.

## Port mapping (Stage C — classic CPW → WavePort)

When every Design port is `cpw`, the planar path admits **classic CPW** only: one dielectric
substrate box, metal sheets on the substrate **top** (center strip plus ≥2 coplanar ground
sheets), and no substrate-bottom ground / PEC-z− sheet. Grounded CPW (bottom ground present) is
**rejected** with a clear error. Ports map to EMerge `WavePort` when `accept_modal_ports: true`,
or to a board-edge gap-style `LumpedPort` plate (`ground_mode: "coplanar"`) when only
`accept_lumped_terminals: true`. At least one accept is required; if both are set, **modal wins**.
The terminal face is the locked CPW aperture: board-edge plate, transverse span = center-strip
width widened by `2*gap` each side, vertical span = substrate thickness plus
`CPW_AIR_APERTURE_FRACTION` of `air_height_mm` above the metal plane (clamped to the air box;
currently **1.0**). Microstrip / Discrete terminals stay substrate-tall. WavePort setup failure
is a hard error — no silent fall back to `LumpedPort`. Classic CPW WavePorts call
`set_terminals(strip, ground)` so EMerge can compute PV Z0 when the face has more than two PEC
islands. The solver process does **not** attach PEC on the substrate bottom for classic CPW
(that would invent a backside ground). Prefer `WavePort`; do not ship `ModalPort` without a
documented trial and human go-ahead.

**Limits (honest):**
- Homogeneous all-`cpw` only; mixed microstrip/lumped/coax stays rejected.
- GCPW / bottom-ground CPW not admitted yet.
- Lumped CPW uses the same coplanar aperture plate (gap-style), not microstrip strip-to-ground;
  worker still drives `LumpedPort` with `direction=ZAX` (poor on coplanar — see measured note).
- Feed/measurement shifts unused; no openEMS S-parameter agreement claim.
- **O17 BLOCKED (2026-11-07):** air aperture + open enclosure + `set_terminals` do not yield a
  plausible broadband through-line on `portmap_cpw_line`. Human rejected WavePort S (band-low
  still highly reflective). ModalPort not started. Microstrip planar sanity (hairpin / portmap
  line) remains healthy on the same code — CPW-specific, not a general planar break.
- Measured 2026-11-07 on managed EMerge **3.0.0b12** (Windows Install EMerge), local
  `portmap_cpw_line`, shielded coarse unless noted:
  - Early admit (substrate-only face): `mesh_only` **5453** nodes / **27377** tets (~1.0 s);
    3-pt S exported (~8.1 s) before physics review.
  - After air aperture (full air column): human job `20261107-013032-d9b825` — \|S11\| min≈0.17
    @~3.09 GHz / max≈0.90; \|S21\| max≈0.93 @~3.09 GHz but **~0.43 (−7.4 dB) @1.2 GHz** (FAIL
    vs through-line expectation). Open pad-10 run similar shape, slightly better mid-band.
  - With `set_terminals`: PV Z0 ~70–74 Ω logged; S unchanged vs aperture-only.
  - Lumped-only accept: \|S21\| ≲ 0.003 (~−50…−64 dB) — worse than WavePort.
  - No openEMS S-agreement claim.

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

## Level B3: unified N-port Run (Design path)

In the app, open **Run**, choose **EMerge FEM · Experimental** (shown when health `emerge` ≥ 3),
set the band and resolution, accept the approximates required by the draft ports, and submit.
`backend` is `"emerge"` and `analysis` is `"emerge_nport"`. The server classifies the Design into
`geometry_kind` `driven_lumped`, `planar_microstrip`, `stripline`, or `coaxial_tem` (or rejects with the
failed class checks). Port count may be **1…8** (`N_MAX`); ports must be contiguous `1…N` and
all the same allowed type for that class. All-coaxial drafts also require `accept_coaxial_tem`
(see Stage B above). Shared Results get a complete N×N experimental `sparams` matrix
(`fairbeam.emerge-result/2`). openEMS remains available in the same dialog. The historical Level B
and B2 subsections below document the geometry recipes and recorded native numbers; they are not
separate Run brands anymore.

## Stripline sandwich

The experimental path also admits a stripline sandwich. The sandwich is one dielectric, with a ground on each face and the strip between those grounds. Lumped ports run from one ground to the strip. The air box uses the same z as the dielectric and adds padding in x and y. The lid and the floor are PEC. The four sides are a second-order ABC. Results stay `results_exported`.

## Level B: bounded Design subset (driven discrete port)

Admission mirrors Elmer's driven rules for the same geometry class: axis-aligned dielectric boxes
and metal sheets, **1…8** lumped (Discrete) ports numbered contiguously `1…N`, no resistors /
lumped elements / transforms / cuts / voids, no overlapping dielectrics. An ideal line feed is
widened only with explicit `accept_finite_feed` and `feed_width_mm`. Metal sheets with positive
`conductivity` use EMerge `ThinConductor` (σ and sheet `thickness`, default 0.035 mm); empty
conductivity stays PEC. Optional `approximate_metals` forces PEC for that run only. Nonzero
`tan_d` is admitted as EMerge's constant loss tangent (recorded as a limitation). Surface roughness
is not modelled. The air box is the parts+feed bounding box plus `padding_mm` on every side, with
second-order absorbing boundaries on all six faces (not PML). Unsupported geometry raises
`ValueError`; nothing is dropped silently.

Frozen settings (Task 5 / Task 6; B3 still uses them for the driven class): resolutions
`coarse` = 0.25 and `fine` = 0.15 (wavelength fraction at `f_max`); worker timeout 1800 s; refuse
before launch when the air-box volume proxy exceeds 200000. Sweep: `f_min_hz`…`f_max_hz`, 3–41
linspace points on the unified form (driven class historically used 3–21). Schema is
`fairbeam.emerge-result/2` with `geometry_kind: "driven_lumped"` only. Status
`results_exported`, `precision_converged: false`, `gain_qualified: false`, no far field.

```powershell
# after emerge_design.admit → case.json
python python/fairbeam_emerge.py --root $env:LOCALAPPDATA\org.fairbeam.desktop\emerge\3.0.0b12 design --experimental --case case.json --out E:/research/patch-coarse
```

Use **EMerge FEM · Experimental** (Level B3/B4). CLI `design` still accepts a driven-class
case.json.

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

## Level B2: planar microstrip (hairpin class)

Admission (`emerge_planar.admit`) accepts **1…8** ports numbered contiguously `1…N`, either all
`microstrip` (propagation in `x`/`y`, excitation `z`, real positive `reference_ohm`), all classic
`cpw` (coplanar top grounds; see Stage C CPW above), or all Discrete/`lumped`. Microstrip and
Discrete require one dielectric substrate box, ground as a metal z-flat box at the substrate
bottom or domain-floor PEC, and metal traces that are z-normal `polygon`s (or z-flat boxes) on the
substrate top. It rejects mixed port types, other port types, `N > 8`, resistors, lumped elements,
transforms, cuts, voids, multilayer/via geometry, grounded CPW, metal at other elevations, and
unknown settings. Trace metals with positive `conductivity` use EMerge `ThinConductor` (σ and sheet
thickness); empty conductivity stays PEC. Optional `approximate_metals` forces PEC traces for that
run. For microstrip/Discrete the substrate-bottom ground remains PEC; classic CPW skips that floor
PEC. Each microstrip port becomes a lumped strip-to-ground terminal at the board-edge face when
the user sets `accept_lumped_terminals: true`, or an EMerge `WavePort` on that same face when
`accept_modal_ports: true` (Stage C; modal wins if both accepts are set). Classic CPW uses the
same accept pair with a coplanar aperture plate. Each Discrete port uses the board-edge plate under
`accept_finite_feed: true`. `feed_shift`, `measurement_shift` and `termination` are unused for that
run. The saved Design and openEMS materials stay unchanged.

Frozen settings on the unified path: `analysis: "emerge_nport"` with
`geometry_kind: "planar_microstrip"`,
`enclosure: "shielded" | "open"`, `air_height_mm` (> 0 above the substrate top), `padding_mm`
(> 0, only with `open`), resolutions `coarse` = 0.25 and `fine` = 0.15, band 1 MHz–100 GHz with
3–41 linspace points, optional `approximate_metals`. Trace model: zero-thickness `XYPolygon`
sheets (`ThinConductor` or PEC); metal-edge mesh size 0.4 mm; `PORT_PAD_MM` = 1.0 beyond each
terminal face. Worker timeout 3600 s; refuse when the resource proxy exceeds 400000 tetrahedra.
Schema is `fairbeam.emerge-result/2` only. Status `results_exported`, `precision_converged: false`,
`gain_qualified: false`, empty far field. Shared Results get a complete N×N `sparams` matrix.

`shielded` leaves exterior faces to EMerge's default PEC box (closed cavity above the board).
`open` places second-order absorbing boundaries on the four sides and the top, with `padding_mm`
on those faces. The substrate bottom is always PEC.

```powershell
# after emerge_planar.admit → case.json
python python/fairbeam_emerge.py --root $env:LOCALAPPDATA\org.fairbeam.desktop\emerge\3.0.0b12 planar --experimental --case case.json --out E:/research/hairpin-coarse
```

Prefer the unified **EMerge FEM · Experimental** Run entry (Level B3); enclosure, air height and
padding appear when the Design classifies as planar. The older **EMerge FEM · Experimental planar
two-port** label is retired from the selector; CLI `planar` still accepts a planar case.json.
Recorded hairpin numbers below remain from the historical two-port runs.

### Hairpin class — recorded native observations (2026-11-04)

Test fixture `python/tests/fixtures/emerge_hairpin.design.json` (50.828 × 58 mm FR4-like
substrate 1.6 mm, εr 4.34, tanδ 0.0026 at 0.95 GHz, five copper polygons, two microstrip ports).
Managed EMerge **2.8.9** on Windows (recorded 2026-11-04, before the 3.0.0b12 pin), sheet copper
forced to PEC via `approximate_metals` (pre–ThinConductor path), `air_height_mm=6.4`, band
0.75–1.25 GHz × 15 points unless noted:

| Run | Enclosure / resolution | Nodes / tets | Solver elapsed | Best \|S21\| | S21 / S11 there |
|---|---|---|---|---|---|
| CLI planar | shielded coarse | 19147 / 109584 | 971.7 s | 1.071429 GHz | −0.63 dB / −30.45 dB |
| CLI planar | shielded fine | 19164 / 109714 | 1054 s | 1.071429 GHz | −0.63 dB / −31.27 dB |
| CLI planar | open coarse (`padding_mm=10`) | 19441 / 111586 | 1055 s | 1.071429 GHz | −0.51 dB / −34.20 dB |
| CLI / Run dialog | shielded coarse, short 5 pts 0.95–1.15 GHz | 19194 / 109920 | 320–338 s | 1.050 GHz | −0.82 dB / −19.55 dB |

All four EMerge runs reported `results_exported`. Full-band coarse→fine kept the same best-|S21|
frequency bin (1.071429 GHz) and the same −0.63 dB peak; mesh size was dominated by the metal-edge
setting (~110k tets). Open enclosure kept that peak frequency and lowered insertion loss slightly
(−0.51 dB). Reciprocity max |S21 − S12| stayed ≤ 4.2e−5; column power stayed ≤ 0.999.

Same fixture through Fairbeam's normal openEMS Run path (`fairbeam run --engine gpu --threads
auto`, design default mesh/band): `sparams.complete=false` (excited port 1 only; Design port 2 has
`excite: false`), best |S21| **1.025625 GHz** at **+5.07 dB** (non-physical; reported column power
max 3.40), S11 there **−7.27 dB**; Fairbeam band note min S11 **−13.4 dB** at **1.024 GHz**;
`mesh.total_cells=145152`, solver 107.4 s, converged.

### Hairpin qualification statement

Level B2 does **not** claim S-parameter agreement between EMerge planar and Fairbeam openEMS for
this fixture. The openEMS default path above is not a qualified two-port control (|S21| > 1,
incomplete matrix). Among EMerge planar runs alone: passband centre on the 15-point shielded
linspace is **1.071429 GHz**; coarse→fine peak shift is **0** on that grid; open vs shielded
peak-frequency shift is also **0**, with open ~0.12 dB lower insertion loss at the peak. Results
stay experimental exports (`results_exported` only). Port model (lumped strip-to-ground at the
board edge) and enclosure choice are expected to move magnitudes relative to a microstrip modal
port with feed/measurement planes.

## Field planes (multi-frequency post-sample)

After a successful EMerge Design solve, the worker samples E-field cutplanes with
`MWField.cutplane` (no second FEM). Default: one auto frequency (`max_abs_s21`, else
`min_abs_s11`, else band center). Optional Run setting `field_cut_frequencies_hz` (≤ **4**
positive Hz) snaps each request to the nearest solved sweep frequency, dedupes, and exports
ascending maps into `field_cuts` / shared Results `field_planes`. Empty list = auto one.
Play is phase animation on the selected harmonic map, not an FDTD time movie.

Measured 2026-11-07 on managed EMerge **3.0.0b12** (Windows), classic-CPW port-map line case
(shielded coarse, 1.2–3.6 GHz × 15 points, `accept_lumped_terminals`), CLI `planar
--experimental` after restarting `fairbeam serve`:

| Run | Requested Hz | `field_planes` | Worker wall |
| --- | --- | --- | --- |
| Auto (no list) | — | 1 @ 3.6 GHz (`max_abs_s21`) | **27.4 s** |
| User list | 2.4 / 3.5 / 3.0 GHz | 3 @ 2.4 / ≈2.914 / ≈3.429 GHz (`user`) | **27.2 s** |

Extra maps did not multiply solve time (same mesh+sweep class); cost is post-sample + larger
JSON. Evidence dirs: `.sim/o4-smoke/auto/run`, `.sim/o4-smoke/multi/run`.

## Results UI honesty (convergence)

EMerge exports always keep `precision_converged: false` (no mesh-convergence certificate). The
shared Results header does **not** reuse openEMS FDTD “Not converged” (timestep / field-energy
stop): a finished experimental export shows **Mesh not certified** instead. Run-quality
timestep-limit badges are skipped for EMerge bundles. Research still uses `emergeExp.qa`
(“Mesh, feed and boundary convergence have not been established for this run.”).

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
