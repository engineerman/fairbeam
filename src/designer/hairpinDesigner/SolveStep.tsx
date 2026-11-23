import { Show } from "solid-js";
import { t } from "../../i18n";
import {
  hairpinCancelEdc,
  hairpinEdc,
  hairpinSelectClosedForm,
  hairpinSelectEdc,
  hairpinSolveChoice,
  hairpinSolveError,
  hairpinSolving,
  hairpinStartEdc,
  type HairpinSolveChoice,
} from "./state";

const CHOICES: HairpinSolveChoice[] = ["closed_form", "edc"];

function edcPhaseLabel(phase: "qe" | "k" | "assemble" | null | undefined): string {
  if (phase === "qe") return t("hairpinDesigner.edc.phase.qe");
  if (phase === "k") return t("hairpinDesigner.edc.phase.k");
  if (phase === "assemble") return t("hairpinDesigner.edc.phase.assemble");
  return "";
}

export default function SolveStep() {
  const study = hairpinEdc;
  const edcActive = () => {
    const row = study();
    return hairpinSolving() || row?.status === "running" || row?.status === "done";
  };
  return (
    <div class="hd-solve">
      <div class="hd-cards" role="radiogroup" aria-label={t("hairpinDesigner.step.solve")}>
        {CHOICES.map((id) => (
          <button
            type="button"
            class="hd-card"
            role="radio"
            aria-checked={hairpinSolveChoice() === id}
            disabled={id === "edc" && hairpinSolving()}
            onClick={() => {
              if (id === "closed_form") hairpinSelectClosedForm();
              else hairpinSelectEdc();
            }}
          >
            <strong class="hd-card-title">{t(id === "closed_form" ? "hairpinDesigner.solve.closedForm" : "hairpinDesigner.solve.edc")}</strong>
            <span class="hd-info">{t(id === "closed_form" ? "hairpinDesigner.solve.closedFormInfo" : "hairpinDesigner.solve.edcInfo")}</span>
          </button>
        ))}
      </div>
      <Show when={hairpinSolveChoice() === "edc" && !edcActive()}>
        <button type="button" class="btn btn-primary hd-edc-start" onClick={() => void hairpinStartEdc()}>
          {t("hairpinDesigner.solve.startEdc")}
        </button>
      </Show>
      <Show when={hairpinSolveChoice() === "edc" && edcActive()}>
        <Show when={study()} fallback={
          <div>
            <progress class="hd-progress" aria-label={t("hairpinDesigner.edc.queued")} />
            <button type="button" class="btn btn-ghost" onClick={() => void hairpinCancelEdc()}>{t("hairpinDesigner.solve.cancel")}</button>
          </div>
        }>
          {(row) => (
            <div>
              <Show when={row().status === "done"} fallback={
                <>
                  <progress class="hd-progress" max={1} value={row().run_fraction ?? 0} aria-label={t("hairpinDesigner.solve.progress", { done: String(row().completed), total: String(row().total) })} />
                  <p class="hd-info">{t("hairpinDesigner.solve.progress", { done: String(row().completed), total: String(row().total) })}</p>
                  <p class="hd-info">{t("hairpinDesigner.edc.samplePercent", { pct: String(Math.round((row().run_fraction ?? 0) * 100)) })}</p>
                  <Show when={row().sample_status === "queued"}>
                    <p class="hd-info">{t("hairpinDesigner.edc.queued")}</p>
                  </Show>
                  <Show when={row().phase === "qe" || row().phase === "k" || row().phase === "assemble"}>
                    <p class="hd-info">{edcPhaseLabel(row().phase)}</p>
                  </Show>
                  <Show when={row().status === "running"}>
                    <button type="button" class="btn btn-ghost" onClick={() => void hairpinCancelEdc()}>{t("hairpinDesigner.solve.cancel")}</button>
                  </Show>
                </>
              }>
                <p class="hd-info">{t("hairpinDesigner.solve.progress", { done: String(row().completed), total: String(row().total) })}</p>
              </Show>
            </div>
          )}
        </Show>
      </Show>
      <Show when={hairpinSolveError()}>
        <p class="status-block status-critical" role="alert">{hairpinSolveError()}</p>
      </Show>
    </div>
  );
}
