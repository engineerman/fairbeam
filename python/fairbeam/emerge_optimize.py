"""EMerge parameter search.

One optimize job. Each candidate is an EMerge research solve
(``research.prepare`` with that point's ``param_overrides``, then ``research.execute``).
The search is ``optimize.optimize``. This module does not call ``fairbeam run`` or
``fairbeam optimize`` (those run openEMS).
"""
import argparse
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path

from .optimize import OPT_SCHEMA, RADIATION_GOALS, Vary, _atomic_json, _emit, bundle_metrics, make_goal, optimize
from .research import emerge_drawing_design, encode, execute, prepare

EMPTY_FAR_FIELD = "EMerge far field is empty"


def refuse_radiation_goals(goals):
    """Radiation goals need a far field. EMerge results leave that list empty."""
    if not isinstance(goals, list):
        return
    found = []
    for goal in goals:
        kind = goal.get("kind") if isinstance(goal, dict) else getattr(goal, "kind", None)
        if kind in RADIATION_GOALS and kind not in found:
            found.append(kind)
    if found:
        raise ValueError(f"{EMPTY_FAR_FIELD}, so {', '.join(found)} cannot be scored")


def check_goal_band(goals, settings):
    """Goal frequencies are GHz. EMerge settings store the band in Hz."""
    if not isinstance(settings, dict):
        raise ValueError("emerge settings must be an object")
    f_min, f_max = settings.get("f_min_hz"), settings.get("f_max_hz")
    if (isinstance(f_min, bool) or not isinstance(f_min, (int, float)) or not math.isfinite(f_min)
            or isinstance(f_max, bool) or not isinstance(f_max, (int, float)) or not math.isfinite(f_max)
            or f_min <= 0 or f_max <= f_min):
        raise ValueError("EMerge settings need a positive f_min_hz below f_max_hz")
    lo, hi = float(f_min) / 1e9, float(f_max) / 1e9
    for goal in goals:
        kind = goal["kind"] if isinstance(goal, dict) else goal.kind
        at = goal["at"] if isinstance(goal, dict) else goal.at
        at_hi = goal["at_hi"] if isinstance(goal, dict) else goal.at_hi
        if at is not None and not lo - 1e-9 <= float(at) <= hi + 1e-9:
            raise ValueError(f"goal {kind}: {float(at):g} GHz is outside the EMerge band {lo:g}-{hi:g} GHz")
        if at_hi is not None and float(at_hi) > hi + 1e-9:
            raise ValueError(f"goal {kind}: upper frequency is outside the EMerge band {lo:g}-{hi:g} GHz")


def _slug(model_id, point):
    parts = [str(model_id)] + [f"{key}-{value:g}" for key, value in sorted(point.items())]
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", "--".join(parts)).strip("-").lower() or "point"


def _ports(design):
    ports = design.get("ports") if isinstance(design, dict) else None
    if not isinstance(ports, list):
        return []
    return [p["number"] for p in ports if isinstance(p, dict) and type(p.get("number")) is int]


def run_emerge_optimization(design, emerge, vary, goals, *, out, name=None, max_evals=12,
                            method="auto", fixed=None, seed=0):
    """Search ``vary`` with ``optimize``. Each point is one EMerge research solve."""
    refuse_radiation_goals(goals)
    if not isinstance(emerge, dict) or "path" not in emerge or not isinstance(emerge.get("settings"), dict):
        raise ValueError("emerge optimization expects path and settings")
    check_goal_band(goals, emerge["settings"])
    fixed = {key: float(value) for key, value in (fixed or {}).items()}
    model = design.get("model") if isinstance(design, dict) else {}
    model_id = (model or {}).get("id") or "design"
    model_name = (model or {}).get("name") or model_id
    name = name or f"{model_id}-opt"
    out = Path(out)
    member_dir = out / "optimizations" / name
    ports = _ports(design)
    goal_rows = [g if isinstance(g, dict) else {"kind": g.kind, "target": g.target, "at": g.at,
                                                "weight": g.weight, "ports": list(g.ports) if g.ports else None,
                                                "at_hi": g.at_hi, "label": g.label()} for g in goals]
    doc = {
        "schema": OPT_SCHEMA, "name": name,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "model": {"id": model_id, "name": model_name},
        "method": method, "vary": [{"key": v.key, "lo": v.lo, "hi": v.hi, "start": v.start} for v in vary],
        "goals": goal_rows, "fixed": fixed, "max_evals": max_evals,
        "ports": ports, "excite": ports, "engine": "emerge",
        "evaluations": [], "best": None, "start": None, "reason": "running", "finished": None,
    }
    doc_path = out / "optimizations" / f"{name}.json"
    t_start = time.time()
    _emit("start", {"name": name, "file": f"optimizations/{name}.json", "vary": doc["vary"],
                    "goals": doc["goals"], "max_evals": max_evals, "engine": "emerge",
                    "ports": ports, "excite": ports})

    def evaluate(point):
        overrides = {**fixed, **{key: float(value) for key, value in point.items()}}
        t0 = time.time()
        try:
            spec = prepare({
                "backend": "emerge", "path": emerge["path"], "settings": emerge["settings"],
                "design": design, "param_overrides": overrides,
            })
            raw = encode(spec)
            digest = hashlib.sha256(raw).hexdigest()
            slug = _slug(model_id, point)
            folder = member_dir / slug
            solve = folder / "solve"
            solve.mkdir(parents=True, exist_ok=True)
            snapshot = folder / "research.json"
            snapshot.write_bytes(raw)
            execute(snapshot, solve, digest)
            result = json.loads((solve / "result.json").read_text(encoding="utf-8"))
            from .emerge_bundle import export_emerge_bundle
            bundle = export_emerge_bundle(emerge_drawing_design(spec), result)
        except (OSError, ValueError, RuntimeError) as exc:
            return {"metrics": {}, "error": str(exc), "wall_time_s": time.time() - t0}
        # EMerge bundles leave farfield empty and do not set run.converged. That is not a failed solve.
        bundle["optimization"] = {"name": name, "point": point}
        rel = f"optimizations/{name}/{slug}.json"
        _atomic_json(out / rel, bundle)
        return {"metrics": bundle_metrics(bundle, goals), "file": rel, "wall_time_s": time.time() - t0}

    def on_eval(entry):
        doc["evaluations"].append(entry)
        best = min((row for row in doc["evaluations"] if not row.get("error")),
                   key=lambda row: row["cost"], default=None)
        doc["best"], doc["start"] = best, doc["evaluations"][0]
        doc["wall_time_s"] = round(time.time() - t_start, 2)
        _atomic_json(doc_path, doc, indent=1)
        _emit("eval", {**entry, "best_index": best["index"] if best else None,
                       "best_cost": best["cost"] if best else None, "max_evals": max_evals})

    start = {v.key: float(v.start if v.start is not None else (v.lo + v.hi) / 2) for v in vary}
    try:
        result = optimize(vary, goals, evaluate, method=method, seed=seed, max_evals=max_evals,
                          start=start, on_eval=on_eval)
    except BaseException as exc:
        doc.update(reason=f"error: {type(exc).__name__}: {exc}" if isinstance(exc, Exception) else "interrupted",
                   finished=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                   wall_time_s=round(time.time() - t_start, 2))
        _atomic_json(doc_path, doc, indent=1)
        raise
    doc.update(method=result["method"], reason=result["reason"], best=result["best"], start=result["start"],
               finished=time.strftime("%Y-%m-%dT%H:%M:%S%z"), wall_time_s=round(time.time() - t_start, 2))
    _atomic_json(doc_path, doc, indent=1)
    _emit("done", {"name": name, "file": f"optimizations/{name}.json", "reason": result["reason"],
                   "method": result["method"], "evaluations": len(result["history"]),
                   "best": result["best"], "start": result["start"], "wall_time_s": doc["wall_time_s"]})
    doc["_path"] = str(doc_path)
    return doc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    design = json.loads(Path(args.design).read_text(encoding="utf-8"))
    job = json.loads(Path(args.job).read_text(encoding="utf-8"))
    spec = job.get("optimize") or {}
    emerge = spec.get("emerge")
    if not isinstance(emerge, dict):
        print("fairbeam: error: EMerge optimize job is missing emerge settings", file=sys.stderr)
        return 2
    vary = [Vary(row["key"], row["min"], row["max"], row.get("start")) for row in spec.get("vary") or []]
    goals = [make_goal(row["kind"], row["target"], row.get("at"), row.get("weight") or 1.0,
                       tuple(row["ports"]) if row.get("ports") else None, row.get("at_hi"))
             for row in spec.get("goals") or []]
    fixed = {key: float(value) for key, value in (job.get("overrides") or {}).items()}
    try:
        run_emerge_optimization(design, emerge, vary, goals, out=Path(args.out), name=job.get("name"),
                                max_evals=spec.get("max_evals", 12), method=spec.get("method", "auto"),
                                fixed=fixed)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"fairbeam: error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
