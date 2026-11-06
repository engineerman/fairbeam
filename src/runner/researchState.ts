import { createSignal } from "solid-js";
import type { ResearchBackend } from "./api";

export const [researchOpen, setResearchOpen] = createSignal(false);
export const [researchSelectedId, setResearchSelectedId] = createSignal<string | null>(null);
export const [researchInitialBackend, setResearchInitialBackend] = createSignal<ResearchBackend>("periodic");
export const [researchResultsOnly, setResearchResultsOnly] = createSignal(false);
export function openResearch(id?: string, backend: ResearchBackend = "periodic", resultsOnly = false) {
  setResearchResultsOnly(resultsOnly);
  setResearchInitialBackend(backend);
  setResearchSelectedId(id ?? null);
  setResearchOpen(true);
}

/** Driven Elmer/EMerge antenna, EMerge planar, and unified N-port: follow in the designer dock.
 * Level A fixtures (WR-90, PEC cavity, …) stay in the Experimental solvers panel. */
export function isDesignBoundResearch(job: {
  kind?: string;
  research?: { settings?: Record<string, unknown> } | null;
}): boolean {
  if (job.kind !== "research") return false;
  const analysis = job.research?.settings?.analysis;
  return analysis === "driven" || analysis === "planar_two_port" || analysis === "emerge_nport";
}

const PATH_KEY = "fairbeam.research.paths";
export function researchPath(backend: string): string {
  try { return JSON.parse(localStorage.getItem(PATH_KEY) ?? "{}")[backend] ?? ""; } catch { return ""; }
}
export function rememberResearchPath(backend: string, path: string) {
  try {
    const paths = JSON.parse(localStorage.getItem(PATH_KEY) ?? "{}");
    localStorage.setItem(PATH_KEY, JSON.stringify({ ...paths, [backend]: path }));
  } catch { /* Storage may be disabled; the path still works for this session. */ }
}
