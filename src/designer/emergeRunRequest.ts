import { createSignal } from "solid-js";
import { researchPath } from "../runner/researchState";
import {
  classifyEmergeDraft,
  defaultMapKind,
  draftNeedsFiniteFeedAccept,
  draftNeedsLumpedTerminalAccept,
  draftNeedsModalPortAccept,
  draftShowsCoaxPadding,
  draftShowsDrivenFeed,
  draftShowsPlanarEnclosure,
  mapOptionsFor,
  type EmergeMapKind,
  type PreviewPortInput,
} from "./emergePortMapPreview";
import {
  emergeAdmitResolution,
  emergeSettings,
  fieldCutFrequenciesHzFromText,
} from "./emergeSettings";

/** Last Port mapping choice from EMerge Run. Sweep and optimize read it when it still fits the ports. */
export const [sessionEmergeMapKind, setSessionEmergeMapKind] = createSignal<EmergeMapKind | null>(null);

export type EmergeResearchSource = {
  model_id: string;
  workspace_hash: string;
  backup_scope: string;
};

export function emergeResearchSource(
  health: { research_source?: boolean },
  saved: { id: string; hash: string; backup_scope?: string },
): EmergeResearchSource | undefined {
  return health.research_source && saved.backup_scope
    ? { model_id: saved.id, workspace_hash: saved.hash, backup_scope: saved.backup_scope }
    : undefined;
}

/** Map kind a sweep or optimizer should send when the Run form is closed. */
export function currentEmergeMapKind(ports: PreviewPortInput[] | null | undefined): EmergeMapKind | null {
  const hint = classifyEmergeDraft(ports);
  const next = defaultMapKind(ports, hint);
  const stored = sessionEmergeMapKind();
  if (stored == null) return next;
  const first = Array.isArray(ports) && ports.length ? ports[0] : null;
  const raw = first?.type;
  const type = raw == null || raw === "" ? "lumped" : String(raw);
  const allowed = new Set(mapOptionsFor(type, hint).map((option) => option.kind));
  return allowed.has(stored) ? stored : next;
}

/** Settings object a single Design EMerge Run submits. */
export function emergeNportSettings(
  ports: PreviewPortInput[] | null | undefined,
  mapKind: EmergeMapKind | null,
): Record<string, unknown> {
  const s = emergeSettings();
  const showCoax = draftShowsCoaxPadding(ports);
  const showDriven = draftShowsDrivenFeed(ports);
  const showPlanar = draftShowsPlanarEnclosure(ports);
  const settings: Record<string, unknown> = {
    analysis: "emerge_nport",
    resolution: emergeAdmitResolution(s),
    f_min_hz: Number(s.f_min_ghz) * 1e9,
    f_max_hz: Number(s.f_max_ghz) * 1e9,
    points: Number(s.points),
  };
  if (showCoax) {
    settings.accept_coaxial_tem = true;
    settings.padding_mm = Number(s.padding_mm);
  } else {
    settings.approximate_metals = s.approximate_metals;
    settings.refine_conductor_edges = s.refine_conductor_edges;
    if (draftNeedsFiniteFeedAccept(ports)) settings.accept_finite_feed = true;
    const needsMap = draftNeedsLumpedTerminalAccept(ports) || draftNeedsModalPortAccept(ports);
    if (needsMap && mapKind === "wave") settings.accept_modal_ports = true;
    else if (needsMap && mapKind === "lumped") settings.accept_lumped_terminals = true;
    if (showPlanar) {
      settings.enclosure = s.enclosure;
      settings.air_height_mm = Number(s.air_height_mm);
    }
    if (showDriven) {
      settings.feed_width_mm = Number(s.feed_width_mm);
      settings.padding_mm = Number(s.padding_mm);
    } else if (s.enclosure === "open") {
      settings.padding_mm = Number(s.padding_mm);
    }
  }
  const cutHz = fieldCutFrequenciesHzFromText(s.field_cut_frequencies_ghz);
  if (cutHz) settings.field_cut_frequencies_hz = cutHz;
  return settings;
}

export function emergeSolveRequest(
  ports: PreviewPortInput[] | null | undefined,
  mapKind: EmergeMapKind | null,
  source: EmergeResearchSource | undefined,
): { path: string; settings: Record<string, unknown>; source?: EmergeResearchSource } {
  return {
    path: researchPath("emerge"),
    settings: emergeNportSettings(ports, mapKind),
    ...(source ? { source } : {}),
  };
}
