// What the live run views (the designer dock's Run tab, the Run panel's progress card and the status
// bar) say about a running job, from its phase, its latest progress event and the run's own info.
// Pure, so scripts/check-run-numbers.mjs checks it in Node.
import type { Phase, ProgressEvent, RunInfo, RunStats } from "./api";

/** Phases in the order a run goes through them. */
const ORDER: Phase[] = ["queued", "building", "setup", "running", "postprocessing", "exporting"];
/** The share of the progress bar a phase starts at: the solver takes the most room. */
const START: Record<string, number> = { queued: 0, building: 0.02, setup: 0.05, running: 0.08, postprocessing: 0.92, exporting: 0.97 };
const SOLVER_SHARE = START.postprocessing - START.running;

/** Research EMerge Design jobs share the designer Run dock with openEMS. */
export function isEmergeResearchJob(
  job: { kind?: string; research?: { backend?: string } | null } | null | undefined,
): boolean {
  return !!job && job.kind === "research" && job.research?.backend === "emerge";
}

/** An optimize job whose candidates are EMerge solves, not ``fairbeam optimize`` (openEMS). */
export function isEmergeOptimizeJob(
  job: { kind?: string; optimize?: { emerge?: unknown } | null } | null | undefined,
): boolean {
  return !!job && job.kind === "optimize" && job.optimize?.emerge != null;
}

/**
 * Map research-only phase names onto the openEMS dock spine so the strip and bar advance.
 * openEMS phases pass through unchanged. Unknown names fall back to queued (honest empty strip).
 */
export function normalizeDockPhase(phase: string | null | undefined): Phase {
  const raw = phase ?? "queued";
  if (raw === "simulating") return "running";
  if (raw === "results_exported" || raw === "validating") return "exporting";
  if ((ORDER as string[]).includes(raw)) return raw as Phase;
  if (raw === "done") return "done" as Phase;
  return "queued";
}

/** The solver has finished (or the run ended): what it said about the timesteps no longer applies. */
export function pastSolver(phase: Phase | null | undefined, status: string): boolean {
  if (["done", "failed", "cancelled", "interrupted"].includes(status)) return true;
  const dock = normalizeDockPhase(phase);
  const i = ORDER.indexOf(dock);
  return i > ORDER.indexOf("running") || dock === "done";
}

/** The latest timestep the run reached: the live progress line, else the solver's summary. */
export function reachedTimestep(progress: ProgressEvent | null | undefined, stats: RunStats | null | undefined): number | null {
  const a = progress?.timestep, b = stats?.timesteps;
  const n = Math.max(typeof a === "number" ? a : -1, typeof b === "number" ? b : -1);
  return n >= 0 ? n : null;
}

export type PulseNote =
  | { kind: "overLimit"; pulse: number; limit: number }
  | { kind: "running"; end: number; left: number };

/** Why the energy line is flat at the start: the excitation pulse is still running (the energy only
 * starts to fall once it ends), or it would not end before the limit at all. Nothing once the solver
 * is past the pulse or has finished (a fast run ends between two progress lines). */
export function pulseNote(info: RunInfo, progress: ProgressEvent | null | undefined, stats: RunStats | null | undefined,
  phase: Phase | null | undefined, status: string): PulseNote | null {
  const end = info.pulse_steps, limit = info.max_timesteps;
  if (!end || pastSolver(phase, status)) return null;
  if (limit && end >= limit) return { kind: "overLimit", pulse: end, limit };
  // before the solver starts there is no timestep to compare: the note belongs to the FDTD phase
  if (normalizeDockPhase(phase) !== "running") return null;
  // without a timestep reading nothing is known about the pulse: openEMS prints one only every few
  // seconds, so a short run often has none before it ends, and "0 of 1,876" would be wrong
  const ts = reachedTimestep(progress, stats);
  if (ts === null) return null;
  return ts < end ? { kind: "running", end, left: end - ts } : null;
}

/** How far the job is, 0 to 1, for the progress bar and the status bar: the phase it is in, and in the
 * solver the furthest of the energy decay towards the end criterion, the timestep towards the solver's
 * projected end, and the timestep towards the limit. Multi-port runs share the solver's part by port. */
export function runFraction(job: { status: string; phase?: Phase | string | null }, progress: ProgressEvent | null | undefined, info: RunInfo = {}): number {
  if (job.status === "done") return 1;
  const phase = normalizeDockPhase(job.phase);
  // Research FEM jobs have no timestep/energy fraction: hold the bar at the start of the solve share.
  const emergeCoarse = isEmergeResearchJob(job as { kind?: string; research?: { backend?: string } });
  if (phase !== "running") return START[phase] ?? (pastSolver(phase, job.status) ? 1 : 0);
  if (emergeCoarse) return START.running;
  const p = progress;
  const ts = p?.timestep ?? 0;
  const target = p?.eta?.target_timestep;
  const solver = Math.max(0, Math.min(1, Math.max(
    p?.energy_fraction ?? 0,
    p?.timestep_fraction ?? (info.max_timesteps ? ts / info.max_timesteps : 0),
    target && target > 0 ? ts / target : 0,
  )));
  const total = Math.max(1, p?.port_total ?? info.port_total ?? 1);
  const done = Math.max(0, (p?.port_run ?? info.port_run ?? 1) - 1);
  return START.running + SOLVER_SHARE * Math.min(1, (done + solver) / total);
}

/** The field energy samples of the current port (openEMS starts over for every excited port) count as
 * enough to forecast the end once the energy has fallen this far below its peak: before that the
 * pulse is still running or the decay has just begun, and a straight-line fit jumps by minutes. */
export const ETA_MIN_DECAY_DB = 10;
export const ETA_MIN_SAMPLES = 3;
export function decayEstablished(energy: readonly { ts: number; db: number }[]): boolean {
  if (energy.length < ETA_MIN_SAMPLES) return false;
  let peak = -Infinity, peakAt = 0;
  energy.forEach((p, i) => { if (p.db > peak) { peak = p.db; peakAt = i; } });
  const after = energy.length - 1 - peakAt;
  return after >= ETA_MIN_SAMPLES - 1 && peak - energy[energy.length - 1].db >= ETA_MIN_DECAY_DB;
}
