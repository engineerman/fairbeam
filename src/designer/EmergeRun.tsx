import { createEffect, createSignal, For, onCleanup, onMount, Show } from "solid-js";
import { api } from "../runner/api";
import { openResearch, researchPath } from "../runner/researchState";
import { followInDesigner } from "../runner/designRun";
import { refreshRuns } from "../runner/store";
import { defaultDesignerSession, draft, errorCount, file, names, prepareSavedDesign } from "./store";
import RunChecksAlert from "./RunChecksAlert";
import { tryEvaluate } from "./expr";
import { t } from "../i18n";
import NumberField from "../components/NumberField";
import { hasDocumentResultScope } from "../lib/nativeDocuments";
import {
  EMERGE_DEFAULT_SETTINGS,
  FIELD_CUT_FREQS_MAX,
  emergeAdmitResolution,
  emergeSettings,
  fieldCutFrequenciesHzFromText,
  patchEmergeSettings,
  type EmergeEnclosure,
  type EmergeResolutionPreset,
} from "./emergeSettings";
import EmergePortMapPreview from "./EmergePortMapPreviewView";
import {
  classifyEmergeDraft,
  defaultMapKind,
  draftNeedsCoaxialTemAccept,
  draftNeedsFiniteFeedAccept,
  draftNeedsLumpedTerminalAccept,
  draftNeedsModalPortAccept,
  draftShowsCoaxPadding,
  draftShowsPlanarEnclosure,
  draftShowsDrivenFeed,
  mapOptionsFor,
  previewPorts,
  acceptIntentFromMapKind,
  type EmergeMapKind,
} from "./emergePortMapPreview";
import { setEmergeMode } from "./activeEngine";
import { emergeNportSettings, emergeResearchSource, setSessionEmergeMapKind } from "./emergeRunRequest";

const BAND_KEYS = ["f_min_hz", "f_max_hz", "points"] as const;

/** Single opt-in EMerge FEM · Experimental Run form (N-port; server classifies geometry). */
export default function EmergeRun(props: { close: () => void }) {
  const number = (v: unknown, fallback: number) => Number((tryEvaluate(v as string | number, names().names).value ?? fallback).toPrecision(12));
  onMount(() => {
    const s = emergeSettings();
    const d = EMERGE_DEFAULT_SETTINGS;
    if (s.f_min_ghz === d.f_min_ghz && s.f_max_ghz === d.f_max_ghz && s.points === d.points) {
      patchEmergeSettings({
        f_min_ghz: String(number(draft.simulation?.f_min, 0.75)),
        f_max_ghz: String(number(draft.simulation?.f_max, 1.25)),
        points: "15",
      });
    }
    const hint = classifyEmergeDraft(draft.ports);
    setEmergeMode(hint === "driven" ? "emerge-driven" : "emerge-planar");
  });
  const values = () => {
    const s = emergeSettings();
    return {
      f_min_hz: s.f_min_ghz,
      f_max_hz: s.f_max_ghz,
      points: s.points,
      air_height_mm: s.air_height_mm,
      padding_mm: s.padding_mm,
      feed_width_mm: s.feed_width_mm,
    };
  };
  const setBand = (key: (typeof BAND_KEYS)[number], v: string) => {
    if (key === "f_min_hz") patchEmergeSettings({ f_min_ghz: v });
    else if (key === "f_max_hz") patchEmergeSettings({ f_max_ghz: v });
    else patchEmergeSettings({ points: v });
  };
  const enclosure = () => emergeSettings().enclosure;
  const setEnclosure = (v: EmergeEnclosure) => patchEmergeSettings({ enclosure: v });
  const resolution = () => {
    const s = emergeSettings();
    const adm = emergeAdmitResolution(s);
    return adm === "coarse" || adm === "fine" ? adm : s.resolution === "custom" ? "coarse" : s.resolution;
  };
  const setResolution = (v: "coarse" | "fine") => patchEmergeSettings({ resolution: v as EmergeResolutionPreset });
  const approxMetals = () => emergeSettings().approximate_metals;
  const setApproxMetals = (v: boolean) => patchEmergeSettings({ approximate_metals: v });

  const showPlanar = () => draftShowsPlanarEnclosure(draft.ports);
  const showDriven = () => draftShowsDrivenFeed(draft.ports);
  const showCoax = () => draftShowsCoaxPadding(draft.ports);
  const needFinite = () => draftNeedsFiniteFeedAccept(draft.ports);
  const needLumped = () => draftNeedsLumpedTerminalAccept(draft.ports);
  const needModal = () => draftNeedsModalPortAccept(draft.ports);
  const needCoax = () => draftNeedsCoaxialTemAccept(draft.ports);
  const previewPath = () => classifyEmergeDraft(draft.ports);

  const [mapKind, setMapKind] = createSignal<EmergeMapKind | null>(
    defaultMapKind(draft.ports, classifyEmergeDraft(draft.ports)),
  );
  const portPreviewOk = () => previewPorts(
    draft.ports,
    previewPath(),
    acceptIntentFromMapKind(mapKind()),
  ).ok;
  const [busy, setBusy] = createSignal(false);
  const [error, setError] = createSignal("");
  const [diagnostic, setDiagnostic] = createSignal("");
  const setup = () => { props.close(); openResearch(undefined, "emerge"); };
  let alive = true; onCleanup(() => { alive = false; });
  let alert: HTMLParagraphElement | undefined;
  createEffect(() => {
    if (error()) queueMicrotask(() => { if (alive) alert?.scrollIntoView({ block: "nearest" }); });
  });
  createEffect(() => {
    // Keep Sim Settings face hint aligned with the draft port mix.
    const hint = previewPath();
    setEmergeMode(hint === "driven" ? "emerge-driven" : "emerge-planar");
    // Default map when ports/path change; keep user pick if still admitted.
    const next = defaultMapKind(draft.ports, hint);
    const first = Array.isArray(draft.ports) && draft.ports.length ? draft.ports[0] : null;
    const rawType = first?.type;
    const type = rawType == null ? "lumped" : String(rawType);
    const allowed = new Set(mapOptionsFor(type, hint).map((o) => o.kind));
    const cur = mapKind();
    const resolved = cur != null && allowed.has(cur) ? cur : next;
    if (resolved !== cur) setMapKind(resolved);
    setSessionEmergeMapKind(resolved);
  });

  const invalid = () => {
    const v = values();
    // Coax admit caps at 21 points; planar/driven Run UI still allows up to 41.
    const pointsMax = showCoax() ? 21 : 41;
    const bandBad = BAND_KEYS.some(key => !v[key].trim() || !Number.isFinite(Number(v[key])) || Number(v[key]) <= 0)
      || Number(v.f_min_hz) >= Number(v.f_max_hz)
      || !Number.isInteger(Number(v.points)) || Number(v.points) < 3 || Number(v.points) > pointsMax;
    if (bandBad) return true;
    // Supported paths default-map on open; only block when a map is still required but missing.
    if ((needLumped() || needModal() || needFinite() || needCoax()) && mapKind() == null) return true;
    if (showPlanar()) {
      if (!v.air_height_mm.trim() || !Number.isFinite(Number(v.air_height_mm)) || Number(v.air_height_mm) <= 0) return true;
      if (enclosure() === "open") {
        if (!v.padding_mm.trim() || !Number.isFinite(Number(v.padding_mm)) || Number(v.padding_mm) <= 0) return true;
      }
    }
    if (showDriven()) {
      if (!v.feed_width_mm.trim() || !Number.isFinite(Number(v.feed_width_mm)) || Number(v.feed_width_mm) <= 0) return true;
      // Driven fallback always needs padding; planar open already validated padding above.
      if (enclosure() !== "open") {
        if (!v.padding_mm.trim() || !Number.isFinite(Number(v.padding_mm)) || Number(v.padding_mm) <= 0) return true;
      }
    }
    if (showCoax()) {
      if (!v.padding_mm.trim() || !Number.isFinite(Number(v.padding_mm)) || Number(v.padding_mm) <= 0) return true;
    }
    // Empty field-cut list = auto one frequency; non-empty must parse to ≤4 positive GHz.
    if (fieldCutFrequenciesHzFromText(emergeSettings().field_cut_frequencies_ghz) === null) return true;
    if (!portPreviewOk()) return true;
    if (errorCount() > 0) return true;
    return false;
  };

  const submit = async (e: Event) => {
    e.preventDefault(); if (invalid() || busy() || !file() || errorCount() > 0) return;
    setBusy(true); setError(""); setDiagnostic("");
    const request = defaultDesignerSession.asyncState.ticket();
    const initialFile = file()!;
    const ownsRequest = () => alive && defaultDesignerSession.asyncState.isDraftCurrent(request)
      && file()?.id === initialFile.id && file()?.hash === initialFile.hash && file()?.backup_scope === initialFile.backup_scope;
    try {
      const health = await api.health();
      if (!ownsRequest()) return;
      if ((health.emerge ?? 0) < 3 || (hasDocumentResultScope(file()) && !health.research_source)) throw Error(t("emergeExp.serverUpdate"));
      const capability = await api.researchProbe("emerge", researchPath("emerge"));
      if (!ownsRequest()) return;
      if (!capability.available) {
        setDiagnostic(capability.reason ?? "");
        throw Error(t("emergeExp.unavailable"));
      }
      const target = await prepareSavedDesign(() => alive);
      if (!alive) return;
      if (!target?.isCurrent()) throw Error(t("run.err.notSaved"));
      const settings = emergeNportSettings(draft.ports, mapKind());
      const saved = target.file;
      const source = emergeResearchSource(health, saved);
      if (hasDocumentResultScope(saved) && !source) throw Error(t("emergeExp.serverUpdate"));
      if (!target.isCurrent()) return;
      const job = await api.researchStart({
        backend: "emerge", path: researchPath("emerge"),
        design: structuredClone(saved.design), settings, ...(source ? { source } : {}),
      });
      void refreshRuns(); if (target.isCurrent()) { props.close(); followInDesigner(job); }
    } catch (err) { if (alive) setError((err as Error).message); } finally { if (alive) setBusy(false); }
  };

  return <form class="rd-body" onSubmit={submit} data-testid="emerge-run-form">
    <RunChecksAlert onNavigate={props.close} />
    <p class="note">{t("emergeExp.scope")}</p>
    <p class="note">{t("emergeExp.limitations")}</p>
    <div class="cluster"><p class="note">{t("emergeExp.setupHint")}</p>
      <button class="btn btn-ghost btn-sm" type="button" disabled={busy()} onClick={setup}>{t("emergeExp.setup")}</button>
    </div>
    <fieldset class="stack" disabled={busy()}><legend>{t("emergeExp.option")}</legend>
      <div class="rd-grid">
        <For each={BAND_KEYS}>{key => <label class="dz-field">
          <span class="dz-label">{t(`emergeExp.${key}`)}</span>
          <NumberField class="rp-input dz-input mono" required value={values()[key]} aria-label={t(`emergeExp.${key}`)}
            onInput={e => { const v = e.currentTarget.value; setBand(key, v); }} />
        </label>}</For>
        <Show when={showPlanar()}>
          <label class="dz-field">
            <span class="dz-label">{t("emergeExp.air_height_mm")}</span>
            <NumberField class="rp-input dz-input mono" required value={values().air_height_mm} aria-label={t("emergeExp.air_height_mm")}
              onInput={e => patchEmergeSettings({ air_height_mm: e.currentTarget.value })} />
          </label>
          <label class="dz-field">
            <span class="dz-label">{t("emergeExp.enclosure")}</span>
            <select class="rp-select dz-input mono" data-testid="emerge-run-enclosure" aria-label={t("emergeExp.enclosure")} value={enclosure()}
              onChange={e => setEnclosure(e.currentTarget.value as EmergeEnclosure)}>
              <option value="shielded">{t("emergeExp.shielded")}</option>
              <option value="open">{t("emergeExp.open")}</option>
            </select>
          </label>
        </Show>
        <Show when={enclosure() === "open" || showDriven() || showCoax()}>
          <label class="dz-field">
            <span class="dz-label">{t("emergeExp.padding_mm")}</span>
            <NumberField class="rp-input dz-input mono" data-testid="emerge-run-padding" required value={values().padding_mm}
              aria-label={t("emergeExp.padding_mm")}
              onInput={e => patchEmergeSettings({ padding_mm: e.currentTarget.value })} />
          </label>
        </Show>
        <Show when={showDriven()}>
          <label class="dz-field">
            <span class="dz-label">{t("emergeExp.feed_width_mm")}</span>
            <NumberField class="rp-input dz-input mono" data-testid="emerge-run-feed" required value={values().feed_width_mm}
              aria-label={t("emergeExp.feed_width_mm")}
              onInput={e => patchEmergeSettings({ feed_width_mm: e.currentTarget.value })} />
          </label>
        </Show>
        <label class="dz-field">
          <span class="dz-label">{t("emergeExp.resolution")}</span>
          <select class="rp-select dz-input mono" data-testid="emerge-run-resolution" aria-label={t("emergeExp.resolution")} value={resolution()}
            onChange={e => setResolution(e.currentTarget.value as "coarse" | "fine")}>
            <option value="coarse">{t("emergeExp.coarse")}</option>
            <option value="fine">{t("emergeExp.fine")}</option>
          </select>
        </label>
        <label class="dz-field" style={{ "grid-column": "1 / -1" }}>
          <span class="dz-label">{t("emergeExp.fieldCutFrequencies")}{" "}
            <span class="dz-unit">{t("emergeExp.fieldCutFrequencies.hint", { max: FIELD_CUT_FREQS_MAX })}</span></span>
          <input class="rp-input dz-input mono" type="text" spellcheck={false} autocomplete="off"
            data-testid="emerge-run-field-cut-freqs"
            aria-label={t("emergeExp.fieldCutFrequencies")}
            placeholder={t("emergeExp.fieldCutFrequencies.placeholder")}
            value={emergeSettings().field_cut_frequencies_ghz}
            onInput={e => patchEmergeSettings({ field_cut_frequencies_ghz: e.currentTarget.value })} />
        </label>
      </div>
      <p class="note">{t("emergeExp.fieldCutFrequencies.note")}</p>
      <Show when={showPlanar()}>
        <p class="note">{t(enclosure() === "shielded" ? "emergeExp.enclosureShieldedHint" : "emergeExp.enclosureOpenHint")}</p>
      </Show>
      <Show when={showDriven() && !showPlanar()}>
        <p class="note">{t("emergeExp.boundary")}</p>
      </Show>
      <Show when={showCoax()}>
        <p class="note">{t("emergeExp.coaxBoundary")}</p>
      </Show>
      <Show when={!showCoax()}>
        <label class="gs-check"><input type="checkbox" checked={approxMetals()} onChange={e => setApproxMetals(e.currentTarget.checked)} />{t("emergeExp.approximateMetals")}</label>
      </Show>
      <EmergePortMapPreview path={previewPath()} mapKind={mapKind()} onMapKind={(kind) => { setMapKind(kind); setSessionEmergeMapKind(kind); }} />
    </fieldset>
    <Show when={error()}><div ref={alert} class="status-block status-critical" role="alert"><p>{error()}</p></div></Show>
    <Show when={diagnostic()}><details><summary>{t("common.details")}</summary><p class="note">{diagnostic()}</p></details></Show>
    <div class="dialog-actions"><button class="btn btn-primary" type="submit" disabled={busy() || invalid()}>{busy() ? t("run.starting") : t("run.saveAndRun")}</button></div>
  </form>;
}
