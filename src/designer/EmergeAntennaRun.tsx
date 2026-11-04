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

const NUMBER_KEYS = ["f_min_hz", "f_max_hz", "points", "padding_mm", "feed_width_mm"] as const;

export default function EmergeAntennaRun(props: { close: () => void }) {
  const number = (v: unknown, fallback: number) => Number((tryEvaluate(v as string | number, names().names).value ?? fallback).toPrecision(12));
  const [values, setValues] = createSignal({
    f_min_hz: String(number(draft.simulation?.f_min, 1.5)),
    f_max_hz: String(number(draft.simulation?.f_max, 3.2)),
    points: "11",
    padding_mm: "40",
    feed_width_mm: "1",
  });
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
  const invalid = () => !ack()
    || Object.values(values()).some(v => !v.trim() || !Number.isFinite(Number(v)) || Number(v) <= 0)
    || Number(values().f_min_hz) >= Number(values().f_max_hz)
    || !Number.isInteger(Number(values().points)) || Number(values().points) < 3 || Number(values().points) > 21;
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
      if ((health.emerge ?? 0) < 2 || (hasDocumentResultScope(file()) && !health.research_source)) throw Error(t("emergeAntenna.serverUpdate"));
      const capability = await api.researchProbe("emerge", researchPath("emerge"));
      if (!ownsRequest()) return;
      if (!capability.available) {
        setDiagnostic(capability.reason ?? "");
        throw Error(t("emergeAntenna.unavailable"));
      }
      const target = await prepareSavedDesign(() => alive);
      if (!alive) return;
      if (!target?.isCurrent()) throw Error(t("run.err.notSaved"));
      const settings: Record<string, unknown> = {
        analysis: "driven",
        accept_finite_feed: true,
        approximate_metals: approxMetals(),
        resolution: resolution(),
      };
      for (const key of NUMBER_KEYS) settings[key] = Number(values()[key]) * (key.endsWith("_hz") ? 1e9 : 1);
      const saved = target.file;
      const source = health.research_source && saved.backup_scope
        ? { model_id: saved.id, workspace_hash: saved.hash, backup_scope: saved.backup_scope } : undefined;
      if (hasDocumentResultScope(saved) && !source) throw Error(t("emergeAntenna.serverUpdate"));
      if (!target.isCurrent()) return;
      const job = await api.researchStart({
        backend: "emerge", path: researchPath("emerge"),
        design: structuredClone(saved.design), settings, ...(source ? { source } : {}),
      });
      void refreshRuns(); if (target.isCurrent()) { props.close(); followInDesigner(job); }
    } catch (err) { if (alive) setError((err as Error).message); } finally { if (alive) setBusy(false); }
  };
  return <form class="rd-body" onSubmit={submit} data-testid="emerge-antenna-form">
    <p class="note">{t("emergeAntenna.scope")}</p>
    <p class="note">{t("emergeAntenna.limitations")}</p>
    <div class="cluster"><p class="note">{t("emergeAntenna.setupHint")}</p>
      <button class="btn btn-ghost btn-sm" type="button" disabled={busy()} onClick={setup}>{t("emergeAntenna.setup")}</button>
    </div>
    <fieldset class="stack" disabled={busy()}><legend>{t("emergeAntenna.option")}</legend>
      <div class="rd-grid"><For each={NUMBER_KEYS}>{key => <label class="dz-field">
        <span class="dz-label">{t(`emergeAntenna.${key}`)}</span>
        <NumberField class="rp-input dz-input mono" required value={values()[key]} aria-label={t(`emergeAntenna.${key}`)}
          onInput={e => { const v = e.currentTarget.value; setValues(old => ({ ...old, [key]: v })); }} />
      </label>}</For>
        <label class="dz-field">
          <span class="dz-label">{t("emergeAntenna.resolution")}</span>
          <select class="rp-select dz-input mono" data-testid="emerge-antenna-resolution" aria-label={t("emergeAntenna.resolution")} value={resolution()}
            onChange={e => setResolution(e.currentTarget.value as "coarse" | "fine")}>
            <option value="coarse">{t("emergeAntenna.coarse")}</option>
            <option value="fine">{t("emergeAntenna.fine")}</option>
          </select>
        </label>
      </div>
      <p class="note">{t("emergeAntenna.boundary")}</p>
      <label class="gs-check"><input type="checkbox" checked={approxMetals()} onChange={e => setApproxMetals(e.currentTarget.checked)} />{t("emergeAntenna.approximateMetals")}</label>
      <label class="gs-check"><input type="checkbox" data-testid="emerge-antenna-accept" checked={ack()} onChange={e => setAck(e.currentTarget.checked)} />{t("emergeAntenna.accept")}</label>
    </fieldset>
    <Show when={error()}><p ref={alert} class="status-block status-critical" role="alert">{error()}</p></Show>
    <Show when={diagnostic()}><details><summary>{t("common.details")}</summary><p class="note">{diagnostic()}</p></details></Show>
    <div class="dialog-actions"><button class="btn btn-primary" type="submit" disabled={busy() || invalid()}>{busy() ? t("run.starting") : t("run.saveAndRun")}</button></div>
  </form>;
}
