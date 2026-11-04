import { createEffect, createSignal, For, onCleanup, Show } from "solid-js";
import { api } from "../runner/api";
import { openResearch, researchPath } from "../runner/researchState";
import { followInDesigner } from "../runner/designRun";
import { refreshRuns } from "../runner/store";
import { defaultDesignerSession, draft, file, names, prepareSavedDesign } from "./store";
import { tryEvaluate } from "./expr";
import { t } from "../i18n";
import NumberField from "../components/NumberField";
import { hasDocumentResultScope } from "../lib/nativeDocuments";

const NUMBER_KEYS = ["f_min_hz", "f_max_hz", "points", "air_height_mm"] as const;

export default function EmergePlanarRun(props: { close: () => void }) {
  const number = (v: unknown, fallback: number) => Number((tryEvaluate(v as string | number, names().names).value ?? fallback).toPrecision(12));
  const [values, setValues] = createSignal({
    f_min_hz: String(number(draft.simulation?.f_min, 0.75)),
    f_max_hz: String(number(draft.simulation?.f_max, 1.25)),
    points: "11",
    air_height_mm: "8",
    padding_mm: "10",
  });
  const [enclosure, setEnclosure] = createSignal<"shielded" | "open">("shielded");
  const [resolution, setResolution] = createSignal<"coarse" | "fine">("coarse");
  const [approxMetals, setApproxMetals] = createSignal(false);
  const [ack, setAck] = createSignal(false);
  const [busy, setBusy] = createSignal(false);
  const [error, setError] = createSignal("");
  const [diagnostic, setDiagnostic] = createSignal("");
  const setup = () => { props.close(); openResearch(undefined, "emerge"); };
  let alive = true; onCleanup(() => { alive = false; });
  let alert: HTMLParagraphElement | undefined;
  createEffect(() => {
    if (error()) queueMicrotask(() => { if (alive) alert?.scrollIntoView({ block: "nearest" }); });
  });
  const numberInvalid = () => {
    const v = values();
    const base = NUMBER_KEYS.some(key => !v[key].trim() || !Number.isFinite(Number(v[key])) || Number(v[key]) <= 0)
      || Number(v.f_min_hz) >= Number(v.f_max_hz)
      || !Number.isInteger(Number(v.points)) || Number(v.points) < 3 || Number(v.points) > 41;
    if (enclosure() === "open") {
      return base || !v.padding_mm.trim() || !Number.isFinite(Number(v.padding_mm)) || Number(v.padding_mm) <= 0;
    }
    return base;
  };
  const invalid = () => !ack() || numberInvalid();
  const submit = async (e: Event) => {
    e.preventDefault(); if (invalid() || busy() || !file()) return;
    setBusy(true); setError(""); setDiagnostic("");
    const request = defaultDesignerSession.asyncState.ticket();
    const initialFile = file()!;
    const ownsRequest = () => alive && defaultDesignerSession.asyncState.isDraftCurrent(request)
      && file()?.id === initialFile.id && file()?.hash === initialFile.hash && file()?.backup_scope === initialFile.backup_scope;
    try {
      const health = await api.health();
      if (!ownsRequest()) return;
      if ((health.emerge ?? 0) < 3 || (hasDocumentResultScope(file()) && !health.research_source)) throw Error(t("emergePlanar.serverUpdate"));
      const capability = await api.researchProbe("emerge", researchPath("emerge"));
      if (!ownsRequest()) return;
      if (!capability.available) {
        setDiagnostic(capability.reason ?? "");
        throw Error(t("emergePlanar.unavailable"));
      }
      const target = await prepareSavedDesign(() => alive);
      if (!alive) return;
      if (!target?.isCurrent()) throw Error(t("run.err.notSaved"));
      const settings: Record<string, unknown> = {
        analysis: "planar_two_port",
        accept_lumped_terminals: true,
        approximate_metals: approxMetals(),
        resolution: resolution(),
        enclosure: enclosure(),
      };
      for (const key of NUMBER_KEYS) settings[key] = Number(values()[key]) * (key.endsWith("_hz") ? 1e9 : 1);
      if (enclosure() === "open") settings.padding_mm = Number(values().padding_mm);
      const saved = target.file;
      const source = health.research_source && saved.backup_scope
        ? { model_id: saved.id, workspace_hash: saved.hash, backup_scope: saved.backup_scope } : undefined;
      if (hasDocumentResultScope(saved) && !source) throw Error(t("emergePlanar.serverUpdate"));
      if (!target.isCurrent()) return;
      const job = await api.researchStart({
        backend: "emerge", path: researchPath("emerge"),
        design: structuredClone(saved.design), settings, ...(source ? { source } : {}),
      });
      void refreshRuns(); if (target.isCurrent()) { props.close(); followInDesigner(job); }
    } catch (err) { if (alive) setError((err as Error).message); } finally { if (alive) setBusy(false); }
  };
  return <form class="rd-body" onSubmit={submit} data-testid="emerge-planar-form">
    <p class="note">{t("emergePlanar.scope")}</p>
    <p class="note">{t("emergePlanar.limitations")}</p>
    <div class="cluster"><p class="note">{t("emergePlanar.setupHint")}</p>
      <button class="btn btn-ghost btn-sm" type="button" disabled={busy()} onClick={setup}>{t("emergePlanar.setup")}</button>
    </div>
    <fieldset class="stack" disabled={busy()}><legend>{t("emergePlanar.option")}</legend>
      <div class="rd-grid"><For each={NUMBER_KEYS}>{key => <label class="dz-field">
        <span class="dz-label">{t(`emergePlanar.${key}`)}</span>
        <NumberField class="rp-input dz-input mono" required value={values()[key]} aria-label={t(`emergePlanar.${key}`)}
          onInput={e => { const v = e.currentTarget.value; setValues(old => ({ ...old, [key]: v })); }} />
      </label>}</For>
        <label class="dz-field">
          <span class="dz-label">{t("emergePlanar.enclosure")}</span>
          <select class="rp-select dz-input mono" data-testid="emerge-planar-enclosure" aria-label={t("emergePlanar.enclosure")} value={enclosure()}
            onChange={e => setEnclosure(e.currentTarget.value as "shielded" | "open")}>
            <option value="shielded">{t("emergePlanar.shielded")}</option>
            <option value="open">{t("emergePlanar.open")}</option>
          </select>
        </label>
        <Show when={enclosure() === "open"}>
          <label class="dz-field">
            <span class="dz-label">{t("emergePlanar.padding_mm")}</span>
            <NumberField class="rp-input dz-input mono" data-testid="emerge-planar-padding" required value={values().padding_mm}
              aria-label={t("emergePlanar.padding_mm")}
              onInput={e => { const v = e.currentTarget.value; setValues(old => ({ ...old, padding_mm: v })); }} />
          </label>
        </Show>
        <label class="dz-field">
          <span class="dz-label">{t("emergePlanar.resolution")}</span>
          <select class="rp-select dz-input mono" data-testid="emerge-planar-resolution" aria-label={t("emergePlanar.resolution")} value={resolution()}
            onChange={e => setResolution(e.currentTarget.value as "coarse" | "fine")}>
            <option value="coarse">{t("emergePlanar.coarse")}</option>
            <option value="fine">{t("emergePlanar.fine")}</option>
          </select>
        </label>
      </div>
      <p class="note">{t(enclosure() === "shielded" ? "emergePlanar.enclosureShieldedHint" : "emergePlanar.enclosureOpenHint")}</p>
      <label class="gs-check"><input type="checkbox" checked={approxMetals()} onChange={e => setApproxMetals(e.currentTarget.checked)} />{t("emergePlanar.approximateMetals")}</label>
      <label class="gs-check"><input type="checkbox" data-testid="emerge-planar-accept" checked={ack()} onChange={e => setAck(e.currentTarget.checked)} />{t("emergePlanar.accept")}</label>
    </fieldset>
    <Show when={error()}><p ref={alert} class="status-block status-critical" role="alert">{error()}</p></Show>
    <Show when={diagnostic()}><details><summary>{t("common.details")}</summary><p class="note">{diagnostic()}</p></details></Show>
    <div class="dialog-actions"><button class="btn btn-primary" type="submit" disabled={busy() || invalid()}>{busy() ? t("run.starting") : t("run.saveAndRun")}</button></div>
  </form>;
}
