// EMerge Simulation Settings: Frequency, Boundaries (enclosure), and curated Mesh knobs.
// Edits the session emergeSettings object used by Run — never openEMS draft.mesh cells/λ.
import { createSignal, For, onCleanup, onMount, Show } from "solid-js";
import { Box, Grid3x3, Waves, X } from "lucide-solid";
import { FOCUSABLE, useModal } from "../lib/dialog";
import { tabKeyTarget } from "../lib/tabKeys";
import { setSimSettingsOpen, setSimSettingsSection, simSettingsSection } from "./simSettingsState";
import {
  cloneEmergeSettings,
  emergeAdmitResolution,
  emergeEnclosureFaces,
  setEmergeSettings,
  type EmergeEnclosure,
  type EmergeFaceKind,
  type EmergeResolutionPreset,
  type EmergeSessionSettings,
} from "./emergeSettings";
import { emergeMode, resolveRunSolver, type EmergeMode } from "./activeEngine";
import { setSessionFemMesh } from "./emergeFemMesh";
import { setMeshView } from "./MeshView";
import { fmt, t } from "../i18n";
import NumberField from "../components/NumberField";
import { api, isTerminal } from "../runner/api";
import { researchPath } from "../runner/researchState";
import { refreshRuns } from "../runner/store";
import { defaultDesignerSession, file, prepareSavedDesign } from "./store";
import { hasDocumentResultScope } from "../lib/nativeDocuments";

function meshAdmitErrorMessage(err: Error): string {
  return err.message || "";
}

const SECTIONS = [
  { id: "freq", label: "sim.section.freq", icon: Waves },
  { id: "bounds", label: "sim.section.bounds", icon: Box },
  { id: "mesh", label: "sim.section.mesh", icon: Grid3x3 },
] as const;

type SectionId = (typeof SECTIONS)[number]["id"];

type MeshCounts = { nodes: number; tetrahedra: number; duration_s: number };

const FACES = ["x−", "x+", "y−", "y+", "z−", "z+"] as const;
const FACE_STYLE: Record<EmergeFaceKind, { short: string; label: string; hint: string; color: string }> = {
  PEC: { short: "PEC", label: "sim.bound.pec", hint: "sim.bound.pec.hint", color: "var(--al-3d-metal)" },
  ABC: { short: "ABC", label: "emergeSim.bound.abc", hint: "emergeSim.bound.abc.hint", color: "var(--al-series-1)" },
};

/** Unfolded box of the six faces; read-only — enclosure preset drives the labels. */
function EmergeBoundaryBox(props: { faces: EmergeFaceKind[] }) {
  const S = 52;
  // [column, row] of each face in the net: z+ above y−, z− below it, x− / y− / x+ / y+ around
  const CELL: [number, number][] = [[0, 1], [2, 1], [1, 1], [3, 1], [1, 2], [1, 0]];
  return (
    <svg class="ss-box ss-box-ro" viewBox={`-4 -4 ${4 * S + 8} ${3 * S + 22}`} role="img"
      aria-label={t("emergeSim.bounds.boxAria")} data-testid="emerge-boundary-box">
      <For each={FACES}>{(face, k) => {
        const [c, r] = CELL[k()];
        const ty = () => FACE_STYLE[props.faces[k()]];
        return (
          <g aria-label={`${face}: ${ty().short}`}>
            <rect class="ss-face" x={c * S} y={r * S} width={S - 2} height={S - 2} rx={3}
              style={{ fill: ty().color, "fill-opacity": 0.28 }} />
            <text x={c * S + (S - 2) / 2} y={r * S + S / 2 - 6} text-anchor="middle">{face}</text>
            <text x={c * S + (S - 2) / 2} y={r * S + S / 2 + 8} text-anchor="middle">{ty().short}</text>
          </g>
        );
      }}</For>
      <text class="ss-axis-l" x={0} y={3 * S + 14}>{t("sim.bounds.unfolded")}</text>
    </svg>
  );
}

function resolveSection(start: string): SectionId {
  return SECTIONS.some((s) => s.id === start) ? (start as SectionId) : "freq";
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

function meshSettingsFromDraft(draft: EmergeSessionSettings, mode: EmergeMode): Record<string, unknown> {
  const resolution = emergeAdmitResolution(draft);
  const fMin = Number(draft.f_min_ghz) * 1e9;
  const fMax = Number(draft.f_max_ghz) * 1e9;
  let points = Math.round(Number(draft.points));
  if (mode === "emerge-driven") {
    points = Math.min(21, Math.max(3, points));
    return {
      analysis: "emerge_nport",
      accept_finite_feed: true,
      approximate_metals: draft.approximate_metals,
      resolution,
      feed_width_mm: Number(draft.feed_width_mm),
      padding_mm: Number(draft.padding_mm),
      // Planar keys so classify can try planar Discrete boards before driven.
      enclosure: draft.enclosure,
      air_height_mm: Number(draft.air_height_mm),
      refine_conductor_edges: draft.refine_conductor_edges,
      f_min_hz: fMin,
      f_max_hz: fMax,
      points,
      mesh_only: true,
    };
  }
  points = Math.min(41, Math.max(3, points));
  const settings: Record<string, unknown> = {
    analysis: "emerge_nport",
    accept_lumped_terminals: true,
    accept_finite_feed: true,
    approximate_metals: draft.approximate_metals,
    refine_conductor_edges: draft.refine_conductor_edges,
    resolution,
    enclosure: draft.enclosure,
    air_height_mm: Number(draft.air_height_mm),
    feed_width_mm: Number(draft.feed_width_mm),
    f_min_hz: fMin,
    f_max_hz: fMax,
    points,
    mesh_only: true,
  };
  // Always include padding for driven fallback; solver strips it for shielded planar.
  settings.padding_mm = Number(draft.padding_mm);
  return settings;
}

export default function EmergeSimSettings() {
  let box: HTMLDivElement | undefined;
  let pane: HTMLDivElement | undefined;
  const opened = cloneEmergeSettings();
  const [draft, setDraft] = createSignal(cloneEmergeSettings(opened));
  const startSection = resolveSection(simSettingsSection());
  const [section, setSection] = createSignal<SectionId>(startSection);
  const [meshBusy, setMeshBusy] = createSignal(false);
  const [meshError, setMeshError] = createSignal("");
  const [meshCounts, setMeshCounts] = createSignal<MeshCounts | null>(null);
  const changed = () => JSON.stringify(draft()) !== JSON.stringify(opened);
  const close = () => {
    setEmergeSettings(draft());
    setSimSettingsOpen(false);
  };
  const cancel = () => {
    if (meshBusy()) return;
    setEmergeSettings(opened);
    setSimSettingsOpen(false);
  };
  useModal(() => box, cancel);

  const patch = (p: Partial<EmergeSessionSettings>) => setDraft((old) => ({ ...old, ...p }));

  let pinned = 0;
  let alive = true;
  onCleanup(() => { alive = false; });
  const go = (id: SectionId) => {
    setSection(id);
    pinned = Date.now() + 800;
    const target = pane?.querySelector<HTMLElement>(`#ess-${id}`);
    if (pane && target) pane.scrollTop += target.getBoundingClientRect().top - pane.getBoundingClientRect().top;
  };

  onMount(() => {
    // Match SimSettingsDialog: consume the ribbon section once, then clear the shared latch.
    setSimSettingsSection("freq");
    requestAnimationFrame(() => go(startSection));
  });

  const onScroll = () => {
    if (!pane || Date.now() < pinned) return;
    if (pane.scrollTop + pane.clientHeight >= pane.scrollHeight - 2) {
      setSection(SECTIONS[SECTIONS.length - 1].id);
      return;
    }
    const top = pane.scrollTop + 24;
    let cur: SectionId = SECTIONS[0].id;
    for (const s of SECTIONS) {
      const el = pane.querySelector<HTMLElement>(`#ess-${s.id}`);
      if (el && el.offsetTop - pane.offsetTop <= top) cur = s.id;
    }
    setSection(cur);
  };

  const onTabKey = (e: KeyboardEvent & { currentTarget: HTMLElement }) => {
    const i = SECTIONS.findIndex((s) => document.getElementById(`ess-tab-${s.id}`) === document.activeElement);
    if (i < 0) return;
    if (e.key === "Tab" && !e.shiftKey) {
      const panel = pane?.querySelector(`#ess-${section()}`);
      const target = [...(panel?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? [])].find((x) => x.offsetParent !== null);
      if (target) { e.preventDefault(); target.focus(); }
      return;
    }
    const next = tabKeyTarget(e.key, i, SECTIONS.length);
    if (next === null) return;
    e.preventDefault();
    go(SECTIONS[next].id);
    document.getElementById(`ess-tab-${SECTIONS[next].id}`)?.focus();
  };

  const modeHint = () => emergeMode() === "emerge-driven" ? t("emergeSim.modeDriven") : emergeMode() === "emerge-planar" ? t("emergeSim.modePlanar") : t("emergeSim.modeUnset");
  const enclosureFaces = () => emergeEnclosureFaces(draft().enclosure, emergeMode());
  const admitResolution = () => emergeAdmitResolution(draft());

  const meshBlockedTitle = () => {
    if (!file()) return t("emergeSim.generateMeshNeedFile");
    return "";
  };
  const meshDisabled = () => meshBusy() || !!meshBlockedTitle();

  const generateMesh = async () => {
    if (meshDisabled() || !file()) return;
    setMeshBusy(true);
    setMeshError("");
    setMeshCounts(null);
    setEmergeSettings(draft());
    // Ownership before save: abandon if the draft changes under us.
    // After prepareSavedDesign, use target.isCurrent() — save updates hash/revision and must not
    // look like a stale click (that used to abort Generate mesh with no error and no counts).
    const request = defaultDesignerSession.asyncState.ticket();
    const initialFile = file()!;
    const ownsPreSave = () => alive && defaultDesignerSession.asyncState.isDraftCurrent(request)
      && file()?.id === initialFile.id && file()?.hash === initialFile.hash && file()?.backup_scope === initialFile.backup_scope;
    try {
      const health = await api.health();
      if (!ownsPreSave()) throw Error(t("emergeSim.generateMeshStale"));
      const solver = resolveRunSolver(health.emerge ?? 0);
      if (solver !== "emerge") {
        throw Error(t("emergeSim.generateMeshNeedInstall"));
      }
      if ((health.emerge ?? 0) < 3 || (hasDocumentResultScope(file()) && !health.research_source)) {
        throw Error(t("emergeExp.serverUpdate"));
      }
      const capability = await api.researchProbe("emerge", researchPath("emerge"));
      if (!ownsPreSave()) throw Error(t("emergeSim.generateMeshStale"));
      if (!capability.available) throw Error(t("emergeExp.unavailable"));
      const target = await prepareSavedDesign(() => alive);
      if (!alive) return;
      if (!target?.isCurrent()) throw Error(t("run.err.notSaved"));
      const geomMode = emergeMode() ?? "emerge-planar";
      const settings = meshSettingsFromDraft(draft(), geomMode);
      const saved = target.file;
      const source = health.research_source && saved.backup_scope
        ? { model_id: saved.id, workspace_hash: saved.hash, backup_scope: saved.backup_scope } : undefined;
      if (hasDocumentResultScope(saved) && !source) {
        throw Error(t("emergeExp.serverUpdate"));
      }
      if (!target.isCurrent()) throw Error(t("emergeSim.generateMeshStale"));
      const job = await api.researchStart({
        backend: "emerge", path: researchPath("emerge"),
        design: structuredClone(saved.design), settings, ...(source ? { source } : {}),
      });
      void refreshRuns();
      let current = job;
      while (alive && target.isCurrent() && !isTerminal(current.status)) {
        await sleep(750);
        if (!alive || !target.isCurrent()) return;
        current = await api.researchRun(current.id);
      }
      if (!alive || !target.isCurrent()) return;
      if (current.status !== "done" || !current.result) {
        throw Error(current.error || t("emergeSim.generateMeshFailed"));
      }
      const result = current.result as {
        schema?: string; nodes?: number; tetrahedra?: number; duration_s?: number;
        mesh?: {
          nodes?: number; tetrahedra?: number;
          surface?: {
            schema?: string; units?: string; nodes_mm?: number[][]; edges?: number[][];
            thinned?: boolean; edge_stride?: number; edge_count?: number;
          };
        };
      };
      if (result.schema !== "fairbeam.emerge-mesh-result/1") {
        throw Error(t("emergeSim.generateMeshFailed"));
      }
      const nodes = result.nodes ?? result.mesh?.nodes;
      const tetrahedra = result.tetrahedra ?? result.mesh?.tetrahedra;
      const duration = result.duration_s;
      if (typeof nodes !== "number" || typeof tetrahedra !== "number" || typeof duration !== "number") {
        throw Error(t("emergeSim.generateMeshFailed"));
      }
      setMeshCounts({ nodes, tetrahedra, duration_s: duration });
      const surface = result.mesh?.surface;
      if (surface?.units === "mm" && Array.isArray(surface.nodes_mm) && Array.isArray(surface.edges)
          && surface.nodes_mm.length > 0 && surface.edges.length > 0) {
        setSessionFemMesh({
          nodes, tetrahedra,
          surface: {
            schema: surface.schema,
            units: "mm",
            nodes_mm: surface.nodes_mm,
            edges: surface.edges,
            thinned: surface.thinned,
            edge_stride: surface.edge_stride,
            edge_count: surface.edge_count,
          },
          source: "session",
        });
        setMeshView(true);
      }
    } catch (err) {
      if (alive) setMeshError(meshAdmitErrorMessage(err as Error));
    } finally {
      if (alive) setMeshBusy(false);
    }
  };

  return (
    <div class="scrim">
      <div class="dialog ss-dialog" role="dialog" aria-modal="true" aria-labelledby="ess-title" ref={box} tabindex={-1} data-testid="emerge-sim-settings">
        <div class="dialog-head">
          <div>
            <h2 id="ess-title">{t("emergeSim.title")}</h2>
            <p class="muted">{t("emergeSim.subtitle")}</p>
          </div>
          <button class="icon-btn" onClick={cancel} disabled={meshBusy()} aria-label={changed() ? t("sim.discardClose") : t("sim.cancelClose")}><X size={16} /></button>
        </div>
        <div class="ss-main">
          <nav class="ss-nav" role="tablist" aria-label={t("sim.sections")} aria-orientation="vertical" onKeyDown={onTabKey}>
            <For each={SECTIONS}>{(s) => (
              <button role="tab" id={`ess-tab-${s.id}`} aria-controls={`ess-${s.id}`} aria-selected={section() === s.id}
                tabindex={section() === s.id ? 0 : -1} onClick={() => go(s.id)}>
                <s.icon size={14} aria-hidden="true" /> {t(s.label)}
              </button>
            )}</For>
          </nav>
          <div class="ss-pane" ref={pane} onScroll={onScroll}>
            <p class="note">{t("emergeSim.experimental")}</p>
            <p class="note">{modeHint()}</p>

            <section id="ess-freq" class="stack" aria-labelledby="ess-freq-title">
              <h3 id="ess-freq-title">{t("sim.section.freq")}</h3>
              <div class="rd-grid">
                <label class="dz-field">
                  <span class="dz-label">{t("emergeSim.f_min_ghz")}</span>
                  <NumberField class="rp-input dz-input mono" data-testid="emerge-sim-fmin" value={draft().f_min_ghz}
                    aria-label={t("emergeSim.f_min_ghz")}
                    onInput={(e) => patch({ f_min_ghz: e.currentTarget.value })} />
                </label>
                <label class="dz-field">
                  <span class="dz-label">{t("emergeSim.f_max_ghz")}</span>
                  <NumberField class="rp-input dz-input mono" data-testid="emerge-sim-fmax" value={draft().f_max_ghz}
                    aria-label={t("emergeSim.f_max_ghz")}
                    onInput={(e) => patch({ f_max_ghz: e.currentTarget.value })} />
                </label>
                <label class="dz-field">
                  <span class="dz-label">{t("emergeSim.points")}</span>
                  <NumberField class="rp-input dz-input mono" data-testid="emerge-sim-points" value={draft().points}
                    aria-label={t("emergeSim.points")}
                    onInput={(e) => patch({ points: e.currentTarget.value })} />
                </label>
                <label class="dz-field">
                  <span class="dz-label">{t("emergeSim.air_height_mm")}</span>
                  <NumberField class="rp-input dz-input mono" data-testid="emerge-sim-air" value={draft().air_height_mm}
                    aria-label={t("emergeSim.air_height_mm")}
                    onInput={(e) => patch({ air_height_mm: e.currentTarget.value })} />
                </label>
                <label class="dz-field">
                  <span class="dz-label">{t("emergeSim.feed_width_mm")}</span>
                  <NumberField class="rp-input dz-input mono" data-testid="emerge-sim-feed" value={draft().feed_width_mm}
                    aria-label={t("emergeSim.feed_width_mm")}
                    onInput={(e) => patch({ feed_width_mm: e.currentTarget.value })} />
                </label>
              </div>
              <p class="note">{t("emergeSim.freqHint")}</p>
            </section>

            <section id="ess-bounds" class="stack" aria-labelledby="ess-bounds-title">
              <h3 id="ess-bounds-title">{t("sim.section.bounds")}</h3>
              <p class="note">{t("emergeSim.boundsNote")}</p>
              <div class="ss-bounds">
                <EmergeBoundaryBox faces={enclosureFaces()} />
                <div class="stack">
                  <div class="rd-grid">
                    <label class="dz-field">
                      <span class="dz-label">{t("emergeSim.enclosure")}</span>
                      <select class="rp-select dz-input mono" data-testid="emerge-sim-enclosure" aria-label={t("emergeSim.enclosure")}
                        value={draft().enclosure}
                        onChange={(e) => patch({ enclosure: e.currentTarget.value as EmergeEnclosure })}>
                        <option value="shielded">{t("emergeExp.shielded")}</option>
                        <option value="open">{t("emergeExp.open")}</option>
                      </select>
                    </label>
                    <Show when={draft().enclosure === "open" || emergeMode() === "emerge-driven"}>
                      <label class="dz-field">
                        <span class="dz-label">{t("emergeSim.padding_mm")}</span>
                        <NumberField class="rp-input dz-input mono" data-testid="emerge-sim-padding" value={draft().padding_mm}
                          aria-label={t("emergeSim.padding_mm")}
                          onInput={(e) => patch({ padding_mm: e.currentTarget.value })} />
                      </label>
                    </Show>
                  </div>
                  <div class="ss-legend">
                    <For each={(["PEC", "ABC"] as EmergeFaceKind[])}>{(kind) => {
                      const ty = FACE_STYLE[kind];
                      return <span title={t(ty.hint)}><span class="ss-swatch" style={{ background: ty.color }} aria-hidden="true" />{t(ty.label)}</span>;
                    }}</For>
                  </div>
                  <p class="note">{t("emergeSim.bounds.readonly")}</p>
                </div>
              </div>
              <Show when={emergeMode() === "emerge-driven"} fallback={
                <>
                  <p class="note">{t(draft().enclosure === "shielded" ? "emergeExp.enclosureShieldedHint" : "emergeExp.enclosureOpenHint")}</p>
                  <p class="note">{t("emergeSim.abcNote")}</p>
                </>
              }>
                <p class="note">{t("emergeSim.enclosureDrivenHint")}</p>
                <p class="note">{t("emergeSim.abcNote")}</p>
              </Show>
            </section>

            <section id="ess-mesh" class="stack" aria-labelledby="ess-mesh-title">
              <h3 id="ess-mesh-title">{t("sim.section.mesh")}</h3>
              <div class="rd-grid">
                <label class="dz-field">
                  <span class="dz-label">{t("emergeSim.resolution")}</span>
                  <select class="rp-select dz-input mono" data-testid="emerge-sim-resolution" aria-label={t("emergeSim.resolution")}
                    value={draft().resolution}
                    onChange={(e) => patch({ resolution: e.currentTarget.value as EmergeResolutionPreset })}>
                    <option value="coarse">{t("emergeSim.coarse")}</option>
                    <option value="fine">{t("emergeSim.fine")}</option>
                    <option value="custom">{t("emergeSim.custom")}</option>
                  </select>
                </label>
                <Show when={draft().resolution === "custom"}>
                  <label class="dz-field">
                    <span class="dz-label">{t("emergeSim.resolution_lambda")}</span>
                    <NumberField class="rp-input dz-input mono" data-testid="emerge-sim-lambda" value={draft().resolution_lambda}
                      aria-label={t("emergeSim.resolution_lambda")}
                      onInput={(e) => patch({ resolution_lambda: e.currentTarget.value })} />
                  </label>
                </Show>
                <label class="dz-field">
                  <span class="dz-label">{t("emergeSim.global_max_size_mm")}</span>
                  <NumberField class="rp-input dz-input mono" data-testid="emerge-sim-maxsize" value={draft().global_max_size_mm}
                    aria-label={t("emergeSim.global_max_size_mm")}
                    onInput={(e) => patch({ global_max_size_mm: e.currentTarget.value })} />
                </label>
              </div>
              <Show when={draft().resolution === "custom"}>
                <p class="note">{t("emergeSim.customAdmitHint", { value: String(admitResolution()) })}</p>
              </Show>
              <label class="gs-check">
                <input type="checkbox" data-testid="emerge-sim-refine" checked={draft().refine_conductor_edges}
                  onChange={(e) => patch({ refine_conductor_edges: e.currentTarget.checked })} />
                {t("emergeSim.refineConductorEdges")}
              </label>
              <p class="note">{t("emergeSim.refineConductorEdgesHint")}</p>
              <label class="gs-check">
                <input type="checkbox" data-testid="emerge-sim-approx" checked={draft().approximate_metals}
                  onChange={(e) => patch({ approximate_metals: e.currentTarget.checked })} />
                {t("emergeSim.approximateMetals")}
              </label>
              <p class="note">{t("emergeSim.approximateMetalsHint")}</p>
              <p class="note">{t("emergeSim.meshNote")}</p>
              <div class="cluster">
                <button class="btn btn-ghost" type="button" data-testid="emerge-sim-generate-mesh"
                  disabled={meshDisabled()} title={meshBlockedTitle() || undefined}
                  onClick={() => void generateMesh()}>
                  {meshBusy() ? t("emergeSim.generateMeshBusy") : t("emergeSim.generateMesh")}
                </button>
              </div>
              <Show when={meshError()}><p class="note" role="alert" data-testid="emerge-sim-mesh-error">{meshError()}</p></Show>
              <Show when={meshCounts()}>{c => (
                <p class="note" role="status" data-testid="emerge-sim-mesh-counts">
                  {t("emergeSim.meshCounts", {
                    nodes: fmt.int(c().nodes),
                    tets: fmt.int(c().tetrahedra),
                    seconds: fmt.fixed(c().duration_s, 2),
                  })}
                </p>
              )}</Show>
              <p class="note">{t("emergeSim.meshCountsHint")}</p>
            </section>
          </div>
        </div>
        <div class="dialog-foot">
          <button class="btn btn-ghost" type="button" disabled={meshBusy()} onClick={cancel}>{t("common.cancel")}</button>
          <button class="btn btn-primary" type="button" data-testid="emerge-sim-ok" disabled={meshBusy()} onClick={close}>{t("common.ok")}</button>
        </div>
      </div>
    </div>
  );
}
