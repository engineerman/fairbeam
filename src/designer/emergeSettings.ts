import { createSignal } from "solid-js";

/** Session-only EMerge Simulation Settings (not written into openEMS draft.mesh). */
export type EmergeEnclosure = "shielded" | "open";
export type EmergeResolutionPreset = "coarse" | "fine" | "custom";

export type EmergeSessionSettings = {
  f_min_ghz: string;
  f_max_ghz: string;
  points: string;
  air_height_mm: string;
  enclosure: EmergeEnclosure;
  padding_mm: string;
  feed_width_mm: string;
  resolution: EmergeResolutionPreset;
  /** Wavelength fraction when resolution is custom (e.g. 0.2). */
  resolution_lambda: string;
  /** Empty string = unset (do not send set_global_max_size). */
  global_max_size_mm: string;
  refine_conductor_edges: boolean;
  approximate_metals: boolean;
};

export const EMERGE_DEFAULT_SETTINGS: EmergeSessionSettings = {
  f_min_ghz: "0.75",
  f_max_ghz: "1.25",
  points: "15",
  air_height_mm: "6.4",
  enclosure: "shielded",
  padding_mm: "10",
  feed_width_mm: "1",
  resolution: "coarse",
  resolution_lambda: "0.2",
  global_max_size_mm: "",
  // Default on: matches prior always-on planar bakeoff (0.4 mm set_boundary_size).
  refine_conductor_edges: true,
  // When false (default), sheet/trace σ maps to EMerge ThinConductor. When true, force PEC for this run.
  approximate_metals: false,
};

const [emergeSettings, setEmergeSettingsRaw] = createSignal<EmergeSessionSettings>({ ...EMERGE_DEFAULT_SETTINGS });

export { emergeSettings };

export function setEmergeSettings(next: EmergeSessionSettings): void {
  setEmergeSettingsRaw({ ...next });
}

export function patchEmergeSettings(patch: Partial<EmergeSessionSettings>): void {
  setEmergeSettingsRaw((old) => ({ ...old, ...patch }));
}

/** Clone for Cancel / restore in the settings dialog. */
export function cloneEmergeSettings(s: EmergeSessionSettings = emergeSettings()): EmergeSessionSettings {
  return { ...s };
}

/**
 * Value sent to admit / worker: named preset, or the typed Custom λ-fraction in (0, 0.5].
 * Invalid custom falls back to coarse so the dialog can still open; admit rejects bad numbers.
 */
export function emergeAdmitResolution(s: EmergeSessionSettings = emergeSettings()): "coarse" | "fine" | number {
  if (s.resolution === "fine" || s.resolution === "coarse") return s.resolution;
  const r = Number(s.resolution_lambda);
  if (!Number.isFinite(r) || !(r > 0 && r <= 0.5)) return "coarse";
  return r;
}

/** @deprecated Use emergeAdmitResolution — kept for call sites that only need a named preset label. */
export function emergeWorkerResolution(s: EmergeSessionSettings = emergeSettings()): "coarse" | "fine" {
  const v = emergeAdmitResolution(s);
  if (v === "fine" || v === "coarse") return v;
  const mid = (0.15 + 0.25) / 2;
  return v <= mid ? "fine" : "coarse";
}

/** Face order matches openEMS Simulation Settings: x−, x+, y−, y+, z−, z+. */
export type EmergeFaceKind = "PEC" | "ABC";

/**
 * Read-only face kinds the experimental worker applies for the given enclosure
 * and last EMerge Run mode. Driven antenna always uses ABC on all six faces;
 * planar open keeps a PEC floor (z−); shielded is PEC on every face.
 */
export function emergeEnclosureFaces(
  enclosure: EmergeEnclosure,
  mode: "emerge-driven" | "emerge-planar" | "emerge" | null = null,
): EmergeFaceKind[] {
  // Driven antenna path always sets AbsorbingBoundary on every exterior face.
  if (mode === "emerge-driven") return ["ABC", "ABC", "ABC", "ABC", "ABC", "ABC"];
  // Planar / unified / unset: enclosure preset. Open keeps the substrate-bottom PEC floor.
  if (enclosure === "shielded") return ["PEC", "PEC", "PEC", "PEC", "PEC", "PEC"];
  return ["ABC", "ABC", "ABC", "ABC", "PEC", "ABC"];
}
