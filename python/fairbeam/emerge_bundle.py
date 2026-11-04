"""Export an EMerge driven Design result into the shared designer Results format.

Geometry comes from the admitted design; no openEMS simulation is performed.
EMerge 2.8.9 is natively ``exp(+i omega t)``, matching Fairbeam frames, so S11 is
not conjugated. Far field is empty in Level B. Completion is never a validation claim.
"""
import copy

import numpy as np

from .emerge_design import admit


def result_bundle(design, result):
    from .preview import build_preview

    if result.get("schema") != "fairbeam.emerge-driven-result/1":
        raise ValueError("unsupported EMerge driven result schema")
    if result.get("status") != "results_exported":
        raise ValueError("EMerge Design result must be results_exported")
    if result.get("precision_converged") is not False:
        raise ValueError("EMerge Design never claims mesh convergence")
    if result.get("gain_qualified") is not False:
        raise ValueError("EMerge Design never claims qualified gain")
    settings = result["settings"]
    case = admit(design, settings)
    drawing = copy.deepcopy(design)
    if settings.get("approximate_metals"):
        for material in drawing["materials"]:
            if material.get("kind") == "metal":
                material.pop("conductivity", None)
                material.pop("thickness", None)
    bundle = build_preview(None, {}, design=drawing)["bundle"]
    bundle.pop("preview", None)
    bundle["name"] += " · EMerge FEM"
    air_lo = [float(v) * 1000 for v in case["air"]["lo"]]
    air_hi = [float(v) * 1000 for v in case["air"]["hi"]]
    axes = [np.array([air_lo[i], air_hi[i]]) for i in range(3)]
    steps = np.array([air_hi[i] - air_lo[i] for i in range(3)], dtype=float)
    mesh_counts = result.get("mesh") or {}
    tetrahedra = mesh_counts.get("tetrahedra", 0)
    bundle["mesh"] = dict(zip("xyz", [axis.tolist() for axis in axes]))
    bundle["mesh"].update(cells=[1, 1, 1], total_cells=int(tetrahedra) if tetrahedra else 1,
                          min_cell=float(steps.min()), max_cell=float(steps.max()),
                          nodes=int(mesh_counts.get("nodes", 0)),
                          tetrahedra=int(mesh_counts.get("tetrahedra", 0)))
    bundle["domain"] = dict(min=air_lo, max=air_hi)
    bundle["nf2ff_box"] = copy.deepcopy(bundle["domain"])
    bundle["nf2ff_center"] = [0, 0, 0]
    bundle["half_space"] = None
    # Task 2: AbsorbingBoundary defaults order=2, abctype="B" (assembler applies second-order).
    bundle["solver"] = dict(
        engine="EMerge", method="Frequency-domain FEM (experimental)",
        excitation=dict(type="Harmonic rectangular terminal", f_min=settings["f_min_hz"],
                        f_max=settings["f_max_hz"], dc_free=True),
        boundaries={k: "Second-order absorbing" for k in ("x-", "x+", "y-", "y+", "z-", "z+")},
        end_criteria_db=0, max_timesteps=0)
    bundle["run"] = None
    bundle["experimental"] = dict(
        solver="EMerge", precision_converged=False,
        limitations=list(result.get("limitations", case["limitations"])),
        settings=settings, input_sha256=result.get("input_sha256"),
        pec_approximations=list(result.get("pec_approximations", case["pec_approximations"])),
        phasor_convention="exp(+i omega t); native EMerge, not conjugated",
        native_phasor_convention=result.get("native_phasor_convention", "exp(+i omega t)"))
    port = bundle["ports"][0]
    width_axis = next(i for i in range(3) if i != "xyz".index(design["ports"][0]["direction"]))
    port["start"][width_axis] -= settings.get("feed_width_mm", 1) / 2
    port["stop"][width_axis] += settings.get("feed_width_mm", 1) / 2
    # Same phasor as Fairbeam frames: keep native S11 (no conjugation).
    reflection = np.asarray(result["s11_re"], dtype=float) + 1j * np.asarray(result["s11_im"], dtype=float)
    z_ref = float(result.get("z_ref", case["port"]["z0"]))
    denominator = 1 - reflection
    if np.any(np.abs(denominator) < 1e-12):
        raise ValueError("Cannot export singular input impedance")
    impedance = z_ref * (1 + reflection) / denominator
    bundle["results"] = dict(
        frequency=list(result["frequency_hz"]),
        ports={str(port["number"]): dict(
            s11_re=reflection.real.tolist(), s11_im=reflection.imag.tolist(),
            zin_re=impedance.real.tolist(), zin_im=impedance.imag.tolist(), z_ref=z_ref)},
        bands=[], signals={}, farfield=[])
    return bundle
