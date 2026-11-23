"""EM design-curve study for the hairpin wizard.

Builds the small singly-loaded and coupled-pair designs, reads Qe and k the
way the hairpin EM design-curve extract procedure does, and queues each sample
through ``JobManager`` (openEMS, one solve at a time). The wizard process does
not call ``sim.run``.
"""

from __future__ import annotations

import copy
import json
import math
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

from fairbeam.filter_synthesis.hairpin_bp_common import (
    MIN_EDGE_GAP_MM_FRAC,
    bandpass_qe_and_k,
    response_qe_ripple,
)
from fairbeam.filter_synthesis.hairpin_microstrip_bp import set_hairpin_placement_exprs

# Measured openEMS sweep on the 2.0 GHz baseline (q_len 22.933 mm, h 1.524 mm).
# The 12 mm tap was ambiguous and is not a sample. Scale these ratios onto the
# seed so another stack keeps the same sample count. This is not a new Qe/k formula.
_BASE_Q_LEN_MM = 22.933
_BASE_H_MM = 1.524
_BASE_TAPS_MM = (2.0, 4.0, 5.852, 8.0)
_BASE_SPACINGS_MM = (0.4, 0.7, 1.002, 1.5, 2.5)
_BAND = 0.2
_POINTS = 81
#: Single-resonator Qe samples: pulse length in cycles of the band center. The sweep stays
#: ``f0 ± 0.5`` GHz and the stop stays −40 dB. Three cycles is a few ring periods.
_QE_PULSE_CYCLES = 3
_STUDY_ID = re.compile(r"^he-\d{8}-\d{6}-[0-9a-f]{4}$")
SOLVER = "openEMS"
# Same flag as the Run dialog's GPU path (`fairbeam run --engine gpu`). Host threads stay 1:
# the CUDA engine does not scale with --threads.
ENGINE = "gpu"


def _default(design: dict, key: str) -> float:
    for param in design.get("params", []):
        if param.get("key") == key and "expr" not in param and "default" in param:
            return float(param["default"])
    raise KeyError(key)


def set_independent(design: dict, key: str, value: float) -> None:
    """Write a numeric default. Tunable rows keep a ±20% band around the new value."""
    value = float(value)
    for param in design.get("params", []):
        if param.get("key") != key or "expr" in param:
            continue
        param["default"] = value
        if "min" in param or "max" in param:
            span = abs(value) * _BAND or 0.1
            param["min"] = value - span
            param["max"] = value + span
        return
    raise KeyError(key)


def resonator_count(design: dict) -> int:
    n = 0
    while any(p.get("key") == f"w{n}" and "expr" not in p for p in design.get("params", [])):
        n += 1
    return n


def _filter_part(design: dict) -> dict:
    for part in design.get("parts", []):
        if part.get("name") == "filter":
            return part
    raise ValueError("hairpin design has no filter part")


def _place(design: dict, n_res: int, tap_mm: float, spacings_mm: list[float]) -> None:
    """Write the chosen tap and spacings. Placement expressions follow those knobs."""
    if len(spacings_mm) != max(n_res - 1, 0):
        raise ValueError("spacings_mm must have one entry between each resonator")
    set_independent(design, "tap_from_fold", tap_mm)
    for k, sp in enumerate(spacings_mm):
        set_independent(design, f"sp{k}", sp)
    set_hairpin_placement_exprs(design, n_res)


def study_design(
    seed: dict,
    *,
    n_res: int,
    tap_mm: float,
    spacings_mm: list[float],
    one_port: bool,
) -> dict:
    """Clone the seed and keep ``n_res`` alternating U resonators.

    A Qe sample is one resonator and port 1. A k sample is a coupled pair and
    both ports. ``q_len``, ``w*``, and ``gap*`` stay at the seed.
    """
    if n_res < 1:
        raise ValueError("n_res must be at least 1")
    design = copy.deepcopy(seed)
    order = resonator_count(design)
    if n_res > order:
        raise ValueError("study has more resonators than the seed")
    part = _filter_part(design)
    prims = part.get("primitives") or []
    if len(prims) != 2 + 3 * order:
        raise ValueError("filter primitives are not feed + 3 boxes per U + feed")
    _place(design, n_res, tap_mm, spacings_mm)
    kept = prims[0 : 1 + 3 * n_res]
    if not one_port:
        kept = kept + [prims[-1]]
    part["primitives"] = kept
    if one_port:
        design["ports"] = [design["ports"][0]]
        design["ports"][0]["excite"] = True
    sim = design.setdefault("simulation", {})
    if one_port:
        sim["pulse_cycles"] = _QE_PULSE_CYCLES
    sim["f_min"] = "f0-0.5"
    sim["f_max"] = "f0+0.5"
    sim["max_timesteps"] = 250_000
    sim["end_criteria_db"] = -40
    design["far_field"] = {"enabled": False}
    design.pop("monitors", None)
    return design


def assemble_design(seed: dict, tap_mm: float, sp_mm: float | None) -> dict:
    """Full-order design: chosen tap and one mirrored spacing. q_len, w*, gap* stay."""
    design = copy.deepcopy(seed)
    order = resonator_count(design)
    if order < 1:
        raise ValueError("design has no resonators")
    if order == 1 or sp_mm is None:
        spacings = [_default(design, f"sp{k}") for k in range(order - 1)]
    else:
        spacings = [float(sp_mm)] * (order - 1)
    _place(design, order, float(tap_mm), spacings)
    return design


def tap_samples(q_len_mm: float) -> list[float]:
    lo = max(0.25, MIN_EDGE_GAP_MM_FRAC * q_len_mm)
    hi = q_len_mm - lo
    if not (hi > lo):
        raise ValueError("quarter-wave length is too short for a tap sweep")
    measured: list[float] = []
    for tap in _BASE_TAPS_MM:
        x = min(max(tap / _BASE_Q_LEN_MM * q_len_mm, lo), hi)
        if not any(abs(x - y) < 1e-4 for y in measured):
            measured.append(x)
    if len(measured) >= 2:
        return measured
    return [lo, hi]


def spacing_samples(h_mm: float) -> list[float]:
    floor = MIN_EDGE_GAP_MM_FRAC * h_mm
    measured: list[float] = []
    for sp in _BASE_SPACINGS_MM:
        x = max(sp / _BASE_H_MM * h_mm, floor)
        if not any(abs(x - y) < 1e-6 for y in measured):
            measured.append(x)
    if len(measured) < 2:
        raise ValueError("need two spacing samples")
    return measured


def plan_samples(design: dict, electrical: dict) -> list[dict]:
    order = resonator_count(design)
    if order != int(electrical["order"]):
        raise ValueError("design order does not match the electrical target")
    samples = [{"kind": "qe", "tap_mm": tap} for tap in tap_samples(_default(design, "q_len"))]
    if order >= 2:
        samples.extend({"kind": "k", "sp_mm": sp} for sp in spacing_samples(_default(design, "h")))
    return samples


def qe_k_targets(electrical: dict) -> tuple[float, float | None]:
    """Mean outer Qe and the first k. Equiripple has no formula, so it raises."""
    if not isinstance(electrical, dict):
        raise ValueError("electrical targets are required")
    try:
        raw_order = electrical["order"]
        f0 = float(electrical["f0_hz"])
        bw = float(electrical["bw_hz"])
        ripple = float(electrical["ripple_db"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("electrical targets need order, f0_hz, bw_hz, and ripple_db") from exc
    if isinstance(raw_order, bool) or not isinstance(raw_order, (int, float)) or not float(raw_order).is_integer():
        raise ValueError("order must be an integer >= 1")
    order = int(raw_order)
    if order < 1:
        raise ValueError("order must be an integer >= 1")
    qe_ripple = response_qe_ripple(str(electrical.get("response") or "chebyshev"), ripple)
    if qe_ripple is None:
        raise ValueError(
            "Equiripple ripple is stored and is not used as Chebyshev passband ripple; "
            "no Qe/k formula is defined."
        )
    if not math.isfinite(f0) or f0 == 0 or not math.isfinite(bw) or not (bw / f0 > 0):
        raise ValueError("fbw must be positive")
    qe1, qen, ks = bandpass_qe_and_k(order, bw / f0, qe_ripple)
    return 0.5 * (qe1 + qen), (float(ks[0]) if ks else None)


def _smooth3(y: np.ndarray) -> np.ndarray:
    out = np.convolve(y, np.ones(3) / 3.0, mode="same")
    out[0] = y[0]
    out[-1] = y[-1]
    return out


def external_q(freq_hz: np.ndarray, s11: np.ndarray) -> dict:
    """Qe from the steepest S11 phase slope. Ambiguous when that peak is not unique."""
    f = np.asarray(freq_hz, float)
    s = np.asarray(s11, complex)
    phase = np.unwrap(np.angle(s))
    phase_s = _smooth3(phase)
    omega = 2.0 * np.pi * f
    slope = np.abs(np.gradient(phase_s, omega))
    i = int(np.argmax(slope))
    ambiguous = False
    reason = None
    if i <= 1 or i >= len(slope) - 2:
        ambiguous = True
        reason = "slope_peak_at_band_edge"
    else:
        window = slope.copy()
        lo = max(0, i - 4)
        hi = min(len(slope), i + 5)
        window[lo:hi] = 0.0
        j = int(np.argmax(window))
        if window[j] > 0.75 * slope[i]:
            ambiguous = True
            reason = "second_slope_peak"
    return {
        "qe": float(omega[i] / 4.0 * slope[i]),
        "f_res_hz": float(f[i]),
        "ambiguous": ambiguous,
        "ambiguous_reason": reason,
    }


def coupling_k(freq_hz: np.ndarray, s21_db: np.ndarray) -> dict:
    """k from the two tallest |S21| peaks. A split under one bin is unresolved, not k = 0."""
    f = np.asarray(freq_hz, float)
    y = np.asarray(s21_db, float)
    bin_hz = float(np.median(np.diff(f)))
    peaks = [i for i in range(1, len(y) - 1) if y[i] >= y[i - 1] and y[i] > y[i + 1]]
    base = {"bin_hz": bin_hz, "status": "unresolved", "k": None, "reason": "single_peak"}
    if len(peaks) < 2:
        return base
    peaks.sort(key=lambda i: y[i], reverse=True)
    i0 = peaks[0]
    i1 = next((i for i in peaks[1:] if abs(f[i] - f[i0]) >= bin_hz), None)
    if i1 is None:
        base["reason"] = "weak_split"
        return base
    fl, fh = sorted((float(f[i0]), float(f[i1])))
    if fh - fl < bin_hz:
        base["reason"] = "weak_split"
        return base
    return {
        "bin_hz": bin_hz,
        "status": "ok",
        "k": float((fh * fh - fl * fl) / (fh * fh + fl * fl)),
        "reason": None,
    }


def interpolate_to_target(samples: list[dict], x_key: str, y_key: str, target: float, prefer_x: float) -> dict:
    """Linear interpolation. Outside the sampled range: nearest sample, clamped, not extrapolated."""
    pts = [p for p in samples if p.get(y_key) is not None and p.get("status", "ok") == "ok"]
    pts.sort(key=lambda p: float(p[x_key]))
    if len(pts) < 2:
        raise RuntimeError(f"need two {y_key} samples to choose a geometry")
    brackets = []
    for a, b in zip(pts, pts[1:]):
        y0, y1 = float(a[y_key]), float(b[y_key])
        x0, x1 = float(a[x_key]), float(b[x_key])
        if y0 == y1:
            if y0 == target:
                brackets.append((x0, abs(x0 - prefer_x)))
            continue
        if (y0 - target) * (y1 - target) <= 0.0:
            t = (target - y0) / (y1 - y0)
            x = x0 + t * (x1 - x0)
            brackets.append((x, abs(x - prefer_x)))
    if not brackets:
        nearest = min(pts, key=lambda p: abs(float(p[y_key]) - target))
        return {"x": float(nearest[x_key]), "clamped": True, "extrapolated": False}
    brackets.sort(key=lambda row: row[1])
    return {"x": float(brackets[0][0]), "clamped": False, "extrapolated": False}


def _s11(bundle: dict) -> tuple[np.ndarray, np.ndarray]:
    results = bundle["results"]
    port = results["ports"]["1"]
    s11 = np.asarray(port["s11_re"], float) + 1j * np.asarray(port["s11_im"], float)
    return np.asarray(results["frequency"], float), s11


def _s21_db(bundle: dict) -> tuple[np.ndarray, np.ndarray]:
    results = bundle["results"]
    entry = results["sparams"]["s"]["2,1"]
    s21 = np.asarray(entry["re"], float) + 1j * np.asarray(entry["im"], float)
    db = 20.0 * np.log10(np.maximum(np.abs(s21), 1e-30))
    return np.asarray(results["frequency"], float), db


def _measure(sample: dict, bundle: dict, job_id: str) -> dict:
    if sample["kind"] == "qe":
        info = external_q(*_s11(bundle))
        ok = not info["ambiguous"]
        return {
            "job": job_id,
            "kind": "qe",
            "tap_mm": float(sample["tap_mm"]),
            "qe": info["qe"] if ok else None,
            "status": "ok" if ok else "skipped",
        }
    info = coupling_k(*_s21_db(bundle))
    ok = info["status"] == "ok" and info["k"] is not None
    return {
        "job": job_id,
        "kind": "k",
        "sp_mm": float(sample["sp_mm"]),
        "k": info["k"] if ok else None,
        "status": "ok" if ok else "skipped",
    }


def _sample_fraction(progress: dict | None) -> float:
    """0..1 from stored energy toward the −40 dB stop.

    Qe and k samples share this scale. The timestep fraction is a different unit
    (a finished sample is still near a fifth of the 250k cap), so the energy-fit
    fallback must not switch to it. Ringing is handled by :meth:`_hold_fraction`.
    """
    if not isinstance(progress, dict):
        return 0.0
    raw = progress.get("energy_fraction")
    if raw is None:
        return 0.0
    try:
        return max(0.0, min(1.0, float(raw)))
    except (TypeError, ValueError):
        return 0.0


def _phase(study: dict) -> str | None:
    """Label the sample the UI should show: Qe, k, or layout assembly."""
    if study.get("status") != "running":
        return None
    samples = study.get("samples") or []
    index = int(study.get("completed") or 0)
    if index >= len(samples):
        return "assemble"
    kind = samples[index].get("kind")
    if kind == "qe":
        return "qe"
    if kind == "k":
        return "k"
    return None


class HairpinEdcStudies:
    """One openEMS sample at a time. Cancel leaves the caller's seed design alone."""

    def __init__(self, manager, projects_dir: Path):
        self.manager = manager
        self.dir = Path(projects_dir) / "studies"
        self.lock = threading.RLock()
        self._admission = threading.Lock()
        self._stop: set[str] = set()
        # (sample index, highest energy fraction seen). Never carry a peak onto the next sample.
        self._fraction_peak: dict[str, tuple[int, float]] = {}

    def path(self, study_id: str) -> Path:
        self._check_id(study_id)
        return self.dir / f"{study_id}.json"

    @staticmethod
    def _check_id(study_id: str) -> None:
        if not isinstance(study_id, str) or not _STUDY_ID.fullmatch(study_id):
            raise KeyError(study_id)

    def load(self, study_id: str) -> dict | None:
        try:
            study = json.loads(self.path(study_id).read_text(encoding="utf-8"))
        except (OSError, ValueError, KeyError):
            return None
        if not isinstance(study, dict) or study.get("id") != study_id:
            return None
        return study

    def _write(self, study: dict) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self.path(study["id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(study), encoding="utf-8")
        os.replace(tmp, path)

    @staticmethod
    def _public(study: dict) -> dict:
        out = {
            "id": study["id"],
            "status": study["status"],
            "completed": study["completed"],
            "total": study["total"],
            "solver": SOLVER,
            "error": study.get("error"),
            "phase": _phase(study),
        }
        if study.get("status") == "done" and isinstance(study.get("design"), dict):
            out["design"] = study["design"]
        return out

    def _hold_fraction(self, study: dict, raw: float) -> float:
        """Highest energy fraction seen for this sample. A later dip does not lower it."""
        study_id = study.get("id")
        if not isinstance(study_id, str):
            return raw
        index = int(study.get("completed") or 0)
        prev = self._fraction_peak.get(study_id)
        held = raw if prev is None or prev[0] != index else max(prev[1], raw)
        self._fraction_peak[study_id] = (index, held)
        return held

    def _view(self, study: dict) -> dict:
        out = self._public(study)
        status, raw = self._sample_view(study)
        fraction = self._hold_fraction(study, raw) if status in ("running", "queued") else raw
        total = max(int(study.get("total") or 0), 1)
        completed = int(study.get("completed") or 0)
        if study.get("status") == "done":
            run = 1.0
        else:
            run = min(1.0, (completed + fraction) / total)
        out["sample_status"] = status
        out["sample_fraction"] = fraction
        out["run_fraction"] = run
        return out

    def _job_for(self, study_id: str, index: int):
        with self.manager.lock:
            found = None
            for job in self.manager.jobs.values():
                sweep = job.sweep or {}
                if sweep.get("kind") != "hairpin-edc" or sweep.get("id") != study_id:
                    continue
                if int(sweep.get("index") or 0) != index:
                    continue
                found = job
            return found

    def _sample_view(self, study: dict) -> tuple[str | None, float]:
        if study.get("status") != "running":
            return None, 0.0
        samples = study.get("samples") or []
        index = int(study.get("completed") or 0)
        if index >= len(samples):
            return None, 0.0
        job = self._job_for(study.get("id"), index)
        if job is None:
            return None, 0.0
        if job.status == "queued":
            return "queued", 0.0
        if job.status != "running":
            return None, 0.0
        return "running", _sample_fraction(job.last_progress)

    def _adopt_terminal_sample(self, study: dict) -> None:
        """Catch up when poll sees a finished sample before the manager callback runs.

        Successful ``done`` jobs use the same path as :meth:`on_finished` (RLock
        re-enters). Do not mark them ``failed`` — that raced the UI poll into
        ``sample failed`` while openEMS had already exported a bundle.
        """
        if study.get("status") != "running":
            return
        samples = study.get("samples") or []
        index = int(study.get("completed") or 0)
        if index >= len(samples):
            return
        job = self._job_for(study.get("id"), index)
        if job is None or not job.terminal:
            return
        if any(row.get("job") == job.id for row in study.get("rows") or []):
            return
        if job.status == "cancelled":
            self._mark_cancelled(study)
            self._write(study)
            return
        if job.status == "done":
            self.on_finished(job)
            return
        self._fail(study, job.error or "sample failed")
        self._write(study)

    def _cancel_other_running(self) -> None:
        """One hairpin study at a time. A new click must not sit behind an older sample."""
        if not self.dir.is_dir():
            return
        ids: list[str] = []
        for path in self.dir.glob("*.json"):
            if ".design." in path.name:
                continue
            try:
                study = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if (isinstance(study, dict) and study.get("status") == "running"
                    and isinstance(study.get("id"), str)):
                ids.append(study["id"])
        for study_id in ids:
            try:
                self.cancel(study_id)
            except KeyError:
                pass

    def _stopped(self, study: dict) -> bool:
        with self._admission:
            return bool(study.get("stop_requested") or study["id"] in self._stop)

    def _fail(self, study: dict, message: str) -> None:
        study["status"] = "failed"
        study["error"] = message
        study.pop("design", None)

    def _mark_cancelled(self, study: dict) -> None:
        study["status"] = "cancelled"
        study["stop_requested"] = True
        study["error"] = None
        study.pop("design", None)

    def _submit(self, study: dict, index: int):
        with self._admission:
            if study.get("stop_requested") or study["id"] in self._stop:
                return None
            sample = study["samples"][index]
            one_port = sample["kind"] == "qe"
            n_res = 1 if one_port else 2
            spacings = [] if one_port else [float(sample["sp_mm"])]
            design = study_design(
                study["seed"],
                n_res=n_res,
                tap_mm=float(sample["tap_mm"]) if one_port else _default(study["seed"], "tap_from_fold"),
                spacings_mm=spacings,
                one_port=one_port,
            )
            path = self.dir / f"{study['id']}-{index}.design.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            text = json.dumps(design)
            path.write_text(text, encoding="utf-8")
            model_id = design.get("model", {}).get("id") or study["id"]
            return self.manager.submit(
                model=str(model_id),
                model_id=str(model_id) if model_id else None,
                model_path=str(path),
                design_input=text,
                threads=1,
                engine=ENGINE,
                points=_POINTS,
                excite="all" if sample["kind"] == "k" else None,
                name=f"hairpin-edc-{index + 1}",
                sweep={
                    "id": study["id"],
                    "kind": "hairpin-edc",
                    "index": index,
                    "total": study["total"],
                    "values": {key: sample[key] for key in ("tap_mm", "sp_mm") if key in sample},
                },
            )

    def _assemble(self, study: dict) -> dict:
        seed = study["seed"]
        tap = interpolate_to_target(
            [r for r in study["rows"] if r["kind"] == "qe"],
            "tap_mm",
            "qe",
            float(study["target_qe"]),
            _default(seed, "tap_from_fold"),
        )
        sp = None
        if study.get("target_k") is not None:
            prefer = _default(seed, "sp0")
            sp = interpolate_to_target(
                [r for r in study["rows"] if r["kind"] == "k"],
                "sp_mm",
                "k",
                float(study["target_k"]),
                prefer,
            )["x"]
        return assemble_design(seed, tap["x"], sp)

    def start(self, design: dict, electrical: dict) -> dict:
        self._cancel_other_running()
        try:
            return self._start(design, electrical)
        except KeyError as exc:
            raise ValueError(f"design is missing {exc}") from exc

    def _start(self, design: dict, electrical: dict) -> dict:
        if not isinstance(design, dict) or not isinstance(design.get("model"), dict):
            raise ValueError("design must be a hairpin design")
        if not design.get("ports"):
            raise ValueError("design must include the microstrip ports")
        qe, k = qe_k_targets(electrical)
        samples = plan_samples(design, electrical)
        study_id = "he-" + time.strftime("%Y%m%d-%H%M%S") + "-" + os.urandom(2).hex()
        study: dict[str, Any] = {
            "schema": "fairbeam.hairpin-edc/1",
            "id": study_id,
            "status": "running",
            "completed": 0,
            "total": len(samples),
            "solver": SOLVER,
            "error": None,
            "seed": copy.deepcopy(design),
            "samples": samples,
            "rows": [],
            "target_qe": qe,
            "target_k": k,
            "stop_requested": False,
        }
        with self.lock:
            job = self._submit(study, 0)
            if job is None:
                raise ValueError("study was not started")
            self._write(study)
        return self._view(study)

    def poll(self, study_id: str) -> dict:
        self._check_id(study_id)
        with self.lock:
            study = self.load(study_id)
            if study is None:
                raise KeyError(study_id)
            self._adopt_terminal_sample(study)
            # on_finished may have advanced the study on disk; re-read for the view.
            study = self.load(study_id)
            if study is None:
                raise KeyError(study_id)
            return self._view(study)

    def cancel(self, study_id: str) -> dict:
        self._check_id(study_id)
        with self._admission:
            self._stop.add(study_id)
        try:
            with self.lock:
                study = self.load(study_id)
                if study is None:
                    raise KeyError(study_id)
                if study.get("status") == "running":
                    self._mark_cancelled(study)
                    self._write(study)
            self.manager.cancel_sweep(study_id)
            study = self.load(study_id)
            if study is None:
                raise KeyError(study_id)
            return self._view(study)
        finally:
            with self._admission:
                self._stop.discard(study_id)

    def on_finished(self, job) -> None:
        sweep = getattr(job, "sweep", None) or {}
        if sweep.get("kind") != "hairpin-edc":
            return
        with self.lock:
            study = self.load(sweep["id"])
            if study is None or study.get("status") != "running":
                return
            if any(row.get("job") == job.id for row in study["rows"]):
                return
            if self._stopped(study):
                self._mark_cancelled(study)
                self._write(study)
                return
            index = int(sweep["index"])
            sample = study["samples"][index]
            if job.status != "done" or not job.bundle:
                self._fail(study, getattr(job, "error", None) or "sample failed")
                self._write(study)
                return
            try:
                bundle_path = Path(self.manager.projects_dir) / job.bundle
                bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
                study["rows"].append(_measure(sample, bundle, job.id))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self._fail(study, str(exc))
                self._write(study)
                return
            study["completed"] = len(study["rows"])
            if self._stopped(study):
                self._mark_cancelled(study)
                self._write(study)
                return
            if study["completed"] < study["total"]:
                try:
                    nxt = self._submit(study, study["completed"])
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    self._fail(study, str(exc))
                    self._write(study)
                    return
                if nxt is None:
                    self._mark_cancelled(study)
                self._write(study)
                return
            try:
                study["design"] = self._assemble(study)
                study["status"] = "done"
                study["error"] = None
            except (RuntimeError, ValueError, KeyError) as exc:
                self._fail(study, str(exc))
            self._write(study)
