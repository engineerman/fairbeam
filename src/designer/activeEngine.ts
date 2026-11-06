import { createSignal } from "solid-js";

/** Primary Simulation chrome engines (Elmer stays outside this picker). */
export type ActiveEngine = "openems" | "emerge";

/**
 * Last EMerge geometry hint for Sim Settings faces (not the Run `<select>` value).
 * Unified Run uses solver id `emerge`; these tokens only remember driven vs planar UI.
 */
export type EmergeMode = "emerge-driven" | "emerge-planar";

const [activeEngine, setActiveEngineRaw] = createSignal<ActiveEngine>("openems");
const [emergeMode, setEmergeModeRaw] = createSignal<EmergeMode | null>(null);

export { activeEngine, emergeMode };

export function setActiveEngine(engine: ActiveEngine): void {
  setActiveEngineRaw(engine);
}

export function setEmergeMode(mode: EmergeMode | null): void {
  setEmergeModeRaw(mode);
}

export const isEmerge = (): boolean => activeEngine() === "emerge";

/** Short engine name for Run chrome (not an i18n key — product names stay Latin). */
export function activeEngineLabel(): string {
  return activeEngine() === "emerge" ? "EMerge" : "openEMS";
}

/** Whether health.emerge admits the unified EMerge Run path (Level B3: >= 3). */
export function emergeRunAdmitted(emergeLevel: number): boolean {
  return emergeLevel >= 3;
}

/**
 * Solver `<select>` value when opening Run from ribbon chrome.
 * `null` = EMerge chrome but health below unified gate → open Research / Install instead.
 */
export function resolveRunSolver(emergeLevel: number): "openems" | "emerge" | null {
  if (activeEngine() !== "emerge") return "openems";
  if (emergeRunAdmitted(emergeLevel)) return "emerge";
  return null;
}

/**
 * Keep ribbon chrome consistent with the Run dialog solver pick.
 * Elmer options do not force the primary picker off openEMS / EMerge.
 */
export function applyRunSolverToChrome(solver: string): void {
  if (solver === "openems") {
    setActiveEngine("openems");
    return;
  }
  if (solver === "emerge") {
    setActiveEngine("emerge");
  }
}
