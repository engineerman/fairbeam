# Design: openEMS ↔ EMerge port mapping (adapter capability matrix)

**Date:** 2026-11-05  
**Branch:** `feat/emerge-experimental`  
**Status:** approved 2026-11-06 (human: design item 1; open points → recommended defaults)  
**Related:** [SCOPE.md](../SCOPE.md), [EMERGE-EXPERIMENT.md](../../EMERGE-EXPERIMENT.md), open cards in [BACKLOG-emerge-port-map.md](../BACKLOG-emerge-port-map.md)

## Goal

Let a Fairbeam Design that already runs on **openEMS** also run on **experimental EMerge** when the port (and geometry) subset is admitted — without requiring S-parameter agreement between solvers.

Success means: clear map or clear reject; approximate maps only behind explicit `accept_*` flags; provenance records what was mapped.

## Non-goals

- Changing the Design JSON port schema into a neutral “port intent” layer (deferred).
- Claiming cross-solver numerical equivalence or `results_validated` for mapped ports.
- Rewriting the openEMS build path.
- Changing Elmer experimental admission (reference only; same pattern may be copied later).
- Supporting Floquet / `UserDefinedPort` in the Design UI.
- Silent fallback (e.g. modal failure → lumped without telling the user).

## Decisions (locked in discussion)

| Topic | Choice |
| --- | --- |
| Primary aim | **A — runnability** with approximate mapping + accept/reject gates |
| Where mapping lives | **Adapter-side**; Design schema stays openEMS-shaped |
| Scope | **Plan all** port kinds; **implement staged** A → B → C |
| Approach | **Capability matrix** + existing `admit` gates (not a shared runtime translator, not per-solver port copies in Design) |

## Related practice (post-decision check)

After the decisions above were locked, we checked how some commercial multi-solver HF tools handle ports when switching time-domain and frequency-domain solvers. Typical pattern: **one shared port inventory** on the model; switching solvers does not require duplicate port definitions; unsupported port forms may be **automatically remapped** (for example a face-like discrete feed becoming an edge-like feed under certain mesh/solver combinations); mode calculation may still differ by solver even when the geometric port is unchanged.

Fairbeam’s adapter-side capability matrix is the internal analogue for experimental backends: one Design port list, map or reject at admit. Differences kept on purpose: **no silent remaps** (explicit `accept_*` + clear reject), provenance of approximations, and **no claim** of numerical or product parity with any commercial suite. Fairbeam continues to name CST only for **CST-compatible VBA macro** file import/export.

This section does not change the locked decisions; it only records that the pattern was checked and is compatible with the adapter-map choice already chosen for Elmer/EMerge.

## Background: port inventories

### Fairbeam Design / openEMS (authoring model)

| Design `ports[].type` | openEMS role |
| --- | --- |
| `lumped` (Discrete) | Lumped / discrete feed across a gap |
| `waveguide` | Rectangular waveguide mode port (TEₘₙ) |
| `microstrip` | Planar microstrip port (feed / measurement shifts) |
| `cpw` | Planar CPW port |
| `coaxial` | Coaxial TEM port |
| grouped lumped members | Parallel / series discrete group |
| Add lumped element… | Lumped R (not a driven S-port) |

### EMerge native BCs (`mw.bc`, emerge 3.0.0b12)

| BC | Role |
| --- | --- |
| `LumpedPort` | Uniform-E lumped / TEM terminal (`width`, `height`, `direction`, `Z0`) |
| `RectangularWaveguide` | Analytic rect WG TE/TM |
| `CoaxPort` | Analytic coax TEM |
| `ModalPort` | Eigenmode port face |
| `WavePort` | Dense wave port (incl. quasi-TEM / hybrid); preferred over deprecated `WavePortIH` |
| `FloquetPort` | Periodic cell |
| `UserDefinedPort` | User field callables |

### Elmer experimental (reference)

| Design | Elmer today |
| --- | --- |
| Single `lumped` | Finite-width FEM terminal (`accept_finite_feed`) |
| All other port types | Reject |

### Who can run what today

| Port class | openEMS | EMerge (Fairbeam) | Elmer exp. |
| --- | --- | --- | --- |
| Discrete / lumped | yes | Level B → `LumpedPort` | yes (single) |
| Rectangular WG | yes | Level A fixture only (not general Design admit) | no |
| Microstrip | yes (modal-ish FDTD) | B2 → `LumpedPort` + `accept_lumped_terminals`, or Stage C → `WavePort` + `accept_modal_ports` (modal wins if both) | no |
| CPW | yes | Stage C classic CPW → `WavePort` + `accept_modal_ports` (or lumped gap plate + `accept_lumped_terminals`; modal wins if both; GCPW rejected) | no |
| Coax | yes | Stage B → `CoaxPort` + `accept_coaxial_tem` | no |

## Mapping matrix (EMerge)

Approximate maps require the listed accept flags. Missing flag → reject with a clear `ValueError` (or UI-blocking error). Nothing is dropped silently.

| Stage | Design port | EMerge BC | Required accept / conditions | Reject |
| --- | --- | --- | --- | --- |
| **A** | `lumped` | `LumpedPort` | Gap → rectangular plate; `width` / `height` / `direction` / `Z0` from `R` (and existing Level B feed rules / `accept_finite_feed` where that path already uses it) | Volume ports, groups, floating ends (existing Level B rules) |
| **A** | `waveguide` | `RectangularWaveguide` | TEₘₙ; `a`/`b` match aperture; single-mode intent for first Design admit | First-pass: TM optional reject; curved WG; aperture mismatch |
| **A** | `microstrip` | `LumpedPort` strip-to-ground | **`accept_lumped_terminals`**; feed/measurement shifts unused | Flag false; wrong port count / geometry for the active path (B2: exactly two, etc.) |
| **B** | `coaxial` | `CoaxPort` | Axis / CS + `r_i` / `r_o`; constant εr fill | Dispersive fill; invalid radius order |
| **C** | `microstrip` | `WavePort` (prefer; do not ship `ModalPort` without trial + human go-ahead) | **`accept_modal_ports`** (separate from lumped); default remains lumped map when only lumped accept is set | Modal setup failure → hard error; **no** silent fall back to lumped |
| **C** | `cpw` (classic) | `WavePort` (prefer) or coplanar gap `LumpedPort` | **`accept_modal_ports`** and/or **`accept_lumped_terminals`** (modal wins if both); coplanar top grounds only | GCPW / bottom ground; mixed port types; WavePort setup failure → hard error (no silent lumped fall back) |
| — | port groups | — | — | reject |
| — | lumped element R | — | — | reject |
| — | Floquet / UserDefined | — | not in Design | no UI |

**Conflict rule (stage C):** if both `accept_lumped_terminals` and `accept_modal_ports` are true for a planar port, **modal wins** (exactly one BC per port).

## Architecture

```
Design JSON (unchanged ports)
        │
        ▼
emerge_* .admit(design, settings)
        │  uses
        ▼
emerge_port_map.resolve(port, path, settings)
        │
        ├─ ok → case JSON includes mapped_bc + approximations + accept_used
        └─ !ok → ValueError (admit fails)
        │
        ▼
fairbeam_emerge_worker  (only place that imports emerge)
        │
        ▼
sim.mw.bc.<MappedBC>(...)
```

openEMS build does not call `emerge_port_map`.

### Modules

| Piece | Role |
| --- | --- |
| `python/fairbeam/emerge_port_map.py` (new) | Single source table: Design port type → `{stage, emerge_bc, required_accepts[], approximations[], reject_if}`. No `emerge` / `numpy` imports. |
| `emerge_design.admit` / `emerge_planar.admit` (+ later coax / waveguide Design paths) | Call `resolve`; write BC fields into the metre-based case. No duplicated mapping policy. |
| `fairbeam_emerge_worker.py` | Apply `mapped_bc` + geometry to native BCs; do not invent policy. |
| `python/tests/test_emerge_port_map.py` | Stage A/B/C outcomes per Design port type. |
| Docs | Keep `docs/EMERGE-EXPERIMENT.md` honest; this file is the design source of truth until a plan supersedes pieces of it. |

### `resolve` contract

```text
resolve(port, *, path, settings) ->
  {
    ok: bool,
    mapped_bc: str | None,          # e.g. "LumpedPort"
    accept_used: list[str],
    approximations: list[str],      # human-readable, frozen strings
    error: str | None,
  }
```

### Provenance

Every EMerge experimental result / manifest records at least:

- `design_port_type` (per port)
- `mapped_bc`
- `approximations[]`
- which `accept_*` flags were true

Completion status stays **`results_exported`** for Design/planar mapped runs (no cross-solver validation claim).

### UI

- Do not proliferate hardcoded accept checkboxes forever: required flags come from the matrix for the active EMerge path + port types present in the Design.
- Near term (stage A consolidation): keep existing `accept_finite_feed` / `accept_lumped_terminals`; the table names them as `required_accepts`.
- Stage B adds coax-specific disclosure when that path exists.
- Stage C adds `accept_modal_ports`.
- Checkbox copy states the approximation (e.g. microstrip → lumped strip-to-ground). Never promise matching openEMS S-parameters.

## Implementation stages

1. **Stage A — matrix + wire-up** — shipped (`emerge_port_map.resolve`, driven/planar admits, provenance).
2. **Stage B — coaxial** — shipped (`coaxial_tem` / `CoaxPort`, accept UI). Mesh quality follow-up is a backlog card, not this matrix.
3. **Stage C — modal planar (microstrip)** — shipped: optional `WavePort` behind `accept_modal_ports`; conflict rule (modal wins); hard fail on WavePort errors; Run UI + preview.
4. **Stage C follow-on — classic CPW** — shipped (O8→C2): homogeneous `cpw` → `WavePort` / coplanar lumped with the same accept pair; GCPW rejected; worker skips substrate-bottom PEC.

## Out of scope until explicitly reopened

- Neutral Design “port intent” schema (discussion option B).
- Shared `translate_port()` used by openEMS and EMerge.
- `ports[].emerge = {…}` side-car fields in Design.
- Grounded CPW (GCPW) / groups / lumped-R on EMerge.
- Elmer matrix implementation.
- Bundling EMerge; replacing openEMS as default.

## Open points (resolved 2026-11-06)

1. **Waveguide Design admit:** **(a)** Stage A is table-only + Level A fixture unchanged; bounded Design waveguide is a follow-on task (not this plan).
2. **TM waveguide modes:** **reject** on first Design admit when/if Design waveguide is added later; fixture stays TE₁₀ as today.
3. **Stage C BC choice:** **prefer `WavePort`**; document `ModalPort` only after a spike if WavePort cannot drive the admitted planar class — no production coercion. (Stage C plan owns the spike.)

## Review checklist (author)

- [x] No vague TBD left without an owner decision above  
- [x] Goal A / adapter mapping / staged A→B→C consistent throughout  
- [x] openEMS / Design schema explicitly untouched  
- [x] Accept flags and conflict rule explicit  
- [x] Implementation deferred to plans after human approval of this file  
- [x] Related-practice note recorded (multi-solver shared ports; no silent remap; no product parity; legal-safe CST wording)

## Approval

- **2026-11-06:** Human approved this design as written (reply “1”). Open points locked to recommended defaults (see above).
- Remaining work (Design waveguide, coax mesh quality, GCPW, housekeeping): [BACKLOG-emerge-port-map.md](../BACKLOG-emerge-port-map.md). Do not implement from chat alone.
